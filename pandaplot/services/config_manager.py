"""Configuration Manager Service (Phase 1.2)

Responsibilities:
    * Manage a singleton-like ApplicationConfig instance
    * Load / save configuration JSON from disk
    * Provide update & reset operations with validation
    * Emit lifecycle events on the shared EventBus

Events emitted (data always includes the *current* config object under key 'config'):
    - config.loaded  : after successful load (even if defaults due to missing/corrupt file)
    - config.updated : after in-memory update/merge
    - config.saved   : after persisting to disk
    - config.reset   : after resetting to defaults

Notes:
    * Migration is deferred to a later phase (a hook is reserved where version differs)
    * The manager is filesystem agnostic apart from the Path passed on construction
    * All file operations are defensive; failures fall back to defaults & log warnings
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Optional
import logging
import shutil

from pandaplot.models.state.config import ApplicationConfig
from pandaplot.models.events.event_bus import EventBus
from pandaplot.services.config_validation import validate_config


class ConfigManager:
    """Manage application configuration persistence & lifecycle."""

    def __init__(self, event_bus: EventBus, config_path: Optional[Path] = None, *, auto_save: bool = True, backup: bool = True) -> None:
        self._log = logging.getLogger(__name__)
        self._event_bus = event_bus
        self._auto_save = auto_save
        self._backup_enabled = backup

        if config_path is None:
            # Default user config directory (~/.pandaplot/config.json)
            config_dir = Path.home() / ".pandaplot"
            config_dir.mkdir(parents=True, exist_ok=True)
            config_path = config_dir / "config.json"
        else:
            # Ensure parent exists
            config_path.parent.mkdir(parents=True, exist_ok=True)
        self._config_path = config_path

        self._config: ApplicationConfig = ApplicationConfig.default()

    # ---------------------------------------------------------------------
    # Properties
    # ---------------------------------------------------------------------
    @property
    def config(self) -> ApplicationConfig:  # read-only exposure
        return self._config

    @property
    def path(self) -> Path:
        return self._config_path

    # ---------------------------------------------------------------------
    # Core operations
    # ---------------------------------------------------------------------
    def load(self) -> ApplicationConfig:
        """Load configuration from disk (or defaults if unavailable).

        Returns live ApplicationConfig instance referenced by manager.
        Emits config.loaded event regardless of success (with 'source': 'file'|'default').
        """
        source = "default"
        if self._config_path.exists():
            try:
                raw = self._config_path.read_text(encoding="utf-8")
                loaded = ApplicationConfig.from_json(raw)
                # Hook for future migration when loaded.version != CONFIG_VERSION
                self._config = loaded
                source = "file"
            except Exception as exc:  # noqa: BLE001
                self._log.warning("Failed to load config; using defaults (%s)", exc)
                self._config = ApplicationConfig.default()
        else:
            self._config = ApplicationConfig.default()
        warnings = validate_config(self._config)
        self._event_bus.emit(
            "config.loaded",
            {"config": self._config, "source": source, "warnings": warnings},
        )
        return self._config

    def save(self) -> None:
        """Persist current configuration to disk (JSON)."""
        try:
            if self._backup_enabled and self._config_path.exists():
                backup_path = self._config_path.with_suffix(self._config_path.suffix + ".bak")
                try:
                    shutil.copy2(self._config_path, backup_path)
                except Exception as exc:  # noqa: BLE001
                    self._log.warning("Failed to create backup of config: %s", exc)

            data = self._config.to_json(indent=2)
            self._config_path.write_text(data, encoding="utf-8")
            self._event_bus.emit("config.saved", {"config": self._config, "path": str(self._config_path)})
        except Exception as exc:  # noqa: BLE001
            self._log.error("Failed to save configuration: %s", exc)

    def update(self, mapping: Mapping[str, Any], *, save: Optional[bool] = None) -> ApplicationConfig:
        """Merge mapping into config and emit update.

        Args:
            mapping: partial nested mapping matching ApplicationConfig sections
            save: override auto_save behaviour (True/False). If None uses manager default.
        """
        before = self._config.to_dict()
        self._config.update_from_mapping(mapping)
        warnings = validate_config(self._config)
        after = self._config.to_dict()

        changes = _diff_nested(before, after)
        self._event_bus.emit(
            "config.updated",
            {"config": self._config, "changes": changes, "warnings": warnings},
        )

        do_save = self._auto_save if save is None else save
        if do_save:
            self.save()
        return self._config

    def reset(self, *, save: bool | None = None) -> ApplicationConfig:
        """Reset configuration to defaults (in-place)."""
        self._config.reset_defaults()
        warnings = validate_config(self._config)
        self._event_bus.emit("config.reset", {"config": self._config, "warnings": warnings})
        self._event_bus.emit(
            "config.updated", {"config": self._config, "changes": {"*": "reset"}, "warnings": warnings}
        )
        if (self._auto_save if save is None else save):
            self.save()
        return self._config

    # Convenience wrappers
    def get(self) -> ApplicationConfig:
        return self._config

    def as_dict(self) -> dict:
        return self._config.to_dict()


# -------------------------------------------------------------------------
# Utility: compute nested diff (very small; avoids external deps)
# -------------------------------------------------------------------------

def _diff_nested(before: dict, after: dict) -> dict:
    """Return a nested dict of changes {path: (old, new)}.

    For simplicity paths are represented with dot notation keys.
    """
    changes: dict[str, tuple[Any, Any]] = {}

    def walk(b: Any, a: Any, path: str = "") -> None:
        if isinstance(b, dict) and isinstance(a, dict):
            # union of keys
            for key in set(b.keys()) | set(a.keys()):
                nb = b.get(key)
                na = a.get(key)
                new_path = f"{path}.{key}" if path else str(key)
                walk(nb, na, new_path)
        else:
            if b != a:
                changes[path] = (b, a)

    walk(before, after)
    return changes


__all__ = ["ConfigManager"]

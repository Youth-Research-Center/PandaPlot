"""Configuration data model (Phase 1.1).

This module defines the data *model* for the application configuration.
The *manager* (load/save, event emission) will be added in Phase 1.2.

Design goals:
	* Explicit section dataclasses (clarity / validation)
	* JSON‑serialisable (primitive types only in ``to_dict`` output)
	* Forward compatible (``version`` field + tolerant parsing)
	* Safe defaults and graceful fallback for malformed input

Future phases (migration, project specific overrides, events) will build
upon the structures defined here.
"""

from __future__ import annotations

import copy
import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, Mapping

CONFIG_VERSION = "1.0.0"  # Increment when structure changes (migration hook)


class Theme(str, Enum):
	"""Enumerated UI themes.

	Keeping as ``str`` subclass so values serialize directly.
	"""

	LIGHT = "light"
	DARK = "dark"
	SYSTEM = "system"  # Follow OS / desktop environment


@dataclass(slots=True)
class AutoSaveConfig:
	enabled: bool = True
	interval_seconds: int = 120  # Reasonable default (2 min)

	def validate(self) -> None:
		if self.interval_seconds <= 0:
			# Fallback to a sane minimum rather than raising hard errors upstream
			self.interval_seconds = 60


@dataclass(slots=True)
class AppearanceConfig:
	theme: Theme = Theme.SYSTEM
	accent_color: str = "#3B82F6"  # Tailwind blue-500 style default
	interface_font_size: int = 12
	editor_font_size: int = 12

	def validate(self) -> None:
		if self.interface_font_size < 8:
			self.interface_font_size = 8
		if self.editor_font_size < 8:
			self.editor_font_size = 8


@dataclass(slots=True)
class EditorConfig:
	word_wrap: bool = True
	line_numbers: bool = True
	tab_size: int = 4

	def validate(self) -> None:
		if self.tab_size <= 0:
			self.tab_size = 4
		if self.tab_size > 16:  # Arbitrary upper bound to prevent absurd values
			self.tab_size = 16


@dataclass(slots=True)
class ProjectConfig:
	"""Placeholder for future per‑project overrides.

	Currently empty; defined now to ease integration when TASK-001 arrives.
	"""

	# Example future field (commented):
	# default_chart_type: str = "line"

	def validate(self) -> None:  # noqa: D401 (simple placeholder)
		"""No validation rules yet."""
		return


@dataclass(slots=True)
class ApplicationConfig:
	"""Top-level application configuration.

	Contains global (cross‑project) settings plus nested sections. The public
	API intentionally keeps only a small set of convenience methods; persistence
	semantics belong in the forthcoming manager service.
	"""

	version: str = CONFIG_VERSION
	auto_save: AutoSaveConfig = field(default_factory=AutoSaveConfig)
	appearance: AppearanceConfig = field(default_factory=AppearanceConfig)
	editor: EditorConfig = field(default_factory=EditorConfig)
	project: ProjectConfig = field(default_factory=ProjectConfig)
	recent_projects: list[str] = field(default_factory=list)

	# ----- construction helpers -------------------------------------------------
	@classmethod
	def default(cls) -> "ApplicationConfig":
		return cls()

	# ----- serialization --------------------------------------------------------
	def to_dict(self) -> Dict[str, Any]:
		"""Return a JSON‑safe dict.

		We avoid ``asdict`` for nested Enum normalisation.
		"""

		return {
			"version": self.version,
			"auto_save": asdict(self.auto_save),
			"appearance": {
				**asdict(self.appearance),
				"theme": self.appearance.theme.value,
			},
			"editor": asdict(self.editor),
			"project": asdict(self.project),
			"recent_projects": list(self.recent_projects),
		}

	def to_json(self, *, indent: int | None = 2) -> str:
		return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

	# ----- validation -----------------------------------------------------------
	def validate(self) -> None:
		self.auto_save.validate()
		self.appearance.validate()
		self.editor.validate()
		self.project.validate()

	# ----- mutation / update ----------------------------------------------------
	def update_from_mapping(self, data: Mapping[str, Any]) -> None:
		"""Merge values from a mapping (partial updates allowed).

		Unknown sections / keys are ignored (forward compatibility & safety).
		Primitive coercion is best‑effort; invalid types revert to defaults.
		"""

		# Sections mapping: section_name -> (instance, dataclass type)
		sections: Dict[str, Any] = {
			"auto_save": self.auto_save,
			"appearance": self.appearance,
			"editor": self.editor,
			"project": self.project,
		}

		# Handle recent_projects specially (flat list of strings)
		if isinstance(data.get("recent_projects"), list):
			clean: list[str] = []
			for entry in data["recent_projects"]:
				if isinstance(entry, str) and entry:
					clean.append(entry)
			# De-duplicate preserving order
			seen: set[str] = set()
			unique: list[str] = []
			for p in clean:
				if p not in seen:
					seen.add(p)
					unique.append(p)
			self.recent_projects = unique[:50]  # Cap to avoid unbounded growth

		for key, value in data.items():
			if key == "version":
				# We keep existing version if mismatch; manager handles migration.
				continue
			section_obj = sections.get(key)
			if section_obj is None or not isinstance(value, Mapping):
				continue
			for skey, sval in value.items():
				if not hasattr(section_obj, skey):
					continue
				current = getattr(section_obj, skey)
				try:
					if isinstance(current, Enum):
						# Accept either enum name or value
						if isinstance(sval, str):
							enum_type = type(current)
							try:
								sval_enum = enum_type(sval)  # by value
							except ValueError:
								try:
									sval_enum = enum_type[sval.upper()]
								except Exception:  # noqa: BLE001
									continue
							setattr(section_obj, skey, sval_enum)
						continue
					# Basic type coercion for int/bool/str
					if isinstance(current, bool):
						if isinstance(sval, bool):
							setattr(section_obj, skey, sval)
						elif isinstance(sval, str):
							lowered = sval.lower()
							if lowered in {"true", "1", "yes", "on"}:
								setattr(section_obj, skey, True)
							elif lowered in {"false", "0", "no", "off"}:
								setattr(section_obj, skey, False)
						continue
					if isinstance(current, int):
						if isinstance(sval, (int, float)):
							setattr(section_obj, skey, int(sval))
						elif isinstance(sval, str) and sval.isdigit():
							setattr(section_obj, skey, int(sval))
						continue
					if isinstance(current, str):
						if isinstance(sval, str):
							setattr(section_obj, skey, sval)
						continue
				except Exception:  # noqa: BLE001 - defensive; skip invalid
					continue

		self.validate()

	# ----- factory / parsing ----------------------------------------------------
	@classmethod
	def from_mapping(cls, data: Mapping[str, Any]) -> "ApplicationConfig":
		cfg = cls.default()
		if not isinstance(data, Mapping):
			return cfg
		# If version present but different we *still* parse; migrations later.
		cfg.update_from_mapping(data)
		return cfg

	@classmethod
	def from_dict(cls, data: Dict[str, Any]) -> "ApplicationConfig":  # alias
		return cls.from_mapping(data)

	@classmethod
	def from_json(cls, raw: str) -> "ApplicationConfig":
		try:
			data = json.loads(raw)
		except Exception:  # noqa: BLE001
			return cls.default()
		if not isinstance(data, dict):
			return cls.default()
		return cls.from_mapping(data)

	# ----- utility --------------------------------------------------------------
	def clone(self) -> "ApplicationConfig":
		return copy.deepcopy(self)

	def reset_defaults(self) -> None:
		"""Reset all sections to their default values (in-place)."""
		fresh = self.__class__.default()
		self.version = fresh.version
		self.auto_save = fresh.auto_save
		self.appearance = fresh.appearance
		self.editor = fresh.editor
		self.project = fresh.project


# Public export surface
__all__ = [
	"CONFIG_VERSION",
	"Theme",
	"AutoSaveConfig",
	"AppearanceConfig",
	"EditorConfig",
	"ProjectConfig",
	"ApplicationConfig",
]

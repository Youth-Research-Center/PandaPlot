from __future__ import annotations

from pandaplot.gui.components.common.section_header import SectionHeader
from pandaplot.gui.components.common.segmented_control import SegmentedControl
from pandaplot.models.events.event_bus import EventBus
from pandaplot.models.events.event_types import ThemeEvents
from pandaplot.models.state.config import ApplicationConfig, Theme
from pandaplot.services.theme.theme_manager import ThemeManager
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QListWidget,
    QMainWindow,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from pandaplot_storybook.color_contrast import SEGMENTED_SELECTED_TEXT, pick_contrasting_text
from pandaplot_storybook.controls import ControlsPanel
from pandaplot_storybook.registry import StoryDef, all_story_names, get_story

_THEME_OPTIONS = [("Light", "light"), ("Dark", "dark"), ("System", "system")]

# Storybook-local layout constants (see requirement 7: keep spacing/margins
# explicit and consistent between light/dark so nothing shifts when
# font-weight changes on selection, e.g. the SegmentedControl's
# `[selected="true"]` bold text).
_PANE_MARGINS = (10, 10, 10, 10)
_PANE_SPACING = 8
_SECTION_SPACING = 6


class MainWindow(QMainWindow):
    def __init__(
        self,
        theme_manager: ThemeManager,
        config: ApplicationConfig,
        event_bus: EventBus,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("PandaPlot Storybook")
        self._theme_manager = theme_manager
        self._config = config
        self._current_story_def: StoryDef | None = None
        self._current_story_name: str | None = None
        self._current_controls_panel: ControlsPanel | None = None
        self._section_headers: list[SectionHeader] = []
        self._panes: dict[str, QFrame] = {}

        # --- Sidebar pane -------------------------------------------------
        self._sidebar = QListWidget()
        self._sidebar.setObjectName("storySidebar")
        self._sidebar.addItems(all_story_names())
        self._sidebar.currentTextChanged.connect(self._on_story_selected)

        sidebar_pane = self._wrap_pane("sidebarPane", self._sidebar)

        # --- Preview pane ---------------------------------------------------
        self._breadcrumb = QLabel("")
        self._breadcrumb.setObjectName("previewBreadcrumb")

        self._preview_container = QWidget()
        self._preview_container.setObjectName("previewSurface")
        self._preview_layout = QVBoxLayout(self._preview_container)
        self._preview_layout.setContentsMargins(*_PANE_MARGINS)
        self._preview_layout.setSpacing(_PANE_SPACING)
        self._preview_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        preview_pane_layout_host = QWidget()
        preview_pane_layout = QVBoxLayout(preview_pane_layout_host)
        preview_pane_layout.setContentsMargins(*_PANE_MARGINS)
        preview_pane_layout.setSpacing(_PANE_SPACING)
        preview_pane_layout.addWidget(self._breadcrumb)
        preview_pane_layout.addWidget(self._preview_container, stretch=1)

        preview_pane = self._wrap_pane("previewPane", preview_pane_layout_host, own_margins=True)

        # --- Controls pane: "App Settings" + "Controls" sections ----------
        self._theme_switch = SegmentedControl(list(_THEME_OPTIONS))
        self._theme_switch.setCurrentValue(config.appearance.theme.value)
        self._theme_switch.currentValueChanged.connect(self.set_theme)
        self._apply_theme_switch_contrast_override()

        app_settings_section = self._build_section("App Settings", self._theme_switch)

        self._controls_host = QWidget()
        self._controls_host_layout = QVBoxLayout(self._controls_host)
        self._controls_host_layout.setContentsMargins(0, 0, 0, 0)
        self._controls_host_layout.setSpacing(_PANE_SPACING)
        controls_section = self._build_section("Controls", self._controls_host)

        controls_pane_layout_host = QWidget()
        controls_pane_layout = QVBoxLayout(controls_pane_layout_host)
        controls_pane_layout.setContentsMargins(*_PANE_MARGINS)
        controls_pane_layout.setSpacing(_SECTION_SPACING * 2)
        controls_pane_layout.addWidget(app_settings_section)
        controls_pane_layout.addWidget(controls_section)
        controls_pane_layout.addStretch(1)

        controls_pane = self._wrap_pane("controlsPane", controls_pane_layout_host, own_margins=True)

        splitter = QSplitter()
        splitter.addWidget(sidebar_pane)
        splitter.addWidget(preview_pane)
        splitter.addWidget(controls_pane)
        splitter.setSizes([200, 500, 300])

        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(splitter)
        self.setCentralWidget(central)

        self._apply_sidebar_selection_style()

        def _on_theme_changed(_data):
            self._refresh_preview()
            self._apply_theme_switch_contrast_override()
            self._apply_sidebar_selection_style()
            self._refresh_pane_styles()
            tokens = self._theme_manager.get_design_tokens()
            for header in self._section_headers:
                header.set_tokens(tokens)

        event_bus.subscribe(ThemeEvents.THEME_CHANGED, _on_theme_changed)

        if self._sidebar.count():
            self._sidebar.setCurrentRow(0)

    # ------------------------------------------------------------------
    # Layout helpers
    # ------------------------------------------------------------------
    def _wrap_pane(self, object_name: str, content: QWidget, *, own_margins: bool = False) -> QFrame:
        """Wrap a pane's content in a QFrame carrying a distinct per-pane
        background/border (see requirement 2), keyed off `object_name` so
        each splitter region reads as visually distinct rather than being
        separated by just the splitter's hairline.
        """
        pane = QFrame()
        pane.setObjectName(object_name)
        layout = QVBoxLayout(pane)
        if own_margins:
            # `content` already manages its own contentsMargins/spacing.
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
        else:
            layout.setContentsMargins(*_PANE_MARGINS)
            layout.setSpacing(_PANE_SPACING)
        layout.addWidget(content)
        self._panes[object_name] = pane
        self._style_pane(pane, object_name)
        return pane

    def _refresh_pane_styles(self) -> None:
        for object_name, pane in self._panes.items():
            self._style_pane(pane, object_name)

    def _build_section(self, title: str, content: QWidget) -> QWidget:
        """A titled, structurally independent section: a SectionHeader over
        `content`. Kept as its own container (rather than inlined) so lifting
        it into a QTabWidget page later is a small, localized change.
        """
        section = QWidget()
        section.setObjectName(f"section_{title.replace(' ', '')}")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(_SECTION_SPACING)
        header = SectionHeader(title)
        self._section_headers.append(header)
        layout.addWidget(header)
        layout.addWidget(content)
        return section

    def _style_pane(self, pane: QFrame, object_name: str) -> None:
        tokens = self._theme_manager.get_design_tokens()
        # Give the preview pane a recessed surface so it visually reads as
        # "the component under test" (requirement 3); sidebar/controls share
        # the app-chrome surface but are still separated from one another
        # and from the preview by a visible border (requirement 2).
        # Each pane gets its own background+border pairing so all three
        # splitter regions read as visually distinct at the outer-frame
        # level, not just via the preview's inner recessed surface below
        # (requirement 2 / review finding 2). Sidebar and controls both read
        # as "app chrome" (surface_white) but are told apart by border tone;
        # preview is the deliberate odd one out (surface_chrome), since it
        # already gets its own recessed inner surface_inset panel.
        pane_styles = {
            "sidebarPane": (tokens["surface_white"], tokens["border_panel"]),
            "previewPane": (tokens["surface_chrome"], tokens["border_panel"]),
            "controlsPane": (tokens["surface_white"], tokens["border_control"]),
        }
        background, border = pane_styles.get(
            object_name, (tokens["surface_chrome"], tokens["border_panel"])
        )
        pane.setStyleSheet(
            f"QFrame#{object_name} {{"
            f" background-color: {background};"
            f" border: 1px solid {border};"
            "}"
        )
        if object_name == "previewPane":
            self._preview_container.setStyleSheet(
                f"QWidget#previewSurface {{"
                f" background-color: {tokens['surface_inset']};"
                f" border: 1px solid {tokens['border_subtle']};"
                f" border-radius: {tokens['radius_card']}px;"
                "}"
            )
            self._breadcrumb.setStyleSheet(
                f"color: {tokens['text_secondary']}; font-weight: 600; padding: 0 2px;"
            )

    def _apply_theme_switch_contrast_override(self) -> None:
        """Storybook-local fix for requirement 4: pandaplot's global QSS
        pairs `accent_selected_bg` with `accent_active_text` for
        `QPushButton[segment="true"][selected="true"]`, which fails WCAG AA
        in dark mode. This instance-local stylesheet overrides just the
        selected-state colors on this SegmentedControl, using a pair
        verified (in storybook_tests/test_color_contrast.py) to clear 4.5:1
        against both themes' real `accent_selected_bg` token. Qt's
        per-widget stylesheet wins over the app-wide one for this subtree,
        so pandaplot's QSS is never touched.
        """
        tokens = self._theme_manager.get_design_tokens()
        theme_value = self._config.appearance.theme.value
        text_color = SEGMENTED_SELECTED_TEXT.get(theme_value, SEGMENTED_SELECTED_TEXT["light"])
        self._theme_switch.setStyleSheet(
            'QPushButton[segment="true"][selected="true"] {'
            f" background-color: {tokens['accent_selected_bg']};"
            f" color: {text_color};"
            "}"
        )

    def _apply_sidebar_selection_style(self) -> None:
        """Instance-local override: QListWidget's default selection uses
        QPalette::Highlight/HighlightedText, which Qt mutes when the widget
        lacks keyboard focus, so selection visibility would vary by focus
        state and theme. `accent_active_text` doesn't fix this either — it's
        tuned for accent text on light backgrounds, not text drawn on top of
        `accent`, and gives only ~1.22:1 contrast there. Instead we pick
        whichever of black/white clears WCAG AA against `accent` at render
        time (verified in storybook_tests/test_color_contrast.py).
        """
        tokens = self._theme_manager.get_design_tokens()
        selected_text = pick_contrasting_text(tokens["accent"])
        self._sidebar.setStyleSheet(
            "QListWidget::item {"
            f" padding: 4px 8px;"
            "}"
            "QListWidget::item:selected, QListWidget::item:selected:!active {"
            f" background-color: {tokens['accent']};"
            f" color: {selected_text};"
            "}"
            "QListWidget::item:hover {"
            f" background-color: {tokens['surface_inset']};"
            "}"
        )

    # ------------------------------------------------------------------
    # Behavior (unchanged from before this redesign)
    # ------------------------------------------------------------------
    def current_preview_widget(self) -> QWidget | None:
        if self._preview_layout.count() == 0:
            return None
        return self._preview_layout.itemAt(0).widget()

    def set_theme(self, theme_value: str) -> None:
        self._config.appearance.theme = Theme(theme_value)
        self._theme_manager.apply_from_config(self._config)

    def _on_story_selected(self, name: str) -> None:
        if not name:
            return
        self._current_story_name = name
        self._current_story_def = get_story(name)
        self._breadcrumb.setText(name)
        self._rebuild_controls_panel()
        self._refresh_preview()

    def _rebuild_controls_panel(self) -> None:
        self._clear_layout(self._controls_host_layout)
        assert self._current_story_def is not None
        tokens = self._theme_manager.get_design_tokens()
        panel = ControlsPanel(self._current_story_def.controls, tokens=tokens)
        panel.valuesChanged.connect(lambda _values: self._refresh_preview())
        self._controls_host_layout.addWidget(panel)
        self._current_controls_panel = panel

    def _refresh_preview(self) -> None:
        if self._current_story_def is None:
            return
        self._clear_layout(self._preview_layout)
        values = self._current_controls_panel.values() if self._current_controls_panel else {}
        tokens = self._theme_manager.get_design_tokens()
        widget = self._current_story_def.make_widget(values, tokens)
        if not isinstance(widget, QWidget):
            raise TypeError(f"Story '{self._current_story_name}' returned {widget!r}, expected a QWidget")
        if hasattr(widget, "set_tokens"):
            widget.set_tokens(tokens)
        self._preview_layout.addWidget(widget)

    @staticmethod
    def _clear_layout(layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()


__all__ = ["MainWindow"]

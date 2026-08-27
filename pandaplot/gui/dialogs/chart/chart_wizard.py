"""Top-level chart creation wizard: Type step, then Data step."""
from typing import Callable, Optional, override

from PySide6.QtCore import QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QWizard

from pandaplot.gui.core.widget_extension import PWizard
from pandaplot.gui.dialogs.chart.chart_data_page import ChartDataPage
from pandaplot.gui.dialogs.chart.chart_labels_page import ChartLabelsPage
from pandaplot.gui.dialogs.chart.chart_no_dataset_page import ChartNoDatasetPage
from pandaplot.gui.dialogs.chart.chart_type_page import ChartTypePage
from pandaplot.models.events.event_types import DatasetEvents
from pandaplot.models.project.items import Dataset
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.theme.theme_manager import ThemeManager


class ChartWizard(PWizard):
    def __init__(
        self,
        app_context: AppContext,
        parent=None,
        initial_dataset_id: Optional[str] = None,
        initial_column_ids: Optional[list[str]] = None,
        initial_title: Optional[str] = None,
        datasets: Optional[list[tuple[str, str]]] = None,
        columns_provider: Optional[Callable[[str], list[tuple[str, str]]]] = None,
        project=None,
    ):
        self._initial_dataset_id = initial_dataset_id
        self._initial_column_ids = initial_column_ids or []
        self._initial_title = initial_title or ""
        self._datasets = datasets or []
        self._columns_provider = columns_provider or (lambda _dataset_id: [])
        self._project = project
        self._is_empty = False
        self._no_dataset_mode = not self._datasets
        super().__init__(app_context=app_context, parent=parent)
        self._initialize()

    def _init_ui(self):
        self.setWindowTitle("Create Chart")
        # Every page here builds 100% of its own visible chrome (step rail,
        # content, footer) and never calls setTitle()/setSubTitle() on any
        # page, so QWizard's native banner/watermark region -- painted with
        # the OS/native palette, not our theme tokens -- is pure dead space.
        # ClassicStyle doesn't reserve that region when no title is set.
        self.setWizardStyle(QWizard.WizardStyle.ClassicStyle)
        for pixmap_role in (
            QWizard.WizardPixmap.WatermarkPixmap,
            QWizard.WizardPixmap.LogoPixmap,
            QWizard.WizardPixmap.BannerPixmap,
            QWizard.WizardPixmap.BackgroundPixmap,
        ):
            self.setPixmap(pixmap_role, QPixmap())
        self.setFixedSize(720, 440)
        self.setButtonLayout([])

        self.type_page = ChartTypePage(app_context=self.app_context)
        self.type_page.emptyRequested.connect(self._finish_empty)
        self._type_page_id = self.addPage(self.type_page)

        self.data_page = ChartDataPage(app_context=self.app_context)
        self.data_page.emptyRequested.connect(self._finish_empty)
        self.data_page.set_datasets(self._datasets)
        self.data_page.set_dataset_columns_provider(self._columns_provider)
        self._data_page_id = self.addPage(self.data_page)

        self.labels_page = ChartLabelsPage(app_context=self.app_context)
        self._labels_page_id = self.addPage(self.labels_page)

        self.no_dataset_page = ChartNoDatasetPage(app_context=self.app_context)
        self.no_dataset_page.importRequested.connect(self._on_import_requested)
        self.no_dataset_page.emptyRequested.connect(self._finish_empty)
        self._no_dataset_page_id = self.addPage(self.no_dataset_page)

        self.currentIdChanged.connect(self._on_page_changed)
        # QWizard only assigns a currentId (and instantiates page state) once it
        # is shown or restarted; since this wizard is driven headlessly in
        # tests (and may be constructed before `show()`/`exec()`), force that
        # initialization now so `next()`/`currentId()` behave correctly even
        # before the wizard is displayed.
        self.restart()

        for page in (self.type_page, self.data_page, self.labels_page, self.no_dataset_page):
            page.step_rail.stepClicked.connect(self._jump_to_step)

    def _jump_to_step(self, step_index: int) -> None:
        page_id = {0: self._type_page_id, 1: self._data_page_id, 2: self._labels_page_id}[step_index]
        self.setCurrentId(page_id)

    def _apply_theme(self):
        # Qt stylesheets cascade to descendants by default, so setting this on
        # the wizard itself themes both pages (ChartTypePage's type list,
        # ChartDataPage's SeriesConfigCard combos/buttons/checkboxes) without
        # needing per-page stylesheets.
        theme_manager = self.app_context.get_manager(ThemeManager)
        palette = theme_manager.get_surface_palette()

        card_bg = palette.get("card_bg", "#f8f9fa")
        card_border = palette.get("card_border", "#dee2e6")
        base_fg = palette.get("base_fg", "#000000")
        secondary_fg = palette.get("secondary_fg", "#555555")
        accent = palette.get("accent", "#4A90E2")
        # Inputs sit one shade off the surface so fields read as distinct wells.
        input_bg = palette.get("card_hover", "#e9ecef")

        self.setStyleSheet(f"""
            QWizard, QDialog {{
                background-color: {card_bg};
                color: {base_fg};
            }}
            QWizardPage {{
                background-color: {card_bg};
                color: {base_fg};
            }}
            QLabel, QCheckBox {{
                color: {base_fg};
            }}
            QCheckBox::indicator {{
                width: 14px;
                height: 14px;
                border: 1px solid {card_border};
                border-radius: 3px;
                background-color: {input_bg};
            }}
            QCheckBox::indicator:checked {{
                background-color: {accent};
                border-color: {accent};
            }}
            QLineEdit, QSpinBox, QComboBox {{
                background-color: {input_bg};
                border: 1px solid {card_border};
                border-radius: 4px;
                padding: 4px 8px;
                min-height: 22px;
                color: {base_fg};
            }}
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
                border-color: {accent};
            }}
            QLineEdit:hover, QSpinBox:hover, QComboBox:hover {{
                border-color: {accent};
            }}
            QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled {{
                color: {secondary_fg};
                background-color: {card_bg};
                border-color: {card_border};
            }}
            QComboBox QAbstractItemView {{
                background-color: {input_bg};
                color: {base_fg};
                border: 1px solid {card_border};
                border-radius: 4px;
                outline: none;
                padding: 2px;
                selection-background-color: {accent};
                selection-color: white;
            }}
            QListWidget {{
                background-color: {input_bg};
                border: 1px solid {card_border};
                border-radius: 4px;
                color: {base_fg};
                outline: none;
            }}
            QListWidget::item {{
                padding: 4px 6px;
            }}
            QListWidget::item:selected {{
                background-color: {accent};
                color: white;
            }}
        """)

    def _on_page_changed(self, page_id: int) -> None:
        if page_id not in (
            self._type_page_id, self._data_page_id, self._labels_page_id, self._no_dataset_page_id,
        ):
            # QWizard's internal reset() (Cancel/Esc/window-close) emits
            # currentIdChanged(-1); there's no page to sync the rail to.
            return
        summaries = self._completed_step_summaries()
        current_index = {
            self._type_page_id: 0,
            self._data_page_id: 1,
            self._no_dataset_page_id: 1,
            self._labels_page_id: 2,
        }[page_id]
        for page in (self.type_page, self.data_page, self.labels_page, self.no_dataset_page):
            page.step_rail.set_state(current_index, summaries)

        if page_id == self._data_page_id:
            rebuilt = self.data_page.set_chart_type(self.type_page.selected_chart_type() or "line")
            # Only re-apply on a genuine rebuild: a fresh card set has no user
            # edits to clobber, whereas revisiting the page with the same chart
            # type must leave whatever the user configured untouched.
            if rebuilt:
                self._apply_initial_selection()
        elif page_id == self._labels_page_id:
            self._seed_labels_defaults()

    def _completed_step_summaries(self) -> dict[int, str]:
        """Rail text for steps already completed, keyed by step index (0/1/2)."""
        summaries: dict[int, str] = {}
        chart_type = self.type_page.selected_chart_type()
        if chart_type:
            from pandaplot.models.chart.chart_type_spec import get_chart_type_spec
            summaries[0] = f"Type · {get_chart_type_spec(chart_type).display_name}"
        if self.data_page.cards:
            count = len(self.data_page.cards)
            summaries[1] = f"Data · {count} series"
        return summaries

    def _seed_labels_defaults(self) -> None:
        x_label = ""
        y_label = ""
        if self.data_page.cards:
            names = self.data_page.cards[0].get_display_names()
            if self.get_chart_type() == "hist":
                # A histogram plots the binned "Values" column along X; Y is
                # frequency/count, which nothing here can suggest a name for.
                x_label = names.get("values", "")
            else:
                x_label = names.get("x", "")
                y_label = names.get("y", "")
        self.labels_page.set_defaults(self._initial_title, x_label, y_label)
        self.labels_page.refresh_preview(self._project, self.get_chart_type(), self.data_page.series_configs())

    def _apply_initial_selection(self) -> None:
        if not self._initial_dataset_id or not self.data_page.cards:
            return
        card = self.data_page.cards[0]
        dataset_index = card.dataset_combo.findData(self._initial_dataset_id)
        if dataset_index >= 0:
            card.dataset_combo.setCurrentIndex(dataset_index)
        self.data_page._refresh_card_columns(card)
        column_ids = self._initial_column_ids
        roles = [role for role in ("x", "y") if role in card._role_combos] or ["values"]
        if len(column_ids) == 1:
            card.apply_picked_columns("y" if "y" in card._role_combos else "values", column_ids)
        else:
            for role, column_id in zip(roles, column_ids, strict=False):
                card.apply_picked_columns(role, [column_id])
        # The initial selection stays available for the wizard's lifetime so it
        # can be re-applied whenever a fresh card set is built (e.g. the user
        # goes Back, changes the chart type, and comes forward again).

    @override
    def setup_event_subscriptions(self):
        self.subscribe_to_event(DatasetEvents.DATASET_CREATED, self._on_dataset_created)

    def _on_import_requested(self) -> None:
        from pandaplot.commands.project.dataset.import_data_command import ImportDataCommand

        command = ImportDataCommand(self.app_context)
        self.app_context.get_command_executor().execute_command(command)

    def _is_active_on_no_dataset_page(self) -> bool:
        # QWizard's internal reset() (Cancel/Esc/window-close) resets currentId
        # to -1, and accept() (e.g. "Create Empty Chart") leaves currentId
        # unchanged but sets result() to Accepted -- either means this wizard
        # is closed/finished and no longer the active recipient of import
        # events. Comparing currentId() to the no-dataset page also means a
        # DATASET_CREATED that arrives after the wizard has moved on to the
        # Data page (or backed up past it) is ignored, and -- since it isn't
        # gated on "has any import ever succeeded" -- a second import started
        # after backing up to this page is not silently swallowed either.
        if self.result() == QDialog.DialogCode.Accepted:
            return False
        return self.currentId() == self._no_dataset_page_id

    def _on_dataset_created(self, event_data: dict) -> None:
        if not self._is_active_on_no_dataset_page():
            return
        self._no_dataset_mode = False
        if self._initial_dataset_id is None:
            self._initial_dataset_id = event_data.get("dataset_id")
        # Defer to the next event-loop turn: a multi-sheet Excel import emits
        # one DATASET_CREATED per sheet, synchronously, in a loop that adds
        # each dataset to the project before emitting for it. Reacting to the
        # *first* event immediately would only see that one sheet's dataset;
        # deferring lets the whole loop finish so every sheet is visible by
        # the time the Data page's dataset options are computed.
        QTimer.singleShot(0, self._advance_after_import)

    def _advance_after_import(self) -> None:
        if not self._is_active_on_no_dataset_page():
            return
        self.data_page.set_datasets(self._current_dataset_options())
        self.data_page.set_dataset_columns_provider(self._current_columns_provider())
        self.next()

    def _current_dataset_options(self) -> list[tuple[str, str]]:
        if self._project is None:
            return []
        return [(item.id, item.name) for item in self._project.get_all_items() if isinstance(item, Dataset)]

    def _current_columns_provider(self) -> Callable[[str], list[tuple[str, str]]]:
        def provider(dataset_id: str) -> list[tuple[str, str]]:
            if self._project is None:
                return []
            dataset = self._project.find_item(dataset_id)
            if not isinstance(dataset, Dataset) or dataset.data is None:
                return []
            return [(dataset.column_id(name) or "", name) for name in dataset.data.columns]
        return provider

    def _finish_empty(self) -> None:
        self._is_empty = True
        self.accept()

    def get_chart_type(self) -> str:
        return self.type_page.selected_chart_type() or "line"

    def is_empty(self) -> bool:
        return self._is_empty

    def get_series_configs(self) -> list[dict]:
        if self._is_empty:
            return []
        return self.data_page.series_configs()

    def get_title(self) -> str:
        if self._is_empty:
            return ""
        return self.labels_page.get_title()

    def get_subtitle(self) -> str:
        if self._is_empty:
            return ""
        return self.labels_page.get_subtitle()

    def get_x_label(self) -> str:
        if self._is_empty:
            return ""
        return self.labels_page.get_x_label()

    def get_y_label(self) -> str:
        if self._is_empty:
            return ""
        return self.labels_page.get_y_label()

    def get_show_legend(self) -> bool:
        if self._is_empty:
            return True
        return self.labels_page.get_show_legend()

    def get_show_grid(self) -> bool:
        if self._is_empty:
            return True
        return self.labels_page.get_show_grid()

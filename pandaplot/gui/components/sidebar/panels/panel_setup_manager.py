import logging

from PySide6.QtWidgets import QWidget

from pandaplot.gui.components.sidebar import CollapsibleSidebar
from pandaplot.gui.components.sidebar.analysis.analysis_panel import AnalysisPanel
from pandaplot.gui.components.sidebar.chart.chart_properties_panel import (
    ChartPropertiesPanel,
)
from pandaplot.gui.components.sidebar.fit.fit_panel import FitPanel
from pandaplot.gui.components.sidebar.panels.conditional_panel_manager import (
    ConditionalPanelManager,
)
from pandaplot.gui.components.sidebar.panels.panel_conditions import (
    is_chart_tab_active,
    is_dataset_tab_active,
)
from pandaplot.gui.components.sidebar.project.project_view_panel import ProjectViewPanel
from pandaplot.gui.components.sidebar.transform.transform_panel import TransformPanel
from pandaplot.models.state.app_context import AppContext


class PanelSetupManager:
    def __init__(self, app_context: AppContext):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.app_context = app_context
        self.panels: list[dict] = []

    def register_default_panels(self):
        # TODO: this should happen differently as it ideally should be driven 
        # by app registration and support plugin architecture with 
        # distributed panel registration
        self.register_panel(ProjectViewPanel(app_context=self.app_context), "explorer", "📁", lambda _: True)
        self.register_panel(TransformPanel(self.app_context), "transform", "🔧", is_dataset_tab_active)

        self.register_panel(AnalysisPanel(self.app_context), "analysis", "📊", is_dataset_tab_active)
        self.register_panel(ChartPropertiesPanel(self.app_context), "chart_properties", "📈", is_chart_tab_active)
        self.register_panel(FitPanel(self.app_context), "fit", "📐", is_chart_tab_active)

    def register_panel(self, panel: QWidget, name: str, icon: str, visibility_condition):
        self.logger.info("Registered panel: %s", name)
        self.panels.append({
            "panel": panel,
            "name": name,
            "icon": icon,
            "visibility_condition": visibility_condition
        })

    def add_panels(self, sidebar: CollapsibleSidebar, panel_manager:ConditionalPanelManager):
        for priority, panel_info in enumerate(self.panels):
            sidebar.add_panel(panel_info["name"], panel_info["icon"], panel_info["panel"])
            panel_manager.register_conditional_panel(panel_info["name"], panel_info["visibility_condition"], priority)
        panel_manager.evaluate_panel_visibility()
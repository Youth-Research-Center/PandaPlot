import datetime
import os
from pathlib import Path
from typing import override

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pandaplot.gui.core.widget_extension import PWidget
from pandaplot.models.events.event_types import ConfigEvents
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.config.config_manager import ConfigManager
from pandaplot.services.theme.theme_manager import ThemeManager

    
class WelcomeTab(PWidget):
    """
    Welcome tab widget similar to VS Code's welcome screen.
    Shows recent projects, quick actions, and getting started information.
    """
    # Signals (still using Qt signals; planned for event bus replacement)
    new_project_requested = Signal()
    open_project_requested = Signal()
    recent_project_selected = Signal(str)  # project file path
    import_data_requested = Signal()  # importing data

    def __init__(self, app_context:AppContext, parent:QWidget):
        super().__init__(app_context=app_context, parent=parent)
        # Object name for scoped styling (border reset)
        self.setObjectName("WelcomeTabRoot")
        self._initialize()
        self.update_recent_projects()

    def setup_event_subscriptions(self):
        self.subscribe_to_event(ConfigEvents.CONFIG_UPDATED, self._on_config_event)

    def _on_config_event(self, _evt: dict):  # event data unused currently
        """Handle config lifecycle events by refreshing recent projects list."""
        try:
            self.update_recent_projects()
        except Exception as e:  # noqa: BLE001
            self.logger.warning("Failed updating recent projects on config event: %s", e)

    @override
    def _init_ui(self):
        """Initialize the welcome tab UI."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # Create scroll area for content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        # Allow scroll area to inherit theme background
        scroll_area.setStyleSheet("")

        # Content widget
        content_widget = QWidget()
        # No forced background color here
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(30)

        # Header section
        self.create_header_section(content_layout)

        # Quick actions section
        self.create_quick_actions_section(content_layout)

        # Recent projects section
        self.create_recent_projects_section(content_layout)

        # Getting started section
        self.create_getting_started_section(content_layout)

        # Add stretch at the bottom
        content_layout.addStretch()

        # Set content widget to scroll area
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)

    @override
    def _apply_theme(self):
        """Build and apply a local (scoped) stylesheet using ThemeManager palette.

        This keeps WelcomeTab styling self-contained while sourcing colors from
        ThemeManager, avoiding global stylesheet bloat.
        """
        try:
            tm = self.app_context.get_manager(ThemeManager)
            palette = tm.get_surface_palette()
            card_bg = palette["card_bg"]
            card_hover = palette["card_hover"]
            card_pressed = palette["card_pressed"]
            card_border = palette["card_border"]
            base_fg = palette["base_fg"]
            secondary_fg = palette["secondary_fg"]
            accent = palette["accent"]

            # Scoped QSS (only applies within this tab widget)
            qss = f"""
                QWidget {{
                    border: 0px;
                    background: transparent; /* allow window palette to show */
                    color: {base_fg};
                }}
                QWidget#WelcomeTabRoot QLabel[secondary="true"] {{
                    color: {secondary_fg};
                }}
                QWidget#WelcomeTabRoot QLabel#accentIcon {{
                    color: {accent};
                }}
                /* Card style buttons */
                QWidget#WelcomeTabRoot #WelcomeCardButton,
                QWidget#WelcomeTabRoot #WelcomeListButton,
                QWidget#WelcomeTabRoot #WelcomeProjectButton {{
                    background-color: {card_bg};
                    border: 1px solid {card_border};
                    border-radius: 8px;
                    /* Provide vertical padding so larger fonts aren't clipped */
                    padding: 6px 0;
                    color: {base_fg};
                    text-align: left;
                }}
                QWidget#WelcomeTabRoot #WelcomeCardButton:hover,
                QWidget#WelcomeTabRoot #WelcomeListButton:hover,
                QWidget#WelcomeTabRoot #WelcomeProjectButton:hover {{
                    background-color: {card_hover};
                    border-color: {accent};
                }}
                QWidget#WelcomeTabRoot #WelcomeCardButton:pressed,
                QWidget#WelcomeTabRoot #WelcomeListButton:pressed,
                QWidget#WelcomeTabRoot #WelcomeProjectButton:pressed {{
                    background-color: {card_pressed};
                }}
                QWidget#WelcomeTabRoot #WelcomeCardButton QLabel,
                QWidget#WelcomeTabRoot #WelcomeListButton QLabel,
                QWidget#WelcomeTabRoot #WelcomeProjectButton QLabel {{
                    background: transparent;
                    border: 0px;
                    outline: none;
                    padding: 0px;
                }}
                /* Ensure no stray borders on any labels in this tab */
                QWidget#WelcomeTabRoot QLabel {{ border: 0px; }}
                /* Primary (non-secondary) text inside cards */
                QWidget#WelcomeTabRoot #WelcomeCardButton QLabel:not([secondary="true"]),
                QWidget#WelcomeTabRoot #WelcomeListButton QLabel:not([secondary="true"]),
                QWidget#WelcomeTabRoot #WelcomeProjectButton QLabel:not([secondary="true"]) {{
                    color: {base_fg};
                }}
                /* Titles */
                QWidget#WelcomeTabRoot #appTitle {{ color: {base_fg}; }}
                QWidget#WelcomeTabRoot #appSubtitle {{ color: {secondary_fg}; }}
                /* Use QLabel qualifier for higher specificity to override any global label rules */
                QWidget#WelcomeTabRoot QLabel#sectionTitle {{ color: {base_fg}; }}
            """
            self.setStyleSheet(qss)
        except Exception as e:  # noqa: BLE001
            self.logger.warning("Failed building local WelcomeTab stylesheet: %s", e)
    
    def create_header_section(self, layout):
        """Create the header section with app title and description."""
        header_layout = QVBoxLayout()
        header_layout.setSpacing(10)
        
        # App title
        title_label = QLabel("PandaPlot")
        title_label.setObjectName("appTitle")
        title_font = QFont()
        title_font.setPointSize(24)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Margin only; color via theme stylesheet
        title_label.setStyleSheet("margin-bottom: 10px;")
        
        # Subtitle
        subtitle_label = QLabel("Professional Data Visualization & Analysis Tool")
        subtitle_label.setObjectName("appSubtitle")
        subtitle_font = QFont()
        subtitle_font.setPointSize(12)
        subtitle_label.setFont(subtitle_font)
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setStyleSheet("margin-bottom: 20px;")
        
        header_layout.addWidget(title_label)
        header_layout.addWidget(subtitle_label)
        
        layout.addLayout(header_layout)
    
    def create_quick_actions_section(self, layout):
        """Create the quick actions section."""
        # Section title
        title_label = QLabel("Quick Actions")
        title_label.setObjectName("sectionTitle")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        # Margin only; color via theme stylesheet
        title_label.setStyleSheet("margin-bottom: 15px;")
        layout.addWidget(title_label)

        # Actions grid
        actions_layout = QGridLayout()
        actions_layout.setSpacing(20)
        actions_layout.setContentsMargins(0, 0, 0, 20)

        # New Project button
        new_project_btn = self.create_action_button(
            "📊 New Project",
            "Create a new data visualization project",
            self.new_project_requested.emit
        )
        actions_layout.addWidget(new_project_btn, 0, 0)

        # Open Project button
        open_project_btn = self.create_action_button(
            "📂 Open Project",
            "Open an existing project file",
            self.open_project_requested.emit
        )
        actions_layout.addWidget(open_project_btn, 0, 1)

        # Import Data button
        import_data_btn = self.create_action_button(
            "📈 Import Data",
            "Import CSV or Excel data files",
            self.import_data_requested.emit
        )
        actions_layout.addWidget(import_data_btn, 1, 0)

        # Examples button
        examples_btn = self.create_action_button(
            "📚 Examples",
            "Browse sample projects and tutorials",
            lambda: self.logger.info("Examples action triggered")  # TODO: Implement
        )
        actions_layout.addWidget(examples_btn, 1, 1)

        layout.addLayout(actions_layout)
    
    def create_recent_projects_section(self, layout):
        """Create the recent projects section."""
        # Section title
        title_label = QLabel("Recent Projects")
        title_label.setObjectName("sectionTitle")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("margin-bottom: 15px;")
        layout.addWidget(title_label)
        
        # Recent projects will be populated dynamically
        self.recent_projects_layout = QVBoxLayout()
        self.recent_projects_layout.setContentsMargins(0, 0, 0, 20)
        # Add a bit more spacing so each item breathes vertically
        self.recent_projects_layout.setSpacing(12)
        layout.addLayout(self.recent_projects_layout)
        
        # Update recent projects
        self.update_recent_projects()
    
    def create_getting_started_section(self, layout):
        """Create the getting started section."""
        # Section title
        title_label = QLabel("Getting Started")
        title_label.setObjectName("sectionTitle")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("margin-bottom: 15px;")
        layout.addWidget(title_label)
        
        # Getting started content
        content_layout = QVBoxLayout()
        content_layout.setSpacing(8)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        # Step items
        steps = [
            ("1. Create or Open a Project", "Start by creating a new project or opening an existing one"),
            ("2. Import Your Data", "Import CSV, Excel, or other data files into your project"),
            ("3. Explore Data", "Use the data view to examine and understand your dataset"),
            ("4. Create Visualizations", "Generate charts and plots from your data"),
            ("5. Customize and Export", "Customize your plots and export them for presentations")
        ]
        
        for step_title, step_desc in steps:
            step_widget = self.create_step_item(step_title, step_desc)
            content_layout.addWidget(step_widget)
        
        layout.addLayout(content_layout)
    
    def create_action_button(self, title, description, callback):
        """Create a styled action button."""
        button = QPushButton()
        button.setMinimumHeight(100)
        button.setMinimumWidth(220)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setObjectName("WelcomeCardButton")
        
        # Create layout for button content
        button_layout = QVBoxLayout(button)
        button_layout.setContentsMargins(20, 15, 20, 15)
        button_layout.setSpacing(8)
        
        # Title label
        title_label = QLabel(title)
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(11)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Color handled by theme stylesheet
        title_label.setStyleSheet("")
        title_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)  # Prevent text selection

        # Description label
        desc_label = QLabel(description)
        desc_font = QFont()
        desc_font.setPointSize(9)
        desc_label.setFont(desc_font)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setWordWrap(True)
        # Mark as secondary text for theming
        desc_label.setProperty("secondary", True)
        desc_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)  # Prevent text selection
        
        button_layout.addWidget(title_label)
        button_layout.addWidget(desc_label)
        # No inline stylesheet; themed globally
        
        # Connect callback
        button.clicked.connect(callback)
        
        return button
    
    def create_step_item(self, title, description):
        """Create a step item for the getting started section."""
        button = QPushButton()
        button.setMinimumHeight(65)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setObjectName("WelcomeListButton")
        
        # Create layout for button content
        button_layout = QVBoxLayout(button)
        button_layout.setContentsMargins(20, 12, 20, 12)
        button_layout.setSpacing(4)
        
        # Title
        title_label = QLabel(title)
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(10)
        title_label.setFont(title_font)
        # primary text inherits
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        title_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)  # Prevent text selection
        
        # Description
        desc_label = QLabel(description)
        desc_font = QFont()
        desc_font.setPointSize(9)
        desc_label.setFont(desc_font)
        desc_label.setProperty("secondary", True)
        desc_label.setWordWrap(True)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        desc_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)  # Prevent text selection
        
        button_layout.addWidget(title_label)
        button_layout.addWidget(desc_label)
        # No inline stylesheet; themed globally
        # Connect to a placeholder action (logging only)
        button.clicked.connect(lambda: self.logger.info("Getting started step clicked: %s", title)) #TODO: not implemented
        return button
    
    def create_recent_project_item(self, project_name, project_path, last_opened):
        """Create a recent project item."""
        button = QPushButton()
        # Increase height for more vertical space for name line and new spacing
        button.setMinimumHeight(96)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setObjectName("WelcomeProjectButton")

        # Create layout for button content
        button_layout = QHBoxLayout(button)
        # Top/bottom padding
        button_layout.setContentsMargins(20, 18, 20, 18)

        # Project info layout (vertical stack)
        info_layout = QVBoxLayout()
        # Wider spacing so name->path gap is clear (user request)
        info_layout.setSpacing(12)

        # Project name (flush left relative to button content area)
        name_label = QLabel(project_name)
        name_font = QFont()
        name_font.setBold(True)
        name_font.setPointSize(11)
        name_label.setFont(name_font)
        name_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        name_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        # Ensure vertical room for descenders
        fm = name_label.fontMetrics()
        required_h = fm.height() + fm.descent() + 6
        name_label.setMinimumHeight(required_h)
        # Only vertical padding; no left padding so it sits as far left as possible
        name_label.setStyleSheet("padding:2px 0 4px 0;")

        # Project path (optionally slightly indented to the right)
        path_label = QLabel(project_path)
        path_font = QFont()
        path_font.setPointSize(8)
        path_label.setFont(path_font)
        path_label.setProperty("secondary", True)
        path_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        # Provide minimal left indent to visually separate while keeping nearly aligned
        path_label.setStyleSheet("min-height:14px; padding-left:2px;")

        # Last opened label (kept aligned with path)
        last_opened_label = QLabel(f"Last opened: {last_opened}")
        last_opened_label.setFont(path_font)
        last_opened_label.setProperty("secondary", True)
        last_opened_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        last_opened_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        last_opened_label.setStyleSheet("min-height:14px; padding-left:2px;")

        info_layout.addWidget(name_label)
        info_layout.addWidget(path_label)
        info_layout.addWidget(last_opened_label)

        button_layout.addLayout(info_layout)
        button_layout.addStretch()

        # Project type icon
        icon_label = QLabel("📊")
        icon_label.setStyleSheet("font-size: 20px;")
        icon_label.setProperty("accentIcon", True)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        button_layout.addWidget(icon_label)

        # Connect to the signal
        button.clicked.connect(lambda: self.recent_project_selected.emit(project_path))

        return button
    
    def update_recent_projects(self):
        """Update the recent projects list."""
        # TODO: this probably shouldn't be here, but somewhere else as we can update it in multiple places
        if not hasattr(self, "recent_projects_layout"):
            return

        recent_projects = self.get_recent_projects()

        # Dedupe by path while preserving order
        seen = set()
        deduped = []
        for rp in recent_projects:
            p = rp.get("path")
            if not p or p in seen:
                continue
            seen.add(p)
            deduped.append(rp)

        # Optimization: build a signature of current displayed paths to skip unnecessary re-render
        current_paths = []
        for i in range(self.recent_projects_layout.count()):
            w = self.recent_projects_layout.itemAt(i).widget()
            if not w:
                continue
            # Heuristic: second QLabel inside the button layout holds the path (see create_recent_project_item)
            labels = w.findChildren(QLabel)
            if len(labels) >= 2:
                path_text = labels[1].text()
                current_paths.append(path_text)

        desired_paths = [rp.get("path","") for rp in deduped[:5]] if deduped else []
        if current_paths == desired_paths:
            return  # No change

        # Clear existing items safely
        for i in reversed(range(self.recent_projects_layout.count())):
            child = self.recent_projects_layout.itemAt(i).widget()
            if child:
                child.setParent(None)

        if not deduped:
            placeholder = QLabel("No recent projects")
            placeholder.setStyleSheet("font-style: italic; padding: 20px;")
            placeholder.setProperty("secondary", True)
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
            self.recent_projects_layout.addWidget(placeholder)
            return

        for project_info in deduped[:5]:
            project_item = self.create_recent_project_item(
                project_info.get("name", "Untitled Project"),
                project_info.get("path", ""),
                project_info.get("last_opened", "Unknown")
            )
            self.recent_projects_layout.addWidget(project_item)
    
    def get_recent_projects(self):
        """Return a list of recent projects from app configuration.

        Expected config structure (if present):
            app_context.get_app_state().config.recent_projects -> List[str]
        Falls back to empty list if unavailable.
        Each returned entry is dict: { name, path, last_opened }
        """
        # TODO: this shouldn't be here as we might need recent projects in multiple places
        try:
            if not self.app_context:
                return []
            # Prefer ConfigManager (source of truth) instead of AppState (which currently has no config attr)
            cfg_manager = self.app_context.get_manager(ConfigManager)
            cfg = cfg_manager.config
            if not cfg:
                return []
            recent_paths = cfg.recent_projects
            if not recent_paths:
                return []
            results = []
            for p in recent_paths:
                if not p:
                    continue
                try:
                    path_obj = Path(p)
                    if not path_obj.exists():
                        continue
                    name = path_obj.stem
                    # Use file modified time as last_opened fallback
                    ts = os.path.getmtime(p)
                    last_opened = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
                    results.append({
                        "name": name,
                        "path": str(path_obj),
                        "last_opened": last_opened
                    })
                except Exception:
                    continue
            # Sort newest first by last_opened timestamp string descending
            results.sort(key=lambda x: x["last_opened"], reverse=True)
            return results
        except Exception as e:
            self.logger.warning("Failed to load recent projects: %s", e)
            return []
    
    def get_tab_title(self):
        """Get the title for this tab."""
        return "🏠 Welcome"

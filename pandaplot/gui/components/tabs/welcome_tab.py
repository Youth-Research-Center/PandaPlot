from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                             QScrollArea, QFrame, QGridLayout, QSizePolicy)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
import logging


class WelcomeTab(QWidget):
    """
    Welcome tab widget similar to VS Code's welcome screen.
    Shows recent projects, quick actions, and getting started information.
    """
    
    # Signals
    # TODO: remove reliance on signals
    new_project_requested = Signal()
    open_project_requested = Signal()
    recent_project_selected = Signal(str)  # project file path
    import_data_requested = Signal()  # Signal for importing data
    
    def __init__(self, app_context=None, parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.logger = logging.getLogger(__name__)
        self.setup_ui()
    
    def setup_ui(self):
        """Initialize the welcome tab UI."""
        # Set overall background color
        self.setStyleSheet("""QWidget { background-color: #ffffff; border: 0px;}
                           """)
        
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
        scroll_area.setStyleSheet("QScrollArea { background-color: #ffffff; }")
        
        # Content widget
        content_widget = QWidget()
        content_widget.setStyleSheet("QWidget { background-color: #ffffff;}")
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
    
    def create_header_section(self, layout):
        """Create the header section with app title and description."""
        header_layout = QVBoxLayout()
        header_layout.setSpacing(10)
        
        # App title
        title_label = QLabel("PandaPlot")
        title_font = QFont()
        title_font.setPointSize(24)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("color: #333333; margin-bottom: 10px;")
        
        # Subtitle
        subtitle_label = QLabel("Professional Data Visualization & Analysis Tool")
        subtitle_font = QFont()
        subtitle_font.setPointSize(12)
        subtitle_label.setFont(subtitle_font)
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setStyleSheet("color: #666666; margin-bottom: 20px;")
        
        header_layout.addWidget(title_label)
        header_layout.addWidget(subtitle_label)
        
        layout.addLayout(header_layout)
    
    def create_quick_actions_section(self, layout):
        """Create the quick actions section."""
        # Section title
        title_label = QLabel("Quick Actions")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #333333; margin-bottom: 15px;")
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
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #333333; margin-bottom: 15px;")
        layout.addWidget(title_label)
        
        # Recent projects will be populated dynamically
        self.recent_projects_layout = QVBoxLayout()
        self.recent_projects_layout.setContentsMargins(0, 0, 0, 20)
        layout.addLayout(self.recent_projects_layout)
        
        # Update recent projects
        self.update_recent_projects()
    
    def create_getting_started_section(self, layout):
        """Create the getting started section."""
        # Section title
        title_label = QLabel("Getting Started")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #333333; margin-bottom: 15px;")
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
        title_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)  # Prevent text selection

        # Description label
        desc_label = QLabel(description)
        desc_font = QFont()
        desc_font.setPointSize(9)
        desc_label.setFont(desc_font)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666666;")
        desc_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)  # Prevent text selection
        
        button_layout.addWidget(title_label)
        button_layout.addWidget(desc_label)
        
        # Cleaner styling
        button.setStyleSheet("""
            QPushButton {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                text-align: center;
            }
            QPushButton:hover {
                background-color: #e9ecef;
                border-color: #007bff;
            }
            QPushButton:pressed {
                background-color: #dee2e6;
                border-color: #0056b3;
            }
            QLabel {
                background-color: transparent;
            }
        """)
        
        # Connect callback
        button.clicked.connect(callback)
        
        return button
    
    def create_step_item(self, title, description):
        """Create a step item for the getting started section."""
        button = QPushButton()
        button.setMinimumHeight(65)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        
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
        title_label.setStyleSheet("color: #333333;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        title_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)  # Prevent text selection
        
        # Description
        desc_label = QLabel(description)
        desc_font = QFont()
        desc_font.setPointSize(9)
        desc_label.setFont(desc_font)
        desc_label.setStyleSheet("color: #666666;")
        desc_label.setWordWrap(True)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        desc_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)  # Prevent text selection
        
        button_layout.addWidget(title_label)
        button_layout.addWidget(desc_label)
        
        # Consistent styling with action buttons
        button.setStyleSheet("""
            QPushButton {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #e9ecef;
                border-color: #007bff;
            }
            QPushButton:pressed {
                background-color: #dee2e6;
                border-color: #0056b3;
            }
                             QLabel {
                background-color: transparent;
            }
        """)
        # Connect to a placeholder action (logging only)
        button.clicked.connect(lambda: self.logger.info("Getting started step clicked: %s", title)) #TODO: not implemented
        return button
    
    def create_recent_project_item(self, project_name, project_path, last_opened):
        """Create a recent project item."""
        button = QPushButton()
        button.setMinimumHeight(75)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Create layout for button content
        button_layout = QHBoxLayout(button)
        button_layout.setContentsMargins(20, 15, 20, 15)
        
        # Project info layout
        info_layout = QVBoxLayout()
        info_layout.setSpacing(3)
        
        # Project name
        name_label = QLabel(project_name)
        name_font = QFont()
        name_font.setBold(True)
        name_font.setPointSize(10)
        name_label.setFont(name_font)
        name_label.setStyleSheet("color: #333333;")
        name_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        name_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)  # Prevent text selection
        
        # Project path
        path_label = QLabel(project_path)
        path_font = QFont()
        path_font.setPointSize(8)
        path_label.setFont(path_font)
        path_label.setStyleSheet("color: #666666;")
        path_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)  # Prevent text selection
        
        # Last opened
        last_opened_label = QLabel(f"Last opened: {last_opened}")
        last_opened_label.setFont(path_font)
        last_opened_label.setStyleSheet("color: #999999;")
        last_opened_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        last_opened_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)  # Prevent text selection
        
        info_layout.addWidget(name_label)
        info_layout.addWidget(path_label)
        info_layout.addWidget(last_opened_label)
        
        button_layout.addLayout(info_layout)
        button_layout.addStretch()
        
        # Project type icon
        icon_label = QLabel("📊")
        icon_label.setStyleSheet("font-size: 20px; color: #007bff;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)  # Prevent text selection
        button_layout.addWidget(icon_label)
        
        # Consistent styling with other buttons
        button.setStyleSheet("""
            QPushButton {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #e9ecef;
                border-color: #007bff;
            }
            QPushButton:pressed {
                background-color: #dee2e6;
                border-color: #0056b3;
            }
        """)
        
        # Connect to the signal
        button.clicked.connect(lambda: self.recent_project_selected.emit(project_path))
        
        return button
    
    def update_recent_projects(self):
        """Update the recent projects list."""
        # Clear existing items
        for i in reversed(range(self.recent_projects_layout.count())):
            child = self.recent_projects_layout.itemAt(i).widget()
            if child:
                child.setParent(None)
        
        # Get recent projects from app context or settings
        recent_projects = self.get_recent_projects()
        
        if not recent_projects:
            # Show placeholder
            placeholder = QLabel("No recent projects")
            placeholder.setStyleSheet("color: #999999; font-style: italic; padding: 20px;")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)  # Prevent text selection
            self.recent_projects_layout.addWidget(placeholder)
        else:
            # Add recent project items
            for project_info in recent_projects[:5]:  # Show max 5 recent projects
                project_item = self.create_recent_project_item(
                    project_info.get('name', 'Untitled Project'),
                    project_info.get('path', ''),
                    project_info.get('last_opened', 'Unknown')
                )
                self.recent_projects_layout.addWidget(project_item)
    
    def get_recent_projects(self):
        """Get recent projects list. This should be implemented to read from settings."""
        # TODO: Implement reading from settings/app context
        # For now, return empty list
        return []
    
    def get_tab_title(self):
        """Get the title for this tab."""
        return "🏠 Welcome"

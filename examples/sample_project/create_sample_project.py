"""
Example script showing how to use the new project structure system.
"""

import pandas as pd
import numpy as np
import os
import sys

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


from pandaplot.models.project.project import Project
from pandaplot.models.project.items.folder import Folder
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.project.items.note import Note
from pandaplot.storage.project_data_manager import ProjectDataManager
from pandaplot.storage.item_data_manager_factory import ItemDataManagerFactory
from pandaplot.storage.note_data_manager import NoteDataManager
from pandaplot.storage.folder_data_manager import FolderDataManager
from pandaplot.storage.chart_data_manager import ChartDataManager
from pandaplot.storage.dataset_data_manager import DatasetDataManager


def create_project_data_manager() -> ProjectDataManager:
    """Create and configure the project data manager."""
    item_data_manager_factory = ItemDataManagerFactory()

    item_data_manager_factory.register(
        type_name="note",
        item_class=Note,
        manager=NoteDataManager(),
        extension="note"
    )

    item_data_manager_factory.register(
        type_name="folder",
        item_class=Folder,
        manager=FolderDataManager(),
        extension="folder"
    )

    item_data_manager_factory.register(
        type_name="chart",
        item_class=Chart,
        manager=ChartDataManager(),
        extension="chart"
    )

    item_data_manager_factory.register(
        type_name="dataset",
        item_class=Dataset,
        manager=DatasetDataManager(),
        extension="dataset"
    )

    project_data_manager = ProjectDataManager(item_data_manager_factory)
    return project_data_manager


def create_sample_project():
    """Create a sample project with multiple datasets, charts, and notes."""
    
    # Create project and data manager
    project = Project(name="Sales Analysis Project", description="Sample sales data analysis")
    project_data_manager = create_project_data_manager()
    
    # Create folder structure
    data_folder = Folder(name="Raw Data")
    analysis_folder = Folder(name="Analysis")
    reports_folder = Folder(name="Reports")
    
    project.add_item(data_folder)
    project.add_item(analysis_folder)
    project.add_item(reports_folder)
    
    # Create sample data
    # Monthly Sales data
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun']
    sales_data = pd.DataFrame({
        'Month': months,
        'Sales': [12000, 15000, 13500, 16800, 18200, 21000],
        'Units': [120, 150, 135, 168, 182, 210],
        'Returns': [240, 300, 270, 336, 364, 420]
    })
    
    # Customer data
    customer_data = pd.DataFrame({
        'Customer_ID': range(1, 101),
        'Age': np.random.randint(18, 65, 100),
        'Purchase_Amount': np.random.normal(500, 150, 100),
        'Satisfaction': np.random.randint(1, 6, 100)
    })
    
    # Create datasets
    sales_dataset = Dataset(name="Monthly Sales", data=sales_data)
    customer_dataset = Dataset(name="Customer Data", data=customer_data)
    
    project.add_item(sales_dataset, data_folder.id)
    project.add_item(customer_dataset, data_folder.id)
    
    # Create charts
    sales_chart = Chart(name="Sales Trend", chart_type="line")
    # Note: Chart configuration would be handled differently in the new system
    # For now, we just create the basic chart structure
    
    customer_chart = Chart(name="Customer Distribution", chart_type="histogram")
    
    project.add_item(sales_chart, analysis_folder.id)
    project.add_item(customer_chart, analysis_folder.id)
    
    # Create notes
    analysis_note = Note(name="Analysis Summary")
    analysis_content = """# Sales Analysis Summary

## Key Findings:
- Monthly sales show steady growth from January to June
- Total sales increased by 75% over the 6-month period
- Customer satisfaction averages 3.0/5.0
- Strong correlation between units sold and total sales

## Recommendations:
1. Continue current marketing strategy
2. Focus on customer satisfaction improvement
3. Analyze seasonal trends for better forecasting
"""
    analysis_note.content = analysis_content
    
    methodology_note = Note(name="Methodology")
    methodology_content = """# Analysis Methodology

## Data Sources:
- Monthly sales reports (Jan-Jun 2023)
- Customer satisfaction surveys
- Unit sales tracking system

## Analysis Techniques:
- Time series analysis for sales trends
- Statistical distribution analysis for customer data
- Correlation analysis between variables

## Tools Used:
- PandaPlot for visualization
- Pandas for data manipulation
- NumPy for numerical analysis
"""
    methodology_note.content = methodology_content
    
    project.add_item(analysis_note, reports_folder.id)
    project.add_item(methodology_note, reports_folder.id)
    
    # Save the project
    project_file = os.path.join(os.path.dirname(__file__), "sample_project.pplot")
    project_data_manager.save(project, project_file)
    
    print(f"Sample project created and saved to: {project_file}")
    print("\nProject structure:")
    print_project_structure(project, project.root.id, 0)
    
    return project


def print_project_structure(project, item_id, indent_level):
    """Print the project structure in a tree format."""
    if item_id == project.root.id:
        # Print root
        print(f"📁 {project.name}")
        # Print root children
        for item in project.root.get_items():
            print_project_structure(project, item.id, 1)
    else:
        item = project.find_item(item_id)
        if not item:
            return
        
        indent = "  " * indent_level
        icon = {"folder": "📁", "dataset": "📊", "chart": "📈", "note": "📝"}.get(
            item.__class__.__name__.lower(), "📄"
        )
        
        print(f"{indent}{icon} {item.name}")
        
        # If it's a collection (like Folder), print its children
        if hasattr(item, 'get_items'):
            for child in item.get_items():
                print_project_structure(project, child.id, indent_level + 1)


if __name__ == "__main__":
    create_sample_project()

"""Chart style manager for applying configurations to matplotlib."""

from typing import Tuple

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from .chart_configuration import ChartConfiguration, ChartType, ScaleType


class ChartStyleManager:
    """Manages chart styling and application to matplotlib figures."""
    
    def __init__(self):
        """Initialize the chart style manager."""
        self._color_palette = [
            "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
            "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"
        ]
    
    def apply_configuration(self, figure: Figure, config: ChartConfiguration, 
                          data: pd.DataFrame) -> Axes:
        """Apply chart configuration to a matplotlib figure.
        
        Args:
            figure: The matplotlib figure to configure
            config: The chart configuration to apply
            data: The data to plot
            
        Returns:
            The configured axes object
        """
        # Clear any existing content
        figure.clear()
        
        # Set figure size and background
        figure.set_size_inches(config.figure_size)
        figure.patch.set_facecolor(config.background_color)
        
        # Create axes
        ax = figure.add_subplot(111)
        
        # Apply chart type specific plotting
        self._plot_data(ax, config, data)
        
        # Apply styling
        self._apply_axis_styling(ax, config)
        self._apply_legend_styling(ax, config)
        self._apply_title(ax, config)
        
        # Adjust layout
        figure.tight_layout()
        
        return ax
    
    def _plot_data(self, ax: Axes, config: ChartConfiguration, data: pd.DataFrame):
        """Plot data according to chart type."""
        if config.x_column not in data.columns or config.y_column not in data.columns:
            ax.text(0.5, 0.5, f"Columns '{config.x_column}' or '{config.y_column}' not found",
                   ha="center", va="center", transform=ax.transAxes)
            return
        
        x_data = data[config.x_column]
        y_data = data[config.y_column]
        
        if config.chart_type == ChartType.LINE:
            self._plot_line(ax, x_data, y_data, config)
        elif config.chart_type == ChartType.SCATTER:
            self._plot_scatter(ax, x_data, y_data, config)
        elif config.chart_type == ChartType.BAR:
            self._plot_bar(ax, x_data, y_data, config)
        elif config.chart_type == ChartType.HISTOGRAM:
            self._plot_histogram(ax, y_data, config)
        elif config.chart_type == ChartType.BOX:
            self._plot_box(ax, y_data, config)
        elif config.chart_type == ChartType.VIOLIN:
            self._plot_violin(ax, y_data, config)
    
    def _plot_line(self, ax: Axes, x_data: pd.Series, y_data: pd.Series, 
                   config: ChartConfiguration):
        """Plot line chart."""
        line_kwargs = config.line_style.to_matplotlib_kwargs()
        marker_kwargs = config.marker_style.to_matplotlib_kwargs()
        
        # Combine line and marker kwargs
        plot_kwargs = {**line_kwargs, **marker_kwargs}
        
        ax.plot(x_data, y_data, **plot_kwargs, label=config.y_column)
    
    def _plot_scatter(self, ax: Axes, x_data: pd.Series, y_data: pd.Series, 
                      config: ChartConfiguration):
        """Plot scatter chart."""
        marker_kwargs = config.marker_style.to_matplotlib_kwargs()
        
        # Remove marker key for scatter plot
        scatter_kwargs = marker_kwargs.copy()
        scatter_kwargs["s"] = scatter_kwargs.pop("markersize", 6) ** 2  # Convert to area
        scatter_kwargs["c"] = scatter_kwargs.pop("markerfacecolor", "#1f77b4")
        scatter_kwargs["edgecolors"] = scatter_kwargs.pop("markeredgecolor", "#000000")
        scatter_kwargs["linewidths"] = scatter_kwargs.pop("markeredgewidth", 1.0)
        
        # Remove marker key if present
        scatter_kwargs.pop("marker", None)
        
        ax.scatter(x_data, y_data, **scatter_kwargs, label=config.y_column)
    
    def _plot_bar(self, ax: Axes, x_data: pd.Series, y_data: pd.Series, 
                  config: ChartConfiguration):
        """Plot bar chart."""
        color = config.line_style.color
        transparency = config.line_style.transparency
        
        ax.bar(x_data, y_data, color=color, alpha=transparency, label=config.y_column)
    
    def _plot_histogram(self, ax: Axes, data: pd.Series, config: ChartConfiguration):
        """Plot histogram."""
        color = config.line_style.color
        transparency = config.line_style.transparency
        
        ax.hist(data, bins=30, color=color, alpha=transparency, 
                edgecolor="black", label=config.y_column)
    
    def _plot_box(self, ax: Axes, data: pd.Series, config: ChartConfiguration):
        """Plot box plot."""
        bp = ax.boxplot([data], patch_artist=True)
        ax.set_xticklabels([config.y_column])
        
        # Apply colors
        for patch in bp["boxes"]:
            patch.set_facecolor(config.line_style.color)
            patch.set_alpha(config.line_style.transparency)
    
    def _plot_violin(self, ax: Axes, data: pd.Series, config: ChartConfiguration):
        """Plot violin plot."""
        parts = ax.violinplot([data], positions=[1], showmeans=True, showmedians=True)
        
        # Apply colors
        if "bodies" in parts:
            for pc in parts["bodies"]:
                pc.set_facecolor(config.line_style.color)
                pc.set_alpha(config.line_style.transparency)
        
        ax.set_xticks([1])
        ax.set_xticklabels([config.y_column])
    
    def _apply_axis_styling(self, ax: Axes, config: ChartConfiguration):
        """Apply axis styling to the chart."""
        # X-axis
        if config.x_axis.label:
            ax.set_xlabel(config.x_axis.label, **config.x_axis.to_matplotlib_kwargs())
        
        # Y-axis
        if config.y_axis.label:
            ax.set_ylabel(config.y_axis.label, **config.y_axis.to_matplotlib_kwargs())
        
        # Grid
        if config.x_axis.show_grid or config.y_axis.show_grid:
            ax.grid(True, color=config.x_axis.grid_color, 
                   linestyle=config.x_axis.grid_style.value,
                   alpha=0.7)
        
        # Scales
        if config.x_axis.scale == ScaleType.LOG:
            ax.set_xscale("log")
        if config.y_axis.scale == ScaleType.LOG:
            ax.set_yscale("log")
        
        # Limits
        if not config.x_axis.auto_limits:
            if config.x_axis.min_limit is not None and config.x_axis.max_limit is not None:
                ax.set_xlim(config.x_axis.min_limit, config.x_axis.max_limit)
        
        if not config.y_axis.auto_limits:
            if config.y_axis.min_limit is not None and config.y_axis.max_limit is not None:
                ax.set_ylim(config.y_axis.min_limit, config.y_axis.max_limit)
        
        # Font styling for tick labels
        ax.tick_params(axis="x", labelsize=config.x_axis.font_size, 
                      colors=config.x_axis.color)
        ax.tick_params(axis="y", labelsize=config.y_axis.font_size, 
                      colors=config.y_axis.color)
    
    def _apply_legend_styling(self, ax: Axes, config: ChartConfiguration):
        """Apply legend styling to the chart."""
        if config.legend.show:
            legend_kwargs = config.legend.to_matplotlib_kwargs()
            # Remove alpha if present (use transparency mapping instead)
            if "alpha" in legend_kwargs:
                legend_kwargs["framealpha"] = legend_kwargs.pop("alpha")
            ax.legend(**legend_kwargs)
    
    def _apply_title(self, ax: Axes, config: ChartConfiguration):
        """Apply title to the chart."""
        if config.title:
            ax.set_title(config.title, fontsize=14, fontweight="bold", pad=20)
    
    def create_preview(self, config: ChartConfiguration, data: pd.DataFrame, 
                      size: Tuple[float, float] = (4, 3)) -> Figure:
        """Create a preview figure with the given configuration.
        
        Args:
            config: The chart configuration
            data: The data to preview
            size: The figure size for preview
            
        Returns:
            A matplotlib figure with the preview
        """
        # Create a temporary config with preview size
        preview_config = ChartConfiguration(
            title=config.title,
            chart_type=config.chart_type,
            x_column=config.x_column,
            y_column=config.y_column,
            line_style=config.line_style,
            marker_style=config.marker_style,
            x_axis=config.x_axis,
            y_axis=config.y_axis,
            legend=config.legend,
            background_color=config.background_color,
            figure_size=size,
            dataset_id=config.dataset_id
        )
        
        # Create preview figure
        fig = plt.figure(figsize=size)
        self.apply_configuration(fig, preview_config, data)
        
        return fig
    
    def get_default_configuration(self, dataset_id: str = "", 
                                x_column: str = "", y_column: str = "") -> ChartConfiguration:
        """Get a default chart configuration.
        
        Args:
            dataset_id: The dataset ID
            x_column: Default x column
            y_column: Default y column
            
        Returns:
            A default chart configuration
        """
        return ChartConfiguration(
            dataset_id=dataset_id,
            x_column=x_column,
            y_column=y_column
        )
    
    def validate_configuration(self, config: ChartConfiguration, 
                             available_columns: list) -> Tuple[bool, str]:
        """Validate a chart configuration against available data.
        
        Args:
            config: The configuration to validate
            available_columns: List of available column names
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not config.validate():
            return False, "Configuration is incomplete"
        
        if config.x_column not in available_columns:
            return False, f"X column '{config.x_column}' not found in data"
        
        if config.y_column not in available_columns:
            return False, f"Y column '{config.y_column}' not found in data"
        
        return True, ""
    
    def export_style_preset(self, config: ChartConfiguration, name: str) -> dict:
        """Export chart styling as a reusable preset.
        
        Args:
            config: The configuration to export
            name: Name for the preset
            
        Returns:
            Dictionary containing the style preset
        """
        return {
            "name": name,
            "line_style": config.line_style.to_matplotlib_kwargs(),
            "marker_style": config.marker_style.to_matplotlib_kwargs(),
            "x_axis": config.x_axis.to_matplotlib_kwargs(),
            "y_axis": config.y_axis.to_matplotlib_kwargs(),
            "legend": config.legend.to_matplotlib_kwargs(),
            "background_color": config.background_color
        }
    
    def apply_style_preset(self, config: ChartConfiguration, preset: dict) -> ChartConfiguration:
        """Apply a style preset to a configuration.
        
        Args:
            config: The configuration to modify
            preset: The style preset to apply
            
        Returns:
            The modified configuration
        """
        # This would apply the preset values back to the configuration
        # For now, return the original config
        # Full implementation would involve reverse mapping from matplotlib kwargs
        return config

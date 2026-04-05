"""Chart configuration data structures for pandaplot application."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple


class ChartType(Enum):
    """Supported chart types."""
    LINE = "line"
    SCATTER = "scatter"
    BAR = "bar"
    HISTOGRAM = "histogram"
    BOX = "box"
    VIOLIN = "violin"


class LineStyleType(Enum):
    """Line style types."""
    SOLID = "solid"
    DASHED = "dashed"
    DOTTED = "dotted"
    DASHDOT = "dashdot"


class MarkerType(Enum):
    """Marker types."""
    CIRCLE = "circle"
    SQUARE = "square"
    TRIANGLE = "triangle"
    DIAMOND = "diamond"
    STAR = "star"
    PLUS = "plus"
    CROSS = "cross"
    NONE = "none"


class ScaleType(Enum):
    """Axis scale types."""
    LINEAR = "linear"
    LOG = "log"


class LegendPosition(Enum):
    """Legend position options."""
    UPPER_RIGHT = "upper right"
    UPPER_LEFT = "upper left"
    LOWER_RIGHT = "lower right"
    LOWER_LEFT = "lower left"
    CENTER = "center"
    UPPER_CENTER = "upper center"
    LOWER_CENTER = "lower center"
    CENTER_LEFT = "center left"
    CENTER_RIGHT = "center right"
    BEST = "best"


@dataclass
class LineStyle:
    """Configuration for line styling."""
    color: str = "#1f77b4"
    width: float = 2.0
    style: LineStyleType = LineStyleType.SOLID
    transparency: float = 1.0
    
    def to_matplotlib_kwargs(self) -> dict:
        """Convert to matplotlib line kwargs."""
        return {
            "color": self.color,
            "linewidth": self.width,
            "linestyle": self.style.value,
            "alpha": self.transparency
        }


@dataclass
class MarkerStyle:
    """Configuration for marker styling."""
    type: MarkerType = MarkerType.CIRCLE
    size: float = 6.0
    color: str = "#1f77b4"
    edge_color: str = "#000000"
    edge_width: float = 1.0
    transparency: float = 1.0
    
    def to_matplotlib_kwargs(self) -> dict:
        """Convert to matplotlib marker kwargs."""
        marker_map = {
            MarkerType.CIRCLE: "o",
            MarkerType.SQUARE: "s",
            MarkerType.TRIANGLE: "^",
            MarkerType.DIAMOND: "D",
            MarkerType.STAR: "*",
            MarkerType.PLUS: "+",
            MarkerType.CROSS: "x",
            MarkerType.NONE: ""
        }
        
        return {
            "marker": marker_map[self.type],
            "markersize": self.size,
            "markerfacecolor": self.color,
            "markeredgecolor": self.edge_color,
            "markeredgewidth": self.edge_width,
            "alpha": self.transparency
        }


@dataclass
class AxisStyle:
    """Configuration for axis styling."""
    label: str = ""
    font_size: int = 12
    font_family: str = "Arial"
    color: str = "#000000"
    show_grid: bool = True
    grid_color: str = "#cccccc"
    grid_style: LineStyleType = LineStyleType.SOLID
    scale: ScaleType = ScaleType.LINEAR
    auto_limits: bool = True
    min_limit: Optional[float] = None
    max_limit: Optional[float] = None
    
    def to_matplotlib_kwargs(self) -> dict:
        """Convert to matplotlib axis kwargs."""
        return {
            "color": self.color,
            "fontsize": self.font_size,
            "fontfamily": self.font_family
        }


@dataclass
class LegendStyle:
    """Configuration for legend styling."""
    show: bool = True
    position: LegendPosition = LegendPosition.UPPER_RIGHT
    font_size: int = 10
    background_color: str = "#ffffff"
    transparency: float = 0.8
    border_color: str = "#000000"
    border_width: float = 1.0
    
    def to_matplotlib_kwargs(self) -> dict:
        """Convert to matplotlib legend kwargs."""
        return {
            "loc": self.position.value,
            "fontsize": self.font_size,
            "facecolor": self.background_color,
            "framealpha": self.transparency
        }


@dataclass
class ChartConfiguration:
    """Complete chart configuration."""
    title: str = ""
    chart_type: ChartType = ChartType.LINE
    x_column: str = ""
    y_column: str = ""
    line_style: LineStyle = field(default_factory=lambda: LineStyle())
    marker_style: MarkerStyle = field(default_factory=lambda: MarkerStyle())
    x_axis: AxisStyle = field(default_factory=lambda: AxisStyle())
    y_axis: AxisStyle = field(default_factory=lambda: AxisStyle())
    legend: LegendStyle = field(default_factory=lambda: LegendStyle())
    background_color: str = "#ffffff"
    figure_size: Tuple[float, float] = (10, 6)
    dataset_id: str = ""
    chart_id: str = ""
    
    def validate(self) -> bool:
        """Validate the configuration."""
        if not self.x_column or not self.y_column:
            return False
        if not self.dataset_id:
            return False
        return True
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "title": self.title,
            "chart_type": self.chart_type.value,
            "x_column": self.x_column,
            "y_column": self.y_column,
            "line_style": {
                "color": self.line_style.color,
                "width": self.line_style.width,
                "style": self.line_style.style.value,
                "transparency": self.line_style.transparency
            },
            "marker_style": {
                "type": self.marker_style.type.value,
                "size": self.marker_style.size,
                "color": self.marker_style.color,
                "edge_color": self.marker_style.edge_color,
                "edge_width": self.marker_style.edge_width,
                "transparency": self.marker_style.transparency
            },
            "x_axis": {
                "label": self.x_axis.label,
                "font_size": self.x_axis.font_size,
                "font_family": self.x_axis.font_family,
                "color": self.x_axis.color,
                "show_grid": self.x_axis.show_grid,
                "grid_color": self.x_axis.grid_color,
                "grid_style": self.x_axis.grid_style.value,
                "scale": self.x_axis.scale.value,
                "auto_limits": self.x_axis.auto_limits,
                "min_limit": self.x_axis.min_limit,
                "max_limit": self.x_axis.max_limit
            },
            "y_axis": {
                "label": self.y_axis.label,
                "font_size": self.y_axis.font_size,
                "font_family": self.y_axis.font_family,
                "color": self.y_axis.color,
                "show_grid": self.y_axis.show_grid,
                "grid_color": self.y_axis.grid_color,
                "grid_style": self.y_axis.grid_style.value,
                "scale": self.y_axis.scale.value,
                "auto_limits": self.y_axis.auto_limits,
                "min_limit": self.y_axis.min_limit,
                "max_limit": self.y_axis.max_limit
            },
            "legend": {
                "show": self.legend.show,
                "position": self.legend.position.value,
                "font_size": self.legend.font_size,
                "background_color": self.legend.background_color,
                "transparency": self.legend.transparency,
                "border_color": self.legend.border_color,
                "border_width": self.legend.border_width
            },
            "background_color": self.background_color,
            "figure_size": self.figure_size,
            "dataset_id": self.dataset_id,
            "chart_id": self.chart_id
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ChartConfiguration":
        """Create configuration from dictionary."""
        config = cls()
        config.title = data.get("title", "")
        config.chart_type = ChartType(data.get("chart_type", ChartType.LINE.value))
        config.x_column = data.get("x_column", "")
        config.y_column = data.get("y_column", "")
        config.background_color = data.get("background_color", "#ffffff")
        config.figure_size = tuple(data.get("figure_size", (10, 6)))
        config.dataset_id = data.get("dataset_id", "")
        config.chart_id = data.get("chart_id", "")
        
        # Line style
        line_data = data.get("line_style", {})
        config.line_style = LineStyle(
            color=line_data.get("color", "#1f77b4"),
            width=line_data.get("width", 2.0),
            style=LineStyleType(line_data.get("style", LineStyleType.SOLID.value)),
            transparency=line_data.get("transparency", 1.0)
        )
        
        # Marker style
        marker_data = data.get("marker_style", {})
        config.marker_style = MarkerStyle(
            type=MarkerType(marker_data.get("type", MarkerType.CIRCLE.value)),
            size=marker_data.get("size", 6.0),
            color=marker_data.get("color", "#1f77b4"),
            edge_color=marker_data.get("edge_color", "#000000"),
            edge_width=marker_data.get("edge_width", 1.0),
            transparency=marker_data.get("transparency", 1.0)
        )
        
        # X axis
        x_axis_data = data.get("x_axis", {})
        config.x_axis = AxisStyle(
            label=x_axis_data.get("label", ""),
            font_size=x_axis_data.get("font_size", 12),
            font_family=x_axis_data.get("font_family", "Arial"),
            color=x_axis_data.get("color", "#000000"),
            show_grid=x_axis_data.get("show_grid", True),
            grid_color=x_axis_data.get("grid_color", "#cccccc"),
            grid_style=LineStyleType(x_axis_data.get("grid_style", LineStyleType.SOLID.value)),
            scale=ScaleType(x_axis_data.get("scale", ScaleType.LINEAR.value)),
            auto_limits=x_axis_data.get("auto_limits", True),
            min_limit=x_axis_data.get("min_limit"),
            max_limit=x_axis_data.get("max_limit")
        )
        
        # Y axis
        y_axis_data = data.get("y_axis", {})
        config.y_axis = AxisStyle(
            label=y_axis_data.get("label", ""),
            font_size=y_axis_data.get("font_size", 12),
            font_family=y_axis_data.get("font_family", "Arial"),
            color=y_axis_data.get("color", "#000000"),
            show_grid=y_axis_data.get("show_grid", True),
            grid_color=y_axis_data.get("grid_color", "#cccccc"),
            grid_style=LineStyleType(y_axis_data.get("grid_style", LineStyleType.SOLID.value)),
            scale=ScaleType(y_axis_data.get("scale", ScaleType.LINEAR.value)),
            auto_limits=y_axis_data.get("auto_limits", True),
            min_limit=y_axis_data.get("min_limit"),
            max_limit=y_axis_data.get("max_limit")
        )
        
        # Legend
        legend_data = data.get("legend", {})
        config.legend = LegendStyle(
            show=legend_data.get("show", True),
            position=LegendPosition(legend_data.get("position", LegendPosition.UPPER_RIGHT.value)),
            font_size=legend_data.get("font_size", 10),
            background_color=legend_data.get("background_color", "#ffffff"),
            transparency=legend_data.get("transparency", 0.8),
            border_color=legend_data.get("border_color", "#000000"),
            border_width=legend_data.get("border_width", 1.0)
        )
        
        return config

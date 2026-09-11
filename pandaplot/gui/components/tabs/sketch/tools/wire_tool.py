import math
from typing import TYPE_CHECKING, List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QMouseEvent

from pandaplot.gui.components.tabs.sketch.tools.base_tool import BaseTool, ToolMode
from pandaplot.models.project.items.sketch import CircuitComponentElement, Sketch, WireElement

if TYPE_CHECKING:
    from pandaplot.gui.components.tabs.sketch.sketch_canvas import SketchCanvas


def find_snap_terminal(
    point: Tuple[float, float], sketch: Sketch, radius_px: float = 15.0
) -> Optional[Tuple[str, str, Tuple[float, float]]]:
    """Find the nearest component terminal to a canvas point within radius_px.

    Returns (component_id, terminal_id, terminal_world_pos) or None.
    """
    best_match = None
    best_dist = radius_px

    for layer in sketch.layers:
        if not layer.visible or layer.locked:
            continue
        for elem in layer.elements:
            if isinstance(elem, CircuitComponentElement):
                for term in elem.terminals:
                    pos = elem.terminal_world_pos(term.id)
                    dist = math.hypot(point[0] - pos[0], point[1] - pos[1])
                    if dist <= best_dist:
                        best_dist = dist
                        best_match = (elem.id, term.id, pos)

    return best_match


def compute_manhattan_elbow(
    start_pos: Tuple[float, float], end_pos: Tuple[float, float]
) -> List[Tuple[float, float]]:
    """Compute orthogonal Manhattan elbow path (2 to 4 waypoints)."""
    x1, y1 = start_pos
    x2, y2 = end_pos

    if math.isclose(x1, x2) or math.isclose(y1, y2):
        return [(x1, y1), (x2, y2)]

    mid_x = (x1 + x2) / 2.0
    return [(x1, y1), (mid_x, y1), (mid_x, y2), (x2, y2)]


def get_attached_wire_updates(sketch: Sketch, component_id: str) -> List[Tuple[str, List[Tuple[float, float]]]]:
    """Compute new waypoints for all wires connected to component_id.

    Returns list of (wire_id, new_waypoints).
    """
    results = []
    comp = None
    for layer in sketch.layers:
        for elem in layer.elements:
            if elem.id == component_id and isinstance(elem, CircuitComponentElement):
                comp = elem
                break

    if not comp:
        return results

    for layer in sketch.layers:
        for elem in layer.elements:
            if isinstance(elem, WireElement):
                wire = elem
                updated = False
                wps = list(wire.waypoints)
                if not wps:
                    continue

                if wire.start_ref and wire.start_ref[0] == component_id:
                    term_id = wire.start_ref[1]
                    new_pt = comp.terminal_world_pos(term_id)
                    wps[0] = new_pt
                    if len(wps) >= 2:
                        wps = compute_manhattan_elbow(wps[0], wps[-1])
                    updated = True

                if wire.end_ref and wire.end_ref[0] == component_id:
                    term_id = wire.end_ref[1]
                    new_pt = comp.terminal_world_pos(term_id)
                    wps[-1] = new_pt
                    if len(wps) >= 2:
                        wps = compute_manhattan_elbow(wps[0], wps[-1])
                    updated = True

                if updated:
                    results.append((wire.id, wps))

    return results


class WireTool(BaseTool):
    """Tool for drawing wires and connecting component terminals."""

    def __init__(self, canvas: "SketchCanvas"):
        super().__init__(ToolMode.WIRE, canvas)
        self.is_drawing: bool = False
        self.start_pos: Optional[Tuple[float, float]] = None
        self.start_ref: Optional[Tuple[str, str]] = None

    def mouse_press(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            layer = self.canvas.sketch.get_active_layer()
            if not layer or not layer.visible or layer.locked:
                return

            scene_pos = self.canvas.mapToScene(event.position().toPoint())
            pt = (scene_pos.x(), scene_pos.y())

            snap = find_snap_terminal(pt, self.canvas.sketch)
            if snap:
                self.start_ref = (snap[0], snap[1])
                self.start_pos = snap[2]
            else:
                self.start_ref = None
                self.start_pos = pt

            self.is_drawing = True

    def mouse_move(self, event: QMouseEvent) -> None:
        pass

    def mouse_release(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton and self.is_drawing and self.start_pos:
            scene_pos = self.canvas.mapToScene(event.position().toPoint())
            end_pt = (scene_pos.x(), scene_pos.y())
            snap = find_snap_terminal(end_pt, self.canvas.sketch)

            end_ref = None
            if snap:
                end_ref = (snap[0], snap[1])
                end_pt = snap[2]

            waypoints = compute_manhattan_elbow(self.start_pos, end_pt)
            wire_elem = WireElement(
                stroke_color=self.canvas.active_stroke_color,
                stroke_width=self.canvas.active_stroke_width,
                stroke_style=self.canvas.active_stroke_style,
                waypoints=waypoints,
                start_ref=self.start_ref,
                end_ref=end_ref,
            )

            self.canvas.add_element_to_active_layer(wire_elem)

            self.is_drawing = False
            self.start_pos = None
            self.start_ref = None

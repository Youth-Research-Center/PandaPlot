"""Helpers shared by the sketch element commands."""
from pandaplot.models.events import SketchEvents
from pandaplot.models.events.event_data import SketchChangedData
from pandaplot.models.project.items.sketch import Sketch
from pandaplot.models.state import AppContext


def emit_sketch_changed(app_context: AppContext, sketch: Sketch) -> None:
    """Announce that `sketch`'s layers or elements changed."""
    app_context.event_bus.emit(SketchEvents.SKETCH_CHANGED, SketchChangedData(sketch_id=sketch.id).to_dict())


def locked_element_ids(sketch: Sketch, element_ids: list[str]) -> list[str]:
    """The ids in `element_ids` whose element sits on a locked layer."""
    locked = []
    for element_id in element_ids:
        found = sketch.find_element(element_id)
        if found is not None and found[0].locked:
            locked.append(element_id)
    return locked

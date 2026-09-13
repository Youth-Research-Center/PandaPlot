# Sketching Tab Architecture & Sub-Issues Master Specification

**Parent Issue:** [#148 - Add a sketching tab (freehand/shape drawing canvas item)](https://github.com/Youth-Research-Center/PandaPlot/issues/148)
**Milestone:** 11. Sketching Canvas
**Labels:** `area: chart-types`, `effort: l`, `enhancement`, `priority: medium`

---

## Executive Summary

PandaPlot currently supports Chart, Dataset, Note, Image/ImageGallery, and Folder items within its hierarchical project structure. Issue #148 introduces a dedicated **Sketching Tab** (`Sketch` item) — a general-purpose vector drawing canvas (think draw.io or a single PowerPoint slide), operating alongside existing tabs, for freehand drawing, geometric shapes, text labels, and layered diagrams.

To ensure modularity, high code quality, testability, and incremental delivery, Issue #148 is decomposed into **5 sub-issues**, all under the **11. Sketching Canvas** milestone.

### Architecture decision: Qt Graphics View framework

The interactive canvas (selection, resize handles, freehand capture, pan/zoom, z-ordering) is built on `QGraphicsScene`/`QGraphicsView`. **This is a new pattern for the codebase** — every other visual surface in PandaPlot (chart rendering, 3D charts) is matplotlib-based; there is no existing `QGraphicsView` usage to model GUI code on. This is a deliberate choice, not an oversight: matplotlib is a poor fit for the direct-manipulation interactions this feature needs (drag-to-resize, live freehand strokes, per-element hit-testing), and `QGraphicsView` is purpose-built for exactly this. Confirmed with the repo owner.

Because it's a first-of-its-kind dependency, Sub-Issue 2 should start with a small throwaway spike (a `QGraphicsView` rendering one rectangle inside a real `SketchTab`-shaped widget, run under `QT_QPA_PLATFORM=offscreen` like the rest of the GUI test suite) before building out the full tool set, to surface any integration surprises (embedding inside the existing tab/dock layout, event routing, headless test behavior) early.

Data-side persistence, by contrast, follows the codebase's existing JSON-in-zip convention closely — see Sub-Issue 1.

---

## Sub-Issue Index

| Issue # | Title | Effort | Priority | Key Deliverables |
|---------|-------|--------|----------|------------------|
| **Sub-Issue 1** | [[Sketch Tab] Sketch Data Model, Layer Architecture, and Project Persistence](01-data-model-and-persistence.md) | `effort: m` | `priority: medium` | `Sketch` item model, `SketchLayer`, element primitives (`Freehand`, `Line`, `Rectangle`, `Ellipse`, `Text`), `SketchDataManager` (JSON persisted via `to_dict`/`from_dict`, same pattern as `ChartDataManager`). |
| **Sub-Issue 2** | [[Sketch Tab] Canvas Viewport, Interactive Tools, and Selection/Manipulation](02-canvas-and-drawing-tools.md) | `effort: m` | `priority: medium` | `QGraphicsScene`/`QGraphicsView` canvas, tool state machine, freehand/shape/text tools, selection handles, resize/move/delete, pan & zoom. |
| **Sub-Issue 3** | [[Sketch Tab] Element Styling Controls, Property Inspector, and Commands](03-styling-and-property-inspector.md) | `effort: s` | `priority: medium` | Property inspector toolbar, stroke/fill/line-width/font options, live styling, undoable/redoable `Command` subclasses for element mutations. |
| **Sub-Issue 4** | [[Sketch Tab] Layer Management UI, Tab Editor, and Project Tree Integration](04-layer-management-and-gui-integration.md) | `effort: m` | `priority: medium` | `SketchTab` view, project tree context menu & tree-label icon, `LayerManagerPanel` (add/remove/reorder layers, visibility & lock toggles). |
| **Sub-Issue 5** | [[Sketch Tab] Image Export and Domain Extension Framework Foundation](05-export-and-extension-framework.md) | `effort: s` | `priority: medium` | Export to PNG/SVG/PDF/JPEG, resolution/transparency controls, minimal element-type registry seam for domain-specific follow-ups (e.g. circuit sketching). |

Sub-issues 1 and 2 can start in parallel (model and canvas are independent until wiring). 3 and 4 depend on both. 5 depends on 1+2.

---

## High-Level Architecture

```
                                  ┌────────────────────────┐
                                  │      Project Tree      │
                                  └───────────┬────────────┘
                                              │ Creates/Opens
                                              ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                       SketchTab                                        │
│  ┌───────────────────────┐  ┌───────────────────────────────────┐  ┌────────────────┐  │
│  │    Drawing Toolbar    │  │       SketchCanvas (View/Scene)   │  │ Layer Manager  │  │
│  │ (Pen, Line, Rect,...) │  │  ┌─────────────────────────────┐  │  │ (Layers List,  │  │
│  └───────────┬───────────┘  │  │ Layer 2 (Active/Visible)    │  │  │ Visibility,    │  │
│              │ Active Tool  │  │  ├─ TextElement             │  │  │ Lock, Reorder) │  │
│              ▼              │  └─────────────────────────────┘  │  └───────┬────────┘  │
│  ┌───────────────────────┐  │  ┌─────────────────────────────┐  │          │ Sync      │
│  │  Property Inspector   │  │  │ Layer 1 (Locked/Visible)    │  │  ◄───────┘           │
│  │ (Color, Width, Font)  │  │  │  ├─ FreehandElement         │  │                      │
│  └───────────────────────┘  │  │  └─ RectangleElement        │  │                      │
│                             │  └─────────────────────────────┘  │                      │
│                             └─────────────────┬─────────────────┘                      │
└────────────────────────────────────────────────┼───────────────────────────────────────┘
                                                │ item.to_dict() / Command execute()
                                                ▼
                                    ┌───────────────────────┐
                                    │   SketchDataManager   │
                                    │ (path_in_zip + .json) │
                                    └───────────────────────┘
```

---

## Traceability to Issue #148 Requirements

- **New "Sketch" item type in project tree with own tab/editor:** Handled by Sub-Issues 1 & 4.
- **Basic drawing tools (freehand pen, straight lines, basic shapes, text labels):** Handled by Sub-Issue 2.
- **Selection, move, resize, delete of drawn elements:** Handled by Sub-Issue 2.
- **Color/line-width/style controls for drawn elements:** Handled by Sub-Issue 3.
- **Persist sketches as part of project file:** Handled by Sub-Issue 1.
- **Export sketch as an image:** Handled by Sub-Issue 5.
- **Layers support:** Handled by Sub-Issues 1 & 4.
- **Foundation for structured-drawing features (electronics circuit follow-up):** Handled by Sub-Issue 5 (kept minimal — see that spec's scope note).

## Relationship to Issue #109 (chart annotations)

Issue #109 ("draw/annotate directly on top of a chart") is explicitly out of scope here and stays matplotlib-based, anchored to chart data coordinates. #148/this work is a standalone, general-purpose drawing surface with no data anchoring. The two do not share code; if there's ever appetite to unify them, that's a separate future decision, not an implicit goal of this milestone.

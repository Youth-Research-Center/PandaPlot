# Sub-Issue 5 Design Specification: Image Export and Domain Extension Framework Foundation

**Parent Issue:** [#148 - Add a sketching tab (freehand/shape drawing canvas item)](https://github.com/Youth-Research-Center/PandaPlot/issues/148)
**Milestone:** 11. Sketching Canvas
**Labels:** `area: chart-types`, `effort: s`, `enhancement`, `priority: medium`

---

## 1. Goal & Objectives

Provide export options for sketches to standard image/vector formats (PNG, SVG, PDF, JPEG) with customizable export options, and leave a clean, minimal seam so a future domain-specific drawing feature (electronics circuit components: resistors, capacitors, logic gates) can add its own element types without modifying core sketch code.

---

## 2. Sketch Image Export

```
pandaplot/gui/dialogs/sketch/
└── export_sketch_dialog.py     # Dialog for format, resolution & background settings
```

### 2.1 Export Features & Options
- **Formats**: PNG (raster with alpha channel), JPEG (compressed raster), SVG (vector graphic), PDF (document vector).
- **Export Region Options**:
  - `Entire Canvas Bounds`: Full `canvas_width` x `canvas_height`.
  - `Bounding Box of Elements`: Tight cropping around drawn elements with configurable padding (default: 10px).
- **Background Options**:
  - `Solid Color` (default canvas background).
  - `Transparent` (for PNG / SVG).
- **Resolution / Scale**: Scale factor (`1x`, `2x`, `4x`, custom DPI: 72, 150, 300, 600 DPI for high-resolution publication export).
- **Layer Selection**: Export all visible layers vs export specific layers.

### 2.2 Implementation Detail
Using `QGraphicsScene.render()` onto a `QPainter` target:
- For PNG/JPEG: Render onto `QImage` / `QPixmap` with desired DPI resolution.
- For SVG: Render onto `QSvgGenerator`.
- For PDF: Render onto `QPdfWriter` / `QPrinter`.

---

## 3. Extension seam for domain features — keep this minimal

The parent issue explicitly calls out a follow-up:
> "This is intended as the foundation other structured-drawing features can build on — see the electronics circuit sketching follow-up issue, which extends this with domain-specific components (resistors, capacitors, etc.)."

**Scope this down for now.** The original proposal here was a full plugin architecture — an abstract `SketchExtension` base class plus a `SketchComponentRegistry` singleton for third-party tool/element registration. Building that speculatively, before there is a second concrete consumer, is exactly the kind of premature abstraction this repo's own "4. Architecture Cleanup & Tech Debt" milestone exists to clean up later. There's also only one real requirement right now: new element `type` strings must be addable without editing `SketchElement.from_dict()`'s dispatch table in five places.

So for this sub-issue, do only this:
- Make the `type -> class` lookup used by `SketchElement.from_dict()` (Sub-Issue 1, §2.3) an explicit module-level `dict` that a future module can `.update()` into, rather than a hardcoded `if/elif` chain. That's the entire "extension point" needed today.
- Do **not** build `SketchExtension`, a plugin registry, or a custom-tools-in-toolbar mechanism in this sub-issue. When the circuit-sketching follow-up issue is actually scoped, design its registration API then, informed by what that feature actually needs — it's likely simpler than a generic ABC-based plugin system (e.g. it may just need a handful of new `SketchElement`/`QGraphicsItem`/tool triples registered into the same dict/`ToolManager`/`TabFactory`-style registries already built in Sub-Issues 1, 2 and 4).

---

## 4. Verification & Testing Plan

1. **Export Tests (`tests/gui/sketch/test_export_sketch.py`)**:
   - Verify rendering `SketchCanvas` to temporary PNG, SVG, PDF, JPEG files.
   - Test transparent background export options.
   - Verify DPI scaling factors produce correct image dimensions.
2. **Element-type dispatch test (`tests/models/project/items/test_sketch_element_registry.py`)**:
   - Register a dummy new element type into the `type -> class` dict and confirm `SketchElement.from_dict()` picks it up without any change to the five existing element modules.

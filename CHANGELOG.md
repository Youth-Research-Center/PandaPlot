# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning tracks the tags published via the **Build Release Installer**
GitHub Actions workflow, not necessarily `pyproject.toml`'s version string.

When you open a PR with a user-facing change, add an entry under
`[Unreleased]`. Before running a release, a maintainer renames
`[Unreleased]` to the new version and date, and that section is pulled
into the GitHub Release notes automatically (see `.github/workflows/release_installer.yml`).

## [Unreleased]

### Fixed
- Transient context menus in the tab bar, dataset table, image gallery, and sidebar icon bar are now deleted after closing instead of remaining attached to their parent widget (#587).
- The (x, y) mouse readout on the chart toolbar reserves a fixed amount of space, so moving the cursor over the chart or leaving it no longer resizes the toolbar and makes the chart area flicker; readouts too long for the space, such as two Y values, are shortened with an ellipsis (#511).
- Adding an item beneath a non-folder project item keeps it in the nearest ancestor folder instead of relocating it to the root.

### Added
- In-app Help (#519): **Help → Help Topics...** (`F1`) opens a searchable Help window that explains each analysis operation (statistical tests, descriptive statistics, preprocessing, derivatives, integrals, smoothing, interpolation, signal analysis, curve-fitting models, transforms and formulas, and the Analyze Measurements wizard), with step-by-step instructions for each analysis panel. A **?** button next to each analysis panel's title opens the Help window on that panel's topic. A Charts category covers how to create, style and save a chart (series, axes, legend, error bars, math text, saving an image) with a topic for every chart type; the Chart Properties panel and every step of the chart wizard have a **?** button, `F1` opens help for the current wizard step, and the Help window stays usable while a modal dialog such as the chart wizard is open.
- The leader line of a value label on Line and Scatter series can be styled: choose a plain line, an open arrowhead or a filled arrowhead at the point, its color (or match the label text), width and line style (solid, dashed, dotted) under the Arrow option in the Style tab (#504). Existing charts keep their thin black line.
- Sketch export (#364): **Export…** in a sketch's toolbar writes PNG (optionally transparent), JPEG, SVG or PDF, for the whole canvas or just the drawn elements with padding, at a chosen scale for images, and with the layers you pick.
- Chart types are organised into categories (Line & Scatter, Bar & Pie, Distribution, Fields & Grids, 3-D). The New Chart wizard and the chart tab pick a category from a dropdown and then show only that category's types (#494).
- Value labels on Line and Scatter series can also be limited to local minima and maxima (the peaks and valleys of a curve) with the new "Local min and max" choice in the "Label points" option.
- Value labels on Line and Scatter series can be limited to the minimum and maximum points, only the minimum, or only the maximum, using the new "Label points" option in the Style tab.
- Sketch items (#148): **Data → New Sketch**, or **Add Sketch** in the project tree, creates a sketch that opens in its own tab and is saved with the project. Draw smooth freehand strokes, lines, rectangles, ellipses and text labels; select (click, Shift-click or drag a box), move, resize and delete elements, each as one undo step; pan with space+drag or the middle button and zoom with Ctrl+wheel. A layer panel beside the canvas adds, deletes, renames and reorders layers, shows or hides and locks them, and sets their opacity, all undoable. A property bar under the tools sets stroke colour, width and line style, fill (or none; colours can be translucent), and font, size, bold, italic and alignment for text: for the selection as one undo step, showing "Mixed" where selected elements differ, or, with nothing selected, for new elements.
- Fit panel input settings are remembered independently for each chart or dataset tab, including tabs in floating windows.
- "Swap X/Y" chart toolbar action (#266): swaps a Line, Scatter or Vector chart's X and Y columns (and vector U/V), fits, error-bar columns, fill direction, and axis titles, scales, ranges and ticks in one undoable step.
- Stacked Bar chart type: each series stacks on top of the earlier ones at the same X (negative values stack downward), with error bars, value labels, a wizard preview, and lossless switching to and from Bar. Fits are not available on stacked charts.
- Ready-to-open curve-fitting example project with fitted charts, uncertainty bars, confidence bands, and a PNG preview.
- Date-typed dataset cells support text entry and calendar selection, with undo/redo and timezone-aware values preserved.
- Standalone desktop installer packaging via `pyside6-deploy`/Nuitka (`scripts/build_installer.py`, `pysidedeploy.spec`).
- `Build Release Installer` GitHub Actions workflow: builds installers for Linux, Windows, and macOS, and publishes them to a GitHub Release with SHA256 checksums under a user-supplied version tag.

### Changed
- The chart and note editor toolbars, the image gallery buttons and the image lightbox show bundled Phosphor icons that follow the theme colours instead of emoji or arrow glyphs; menus are unchanged and stay text only (#572). The gallery's back/forward/sort buttons are now icon buttons with accessible names, and the image lightbox is released when it closes.
- The sidebar icon bar and its settings button show bundled Phosphor vector icons that follow the theme colours (muted normally, accent for the open panel) instead of emoji, and the About dialog credits the icon library (#520). Maintainers add icons by editing `icon_manifest.toml` and running `scripts/icons/build_icon_bundle.py`, which regenerates the committed bundle, licence files and `THIRD_PARTY_NOTICES.md` (`--check` verifies they are in sync).
- Dropdowns (combo boxes) share one themed style in sidebar panels, dialogs, and wizards: rounded bordered field, caret arrow, accent outline on hover and focus, an inset disabled state, and a list that always opens below the field instead of over it on macOS (#406).
- The packaged Windows executable no longer opens a console window; logs are written to `~/.pandaplot/application.log` instead of the process's working directory.
- Numeric fields (decimals and whole numbers) in sidebar panels, dialogs, and the chart editor are now a shared input instead of spin boxes: large `-` / `+` buttons that repeat when held, Up/Down arrows to step (Page Up/Down or Shift for ten times as much), a fixed unit label, and `.` or `,` as the decimal separator. The mouse wheel only changes a value while its field has focus, so scrolling a panel no longer edits numbers by accident (#407).

### Fixed
- Renaming an image gallery inline in the project tree no longer puts its 🖼️ icon into the new name. A rejected rename now keeps each item's own icon instead of switching to the chart icon, and no longer blanks the label of an empty folder or gallery.

# PandaPlot design system and responsive side panel

Status: approved (2026-11-12). Milestone: **14. Design System & Responsive UI**, epic #669. Issue `DS-nn` in
section 9 is GitHub issue #(669 + nn), for example DS-01 is #670 and DS-86 is #755.

## 1. Goal

One consistent look across the whole app in light and dark, driven from a single place (design tokens + the app
stylesheet), with visible keyboard focus and WCAG-AA contrast. At the same time, the side panel works in less space,
so users on small screens keep room for their charts and data, and grows into a label-beside layout on large screens.

Order of work:

1. **Baselines and foundation**: tests that prove later PRs change no content, tokens, defaults, density, palette,
   base style, focus ring, Storybook infrastructure.
2. **Components**: controls and multi-select widgets, each shown in Storybook.
3. **Containers**: cards, sections, panel form, tabs, panel shell and the dialog family, each shown in Storybook.
4. **Storybook gate**: composed showcase stories prove the parts work together before any production screen moves.
5. **Progressive migration**: sidebar shell, the side panels, dialogs, main-area tabs and chrome, then cleanup.

The icon migration (bundled Phosphor icons, `themed_icon`, `ActionIcons`, `IconLabel`, `item_icon`) is done and is
reused as is.

## 2. Sources

| Source | Location after DS-01 | What it decides |
|---|---|---|
| Component handoff | `docs/design/handoff/` (moved from `docs/design_handoff_components/`) | Tokens, components, containers, dialog family, panel layout rules, all panels (Step 6 AFTER column) |
| Image import design | `docs/design/handoff/07_image_import/` (`image-import-and-gallery.html`, `1e-import-dialog.png`) | Import dialog option **1e** only. Gallery options 1c/1d are out of scope. |
| This spec | `docs/design/design-system.md` | Decisions that refine or override the handoff, responsive behaviour, issue breakdown |

The handoff's `0N_*/*.py` files are unexecuted drafts and a reference only. Every PR brings them to repo conventions
(type hints, keyword-only booleans, Google docstrings, `WidgetExtension` theming, tests). Do not copy draft QSS that
contradicts the approved picks: `:focus { border: focus }` (focus never changes the border), `[card]` on
`bg_surface` (cards are `bg_inset`), checked chips in solid accent (selected is `accent_sel_bg/text`).

Where this spec and the handoff disagree, this spec wins. The differences are in section 4.

"17 panels" in the handoff counts the 13 `SidebarPanel` subclasses with the 5 Chart Properties tabs counted separately.

## 3. Rules for every issue

- **Content is unchanged.** A migrated screen keeps every section, field, value, order and button. Allowed changes:
  the approved redundant labels (section 7.4), section titles drawn in capitals and sub-group titles in sentence case
  (presentational, section 7.4), and tab-order changes caused by `PanelShell`'s close button and footer. Image import
  1e is the one deliberate redesign.
- **One concern per PR**, one PR per issue. Do not start an issue before its dependencies merge.
- **Every new component** lands with a Storybook state-matrix story (states × light/dark × density) and pytest-qt
  tests for its states, keyboard behaviour and accessible names.
- **Every PR that changes how the app looks** (tokens, stylesheet, palette, components, containers, stories, panels,
  dialogs, chrome) attaches screenshots to its PR description, light and dark: before and after for anything that
  already existed, the Storybook state matrix for a new component. Until the DS-12 screenshot script lands, take them
  offscreen with `QWidget.grab()`. A tests-only or docs-only PR says that it has no screenshot instead.
- **Every migration PR**:
  - removes the widget-local `setStyleSheet` calls and hex colour literals of the code it touches (chart data colours
    are content and stay);
  - replaces `SectionHeader`/raw `QGroupBox`/`QFormLayout` in that code with the new containers;
  - attaches screenshots at panel widths 240, 300, 360 and 480 px, light and dark, made with the DS-12 screenshot
    script (480 px shows the side-by-side mode; 360 px still shows stacked once margins and the scrollbar are taken off);
  - passes its DS-02 inventory golden (section 8);
  - adds a `### Changed` CHANGELOG entry. Storybook-only component PRs add none.
- AGENTS.md pitfalls apply: Qt hygiene (owners, `blockSignals`, `deleteLater` for dialogs), accessibility (accessible
  names, keyboard focus, 3:1 non-text contrast against the real background), keyword-only parameters added after
  existing ones, `ApplicationConfig` fields handled in `reset_defaults()`, `validate()` and `update_from_mapping()`.

## 4. Decisions that refine the handoff

### 4.1 Contrast fixes to the handoff tokens

The handoff table fails its own contrast rules (control border on surface 1.59:1 light / 2.15:1 dark; off toggle on a
card 1.46:1 / 1.79:1; muted text on a card 4.43:1 light). Approved fix (option A, rendered comparison reviewed):

| Token | Light | Dark | Ratio on card (`bg_inset`), light / dark |
|---|---|---|---|
| `border_control` | `#8B8E96` | `#72767B` | 3.01 / 3.32 |
| `toggle_off` | `#8B8E96` | `#737579` | 3.01 / 3.29 |
| `text_muted` | `#69707E` | `#A3A9B3` | 4.57 / 6.42 |

Cards and dividers keep the soft handoff greys (`border_panel`, `border_subtle`).

New semantic tokens (the handoff only defines `danger`; the 1e mock, `StatusMessage` and Y₂ indicators need these):

| Token | Light | Dark |
|---|---|---|
| `warning` | `#9A5B00` | `#E0A94A` |
| `success` | `#1E7A46` | `#5BC48A` |
| `y2_accent` | `#8A4BB8` | `#B788D4` |
| `y2_accent_bg` | `#F5EEFB` | `#3A2E45` |

### 4.2 Accent stays user-configurable; teal is the default

- Teal uses the handoff's hand-tuned table for both themes (`accent`, `accent_hover`, `accent_pressed`,
  `accent_sel_bg`, `accent_sel_text`, `focus`, `on_accent`). The config stores one colour, `#0E7C86`, which means
  "use the teal table" in both themes.
- One fix to that table: the dark `accent_hover` `#14909B` gives white `on_accent` text only 3.82:1, so a hovered
  primary button label fails AA. It becomes `#0F7780` (5.29:1), between `accent` `#11808A` (4.69:1) and
  `accent_pressed` `#0C6E77` (5.98:1), so dark hover darkens the button as light hover already does.
- Any other stored accent derives the same tokens plus `accent_disabled` (mix with `bg_surface` at 0.55) and a
  separate, lighter dark-theme `focus`, adjusting each in steps (as `_accent_icon_color` does) until it passes the
  pairs in section 5.2. The Settings accent picker stays.
- The wizard's series swatches (`series_palette` token, `series_config_card.py`) use the chart's real default series
  colours (`default_series_color`) instead of a separate palette, so a wizard preview matches the chart it creates.

### 4.3 Default font and density

- The handoff is drawn at a 12 px UI font with 26 px controls. The app sets `interface_font_size` in points, default
  12 pt (about 16 px on Windows). **The new default is the platform's UI font size**: 9 pt on Windows (12 px), 13 pt
  on macOS (13 px), the desktop's size on Linux. `interface_font_size = 0` means "system"; the Settings spin box shows
  "System" for it, and `AppearanceConfig.__post_init__`/`validate()` (which clamp to ≥ 8 today) must accept 0. The
  system size is read from `QApplication.font()` before the theme sets a size. Custom sizes up to 36 pt still work.
- Type sizes are ratios of the app font's pixel size, taken from the handoff at a 12 px base: caption 11/12, label and
  value 1, section 10.5/12 (700, +1 px tracking, capitals through `QFont.Capitalization.AllUppercase`, never
  `.upper()`), sub-group 11.5/12 (600), panel title 13/12 (600), dialog title 15/12 (600).
- New `AppearanceConfig.density`: `automatic` (default) | `compact` | `default` | `comfortable`.
  - Control height = font line height + density padding (6 / 10 / 14 px), so a 12 px font gives the handoff's
    22 / 26 / 30 px and a large font never clips. Density also sets `pad_x`, `button_pad_x` and `row_gap` (handoff
    table). The handoff's `font_px` column is not used.
  - `automatic` resolves to Compact when the main window's screen has an available height below 900 logical px, and
    to Default otherwise. Comfortable is manual only. The main window re-resolves on `QWindow.screenChanged`
    (debounced), and the stylesheet is re-applied only when the resolved value changes (each re-apply is a full
    repolish; see #648, #578).
  - `ThemeContext` includes the resolved density so its equality check does not swallow a change; `THEME_CHANGED`
    gains a `density` key.
  - The test fixture pins density to Default (the offscreen screen is 800×800, which would resolve to Compact).
- **Migration**: bump `CONFIG_VERSION`, read the raw stored version before `update_from_mapping()` drops it, and
  migrate once: an accent equal to the old default `#4A56C6` becomes `#0E7C86`, a font size equal to the old default
  12 becomes 0. Later starts never re-migrate, so a user who picks `#4A56C6` or 12 pt again keeps it.

### 4.4 Palette first, then Fusion

The app runs on the native Windows style, which ignores QSS backgrounds on `QPushButton` (#391) and draws native
slider grooves; CI already runs Fusion (offscreen). Two steps:

1. DS-09 builds a complete `QPalette` from the tokens under the current style: every role (including Light, Midlight,
   Mid, Dark, Shadow, AlternateBase, Link, PlaceholderText, Accent) for the Active, Inactive and Disabled groups.
2. DS-10 calls `QApplication.setStyle("Fusion")` in `create_qt_application` (and in the Storybook app; not in
   `_apply_to_qapp`) and adds QSS roles for widgets Fusion would otherwise draw from defaults: `QGroupBox`,
   `QScrollBar`, `QSplitter::handle`, `QToolTip`, `QHeaderView`, `QWizard`. It ends with a screenshot audit of every
   tab and dialog on Windows, macOS and Linux. Closes #391.

### 4.5 Existing classes keep their names

- **Combo boxes**: `ValueComboBox` subclasses `DropDownComboBox` today (34 production files use the base). The new look,
  `searchable=`, `placeholder=` and the mixed state go into `DropDownComboBox`, so every combo changes at once;
  `ValueComboBox` stays its value-based subclass (`currentValue()`/`setCurrentValue()`). The popup opens below and
  keeps the existing fallback that opens above when there is no room below.
- **`SectionHeader`** is a `QLabel` used as a title inside a card grid (11 production files). DS-25 moves its styling to
  a QSS role. Each panel PR replaces it with `SubGroup` or `CollapsibleSection`; DS-86 deletes it.
- **`PDialog`, `PWizard`, `PTabWidget`** (`widget_extension.py`) are `WidgetExtension` mixins and stay as they are.
  - The handoff's dialog layout becomes `DialogScaffold` (title row, body, footer) that any `PDialog` composes.
    `PNavDialog(PDialog)` uses it with a rail.
  - `PStepDialog` subclasses `PWizard`, keeps `QWizard` page ids, `nextId()`, `isComplete()` and `restart()`, hides
    the native buttons (`setButtonLayout([])`) and owns one shared step rail and footer, generalised from the Chart
    Wizard's per-page `WizardStepRail` and `WizardFooter`.
  - Underline tabs are a QSS property on any `QTabWidget` (`tabVariant="underline"`, set with a small helper), not a
    new class. Main document tabs keep their current style.
- `PButton`, `SliderWithSpinbox`, `SegmentedControl`, `ToggleSwitch`, `Card`, `NumberInput` are rewritten in place
  behind their current APIs. New parameters are keyword-only and come after the existing ones. `NumberInput` keeps its
  `setMixed()`/`isMixed()` naming, and new widgets follow it.

### 4.6 Checkbox and radio glyphs

QSS indicators need a file path, so `themed_icon` (a `QIcon`) cannot be used directly. DS-17 renders the bundled
Phosphor `check`, `minus` and `circle` glyphs, tinted to `on_accent`/`text_disabled`, into cached SVG files the way
`caret_icon_path` already does, and uses them for app-wide `QCheckBox`/`QRadioButton` indicators (14 px box,
10 px glyph). `CheckList` rows paint the same glyphs in their delegate. The handoff's `check-white.svg`/`dash-white.svg`
are not added.

### 4.7 Multi-select components

`CheckList`, `SingleList`, `ChipSelect` and `DualList` are all built and shown in Storybook. `CheckList` and
`SingleList` get production users in the panel migration. `ChipSelect` and `DualList` have none yet and are built so
the component set is complete.

Preprocessing and Descriptive Statistics keep their existing "Select all" button as the `SubGroup` ghost action and
use `CheckList(show_all_row=False)`, which keeps their content unchanged. The tri-state "All" row is available for
new screens.

### 4.8 Footer slot

`PanelShell`'s footer is a slot. Chart Properties puts the restyled `DirtyFooter` there; panels with action rows use
`PanelFooter`. #332 (remove Apply/Revert from Chart Properties) then only has to remove the footer widget. Migration
does not wait for #332.

### 4.9 Data import stays a single dialog

The handoff's usage table puts Import on the step dialog, but `ImportWizardDialog` is one window today. Under the
content-unchanged rule it moves to `DialogScaffold` and keeps its single page.

## 5. Tokens

### 5.1 Values

Neutral and accent values: handoff README "Design tokens (final)" with the changes in 4.1. Also:

- `space`: 2 / 4 / 6 / 8 / 12 / 16 / 24 (`xxs`…`xxl`); `radius`: control 4, inner 3, chip 4, card 6.
- `type`: ratios in 4.3; `density`: the resolved entry (`control_h`, `pad_x`, `button_pad_x`, `row_gap`).
- Legacy keys (`surface_white`, `surface_chrome`, `surface_inset`, `accent_active_text`, `accent_selected_bg`,
  `accent_icon_active`, `text_hint`, `radius_*`, `status_*`, `font_size_group_title`, …) stay as aliases of the new
  values until DS-86. `accent_active_text` maps to `accent_sel_text`, which passes 4.5:1 on `accent_sel_bg`, so every
  consumer #581 lists becomes contrast-safe. `get_surface_palette()` stays until DS-86.
- `ThemeManager.current_tokens()` returns the cached token dict for the applied theme (for the focus ring and painted
  widgets, which must not rebuild tokens on every paint).

### 5.2 Contrast pairs

Tested in both themes, for teal and three sample custom accents, against `bg_surface` **and** `bg_inset` (and
`bg_canvas` for text):

- ≥ 4.5: text, muted, danger, warning, success, y2_accent (also on `y2_accent_bg`), sel_text/sel_bg, and
  `on_accent` on each enabled accent fill: `accent`, `accent_hover` and `accent_pressed` (rest, hover and pressed
  primary buttons and checked chips).
- ≥ 3: border_control, toggle_off, focus.

The tests live in `tests/services/theme/` using the DS-03 helpers. The Storybook-local overrides in
`color_contrast.py` are deleted in DS-08.

## 6. Components and containers

Visual spec: the handoff step and option id in brackets. Each row is one issue in section 9.

| Component | Spec | Requirements beyond the handoff picture |
|---|---|---|
| `FocusRing` | 04 | One overlay per top-level window driven by `QApplication.focusChanged` (no per-widget overlay, which leaks top-levels when a widget has no parent yet). Keyboard-only (Tab/Backtab/Shortcut reasons), 2 px `focus` 1 px outside, radius + 2, `danger` for destructive buttons, border never changes on focus. Parents reserve 3 px. |
| `PButton` | 3a | Matrix columns: primary, secondary, ghost, destructive, icon-only; rows rest/hover/pressed/focus/disabled. Destructive: red outline and text at rest, `danger` tint 8 % hover and 16 % pressed. Icon-only: `control_h` square, `text_secondary` glyph. |
| `DropDownComboBox` / `ValueComboBox` | 3g, 3i | `searchable=` (filter field in the popup), `placeholder=`, mixed shows italic "Mixed"; selected row `accent_sel_bg/text`, hover `bg_inset`; border `focus` while open. 3i grouping and type badges are not in scope. |
| `SliderWithSpinbox` | 3d | Painted 4 px track and 14 px knob (2 px accent border on hover/pressed), disabled state, 58 px spinbox with unit suffix and no arrows, `step` snaps both, `setMixed()` hides fill and knob and shows "—". Emits a commit signal on release/editing finished (needed by #332). Identical on Windows, macOS, Linux. |
| Text, number fields, `OutputArea` | 1 | `QLineEdit`, `NumberInput` family (keep its +12 px height logic consistent with `control_h`), text areas: height, padding, disabled, `danger` error border, inline hint text. `OutputArea` (handoff `panel_form.py`): read-only results/preview area used by almost every panel. |
| Checkbox and radio indicators | 1 | Section 4.6. |
| `SegmentedControl`, `ToggleSwitch` | 7 | Segment: selected `accent_sel_bg/text` 600, inner radius 3, no width shift, remove the leaking `border-left` rule. Toggle: track `toggle_off`, knob `knob`, disabled `accent_disabled`, focus ring (it is already a focusable `QAbstractButton`). |
| Token pickup | 7 | `ChipRow` (selected `accent_sel_bg/text`, no `#FFFFFF`), `ColorSwatchRow`, `LineStylePicker`, `BusySpinner`, `StatusMessage` (warning/success tokens; Refs #618), help button, `IconLabel`, `EmptyStatePanel`, `CategoryValueSelect`, `ImageThumbnailTile`, `SnapshotDpiComboBox`. |
| Toolbars | – | One QSS role for `QToolBar` and its tool buttons using button tokens; tool buttons keyboard-focusable (AGENTS.md). |
| `CheckList`, `SingleList` | 4a1 | Shared row delegate with optional swatch and monospace meta; checkbox-only state (no row tint); optional tri-state "All" row (`show_all_row=`); count "n of N"; Space toggles the focused row; Shift+click selects a range. `SingleList`: highlighted row, no checkbox. |
| `ChipSelect` | 4b2 | Single 26 px line, chips `accent_sel_bg/text`, "+N", popover = filter + `CheckList`; ↓ opens, Backspace removes the last chip. Popover owned by the widget (no stray top-level). |
| `DualList` | 4c1 | Available / › ‹ » / Selected with drag reorder and double-click to move; buttons disabled when nothing can move; empty-state texts; caps header strip with count. Dialogs only (≥ 280 px). |
| `Card`, `SubGroup` | 2b, 2h | `Card()` API compatible; hover tint, selected `accent_sel_bg` + accent border, focus border, disabled; margins 12, spacing 6, no layout shift; placed on `bg_surface`. `SubGroup`: 11.5/12 600 `text_secondary` + `border_subtle` hairline, optional ghost action. |
| `CollapsibleSection` | 2d | Caps title, chevron. Optional header toggle, separate from expand/collapse: toggle off shows the header only and hides the card; Space on the switch toggles it, Space/Enter on the header expands/collapses. Optional ghost action ("+ Add series"). Modified dot + Reset ghost (also on hover) only where a panel already has a reset. Expanded state remembered per panel for the session. |
| `PanelForm` | Step 6 + 7.2 | Rows `field`, `bare_field`, `inline`, `pair`, `help`, `sub`, `widget`; two modes in one `QGridLayout`. Row gap = density `row_gap` + 2 (8 at Default), label gap 3. |
| Underline tabs | 2j | Hover underline `border_control`, selected accent underline, focus and disabled states, `border_subtle` hairline on the pane, scroll buttons on overflow (replaces the Chart Properties combo fallback). |
| `PanelShell`, `PanelFooter`, `DirtyFooter` | 2m | Header (title 13/12 600, help, close), scroll body (body padding 10, section gap 12) with a divider once scrolled, footer slot with a `border_subtle` top border. Clean state: secondary disabled, primary `accent_disabled`. Status text hidden below 300 px. `main_layout` stays the body layout so existing panel code keeps working. |
| `DialogScaffold` | 2p | Title 15/12 600, margins 14, footer with `border_subtle` top border and platform button order (`QDialogButtonBox` order). Validation: `danger` field border, inline message, primary disabled until valid. |
| `PRailTabs`, `PNavDialog` | 2l, 2q | Rail on `bg_inset`, rows `control_h`, selected `accent_sel_bg/text`. Settings only. |
| `PStepDialog` | 2r | On `PWizard` (4.5). Footer: Back (secondary, left) · Cancel · Next/Finish. Step dots 16 px: done = accent fill ✓, current = `accent_sel_bg` + accent border, todo = `border_control`. Completed steps are clickable; a step error blocks Next. |

## 7. Responsive side panel

### 7.1 Sidebar sizing (DS-33, closes #225)

- `PanelArea` reports the **current** panel's minimum width, not the widest panel's (it is a `QStackedWidget`). Today
  panels need 321–447 px. Each panel PR brings its panel to **240 px**, so the floor drops panel by panel.
- Default panel width 300 px (sidebar 340 px with the 40 px icon bar; today 250 px total). Maximum 50 % of the window.
- Dragging stops at the minimum; dragging past half the minimum collapses to the icon bar. The 60–100 px auto-collapse
  snap is removed.
- A visible splitter handle (hover highlight in `accent`, resize cursor, accessible name).
- Width and collapsed state are session state beside `last_splitter_sizes` (not `AppearanceConfig`, which
  `reset_defaults()` would wipe), saved on drag release and on close, restored clamped to 50 % of the current screen.
  Works for `sidebar_position = right`.
- `Ctrl+B` toggles the sidebar (main-window action; the icon bar tooltip names the shortcut; there is no View menu).

### 7.2 Icon bar (DS-34)

Keyboard navigation (Up/Down between panels, Enter/Space opens, focus ring), restyle from tokens, and an overflow
("More") menu when the icons do not fit the window height (13 icons at 768 px).

### 7.3 Two layout modes in `PanelForm`

The mode follows the form's own width with 8 px hysteresis. Rows move between cell positions of one `QGridLayout`, so
widgets, values, parents, focus and tab order are kept.

| Mode | Width | Field | Inline (toggles, key/value) | Pairs | Help text |
|---|---|---|---|---|---|
| Stacked | < 340 px | Label above, control indented 10 px, gap 3 | Label left, control right | One label, both controls on the indented line | Muted, under the control, aligned with it |
| Side by side | ≥ 340 px | Label in an aligned column (widest label, capped at 40 % of the form, labels wrap), control right | Unchanged | Both controls in the control column | Aligned with the control column |

Bare fields, lists, output areas and editors are full width in both modes. Dialogs keep a label-beside form.

### 7.4 Allowed presentational and label changes

- Redundant labels dropped, kept as `accessibleName`, exactly the handoff list: the single field in an Input section
  (Series in Chart Properties·Style, Chart Analysis, Chart Signal Analysis, Chart Transform; Sample column in
  Statistical Tests; Signal column in Signal Analysis); the method picker in a Method section (Method in
  Preprocessing, Chart Signal Analysis, Signal Analysis; Type in Transform Operations; Test in Statistical Tests);
  Analysis Operations › Output › Result column.
- Section titles in capitals through font capitalization, sub-group titles in sentence case ("ERROR BARS" →
  "Error bars"). The inventory compares label text case-insensitively.

### 7.5 Plotting output

The chart canvas has a fixed physical size (`width_cm`/`height_cm`/`dpi`) in a non-resizable scroll area, so resizing
the sidebar only changes the viewport. One exception: the first time a chart without a stored size opens, its size is
fitted to the viewport (`_apply_initial_fit_size`), so the sidebar width and density decide the stored size of new
charts. DS-33 adds tests that (a) a sidebar resize leaves figure inches, DPI and stored size unchanged, and (b) the
first-open fit runs after the sidebar width has been restored.

## 8. Testing and verification

- **Content baseline (DS-02)**: `panel_inventory(widget)` walks a panel in a populated state (dataset or chart loaded)
  and records, in tab order: label or accessible name, role (button, combo, checkable, number, text, list, slider —
  not the class, which changes by design), enabled, visible, value, combo items, number ranges, decimals and suffixes.
  Goldens for the 13 panels and 5 Chart Properties tabs are committed **before** any token change. Each panel PR
  regenerates its golden and the diff may only show the changes in 7.4 and the tab-order exception in section 3.
- **Width**: at 240 px the panel's content widget fits without a horizontal scrollbar (asserted on the content, not
  `minimumSizeHint()` of the scroll area).
- **Components**: pytest-qt tests per state, keyboard (ring on Tab, none on mouse focus, Space/Enter activation),
  accessible names; story builds in `pandaplot_storybook/storybook_tests/test_stories_basic.py`, run in CI from DS-12.
- **Tokens and config**: contrast pairs (5.2), density resolution, the one-time migration (old defaults move, a later
  re-pick is kept), `reset_defaults()` for `density`, session restore for sidebar width/collapsed.
- **Fusion**: `grab()` cannot see the native-style bug, so DS-10 has a manual QA checklist for Windows, macOS and
  Linux in its PR and checks palette roles in tests.
- **Leaks**: popups and popovers (combo, `ChipSelect`, focus overlay) must not leave top-level widgets; #652 extends
  the check from e2e to `tests/gui` and lands before DS-14.
- Full suite with `QT_QPA_PLATFORM=offscreen`.

## 9. Issues

Labels: `ds: foundation`, `ds: component`, `ds: container`, `ds: storybook`, `ds: migration`, `ds: cleanup`, plus
existing `area:` and `effort:` labels. An epic issue holds the ordered checklist. Each issue body: goal, spec section
and handoff option id, scope, acceptance checklist, dependencies, screenshots requirement, CHANGELOG line, Closes/Refs.

Prerequisites already filed: **#585** (deleted `P*` widgets stay subscribed; fix before Phase 2 multiplies it) and
**#652** (stray top-level widget check in `tests/gui`), both added to the milestone.

### Phase 0: documentation and baselines

| Id | Title | Depends | Links |
|---|---|---|---|
| DS-01 | Commit the design handoff, image import design and this spec under `docs/design/`; ruff `extend-exclude` for the drafts; design-system issue template | – | |
| DS-02 | Panel inventory goldens for the 13 panels and 5 Chart Properties tabs | DS-01 | Refs #559, #554 |
| DS-03 | Theme test helpers: route token mocks through `ICON_TOKENS` and a theme/accent fixture | – | Closes #593 |

### Phase 1: foundation

| Id | Title | Depends | Links |
|---|---|---|---|
| DS-04 | Design tokens v2: semantic tokens with the 4.1 fixes, space/type/radius/density tables, legacy aliases, `current_tokens()`, contrast tests (5.2) | DS-03 | Closes #581 |
| DS-05 | Derived tokens for custom accents with a contrast guard | DS-04 | |
| DS-06 | New defaults with a one-time config migration: teal accent, system UI font size; wizard swatches use default series colours | DS-04 | |
| DS-07 | Density setting (`automatic`/compact/default/comfortable), font-relative type scale and control height, screen-based resolution, Settings > Appearance combo in the current dialog | DS-06 | Refs #648, #578 |
| DS-08 | Base QSS: control heights, disabled states, field error state, chip/segment fixes; delete the Storybook contrast overrides | DS-07 | Refs #591 |
| DS-09 | Complete token-driven `QPalette` (all roles and groups) under the current style | DS-04 | |
| DS-10 | Fusion style plus QSS roles for group boxes, scrollbars, splitters, tooltips, headers and wizards; cross-platform screenshot audit | DS-08, DS-09 | Closes #391 |
| DS-11 | `FocusRing` overlay (keyboard-only focus ring) | DS-04 | |
| DS-12 | Storybook infrastructure: CI job for `storybook_tests`, Tokens story first, density and width controls, state-matrix helper, story-coverage test with allowlist, offscreen screenshot script | DS-07 | Refs #580 (parked) |

### Phase 2: components

| Id | Title | Depends |
|---|---|---|
| DS-13 | `PButton` v2: ghost role, icon-only, focus ring, density height; 5 × 5 story | DS-10, DS-11, DS-12 |
| DS-14 | `DropDownComboBox`/`ValueComboBox` v2: searchable, placeholder, mixed, popup placement | DS-10, DS-11, DS-12, #652 |
| DS-15 | `SliderWithSpinbox` v2: painted slider, unit suffix, mixed, commit signal | DS-10, DS-11, DS-12 |
| DS-16 | Text and number fields and `OutputArea` | DS-10, DS-11, DS-12 |
| DS-17 | Checkbox and radio indicators from the icon bundle | DS-10, DS-12 |
| DS-18 | `SegmentedControl` and `ToggleSwitch` restyle | DS-10, DS-11, DS-12 |
| DS-19 | Token pickup for the remaining shared widgets (section 6 list) | DS-12 |
| DS-20 | Toolbar style role for `QToolBar` and tool buttons | DS-13 |
| DS-21 | `CheckList` and `SingleList` | DS-17 |
| DS-22 | `ChipSelect` | DS-21, #652 |
| DS-23 | `DualList` | DS-21, DS-13 |

### Phase 3: containers

| Id | Title | Depends |
|---|---|---|
| DS-24 | `Card` v2 and `SubGroup` | DS-13 |
| DS-25 | `CollapsibleSection` (header toggle, ghost action, modified/Reset); `SectionHeader` QSS role | DS-18, DS-24 |
| DS-26 | `PanelForm` with stacked and side-by-side modes | DS-24 |
| DS-27 | Underline tab variant with overflow scrolling | DS-11 |
| DS-28 | `PanelShell`, `PanelFooter`, restyled `DirtyFooter` | DS-13, DS-25 |
| DS-29 | `DialogScaffold` | DS-13, DS-16 |
| DS-30 | `PRailTabs` and `PNavDialog` | DS-29 |
| DS-31 | `PStepDialog` on `PWizard` with one shared step rail and footer | DS-29 |
| DS-32 | Storybook gate: composed showcase stories (side panel at 240/300/360/480 px, Chart Properties Axes, Settings, wizard step, small dialog) built only from the new parts and compared with Step 5/6; all component stories pass in CI | DS-13…DS-31 |

### Phase 4: sidebar shell

| Id | Title | Depends | Links |
|---|---|---|---|
| DS-33 | Sidebar sizing: per-panel floor, visible handle, no snap, 50 % maximum, session-persisted width and collapsed state, `Ctrl+B`, plot-size tests | DS-32 | Closes #225; Refs #515 |
| DS-34 | Icon bar: keyboard navigation, restyle, overflow menu | DS-32 | Refs #562 |
| DS-35 | `SidebarPanel` base adopts `PanelShell` (title band, scroll body, footer slot); Project Explorer, Search and Chart Properties keep working through `main_layout` | DS-32, DS-02 | |

### Phase 5: side panels (one PR each; Step 6 anchor `#pNN`)

Every row depends on DS-35 and the components it lists. Compare against Step 6 AFTER at 260 and 300 px (stacked
mode); at 480 px only label placement differs. Keyboard: Tab order top to bottom, ring visible, sections toggle with
Space/Enter. Panels touching the same files as per-tab context work (#542, #548, #456) coordinate merge order.

| Id | Panel (Step 6) | Details from Step 6 | Extra depends |
|---|---|---|---|
| DS-36 | 01 Project Explorer | Project info row (name + "Unsaved project"); selected tree row `accent_sel_bg/text` 600 | |
| DS-37 | 02 Search Notes | Aa / W / .* toggle chips (selected `accent_sel_bg` + accent border); search highlight colours to tokens | DS-19 |
| DS-38 | Chart Properties shell | Underline tabs replace the combo fallback; one scroll body (no nested `QScrollArea` per tab); `DirtyFooter` in the shell footer | DS-27 |
| DS-39 | 03 Chart Properties · Chart | | DS-38 |
| DS-40 | 04 Data (a): series list and cards | "+ Add series" ghost action in the section header; series header row with ↑ ↓ × icon buttons | DS-38 |
| DS-41 | 04 Data (b): series detail form | "Error bars" and "Confidence band" sub-groups | DS-40 |
| DS-42 | 05 Style (a): chart-level sections | Font size, Padding, Size, DPI, Background | DS-38, DS-15 |
| DS-43 | 05 Style (b): series sections | Line, Fill, Band, Markers, Error bars, Twin Y, Value labels, Density; header toggles (Fill, Markers, Value labels); approved label: Series | DS-42 |
| DS-44 | 05 Style (c): type-specific sections | Vector, Box, Pie, Heatmap, axis style form | DS-43 |
| DS-45 | 06 Axes | "Auto range" on disables Min/Max (`border_subtle`, `text_disabled`) | DS-38, DS-18 |
| DS-46 | 07 Legend | Header toggles (Legend, Frame) | DS-38 |
| DS-47 | 08 Curve Fitting | Auto range disables Min/Max; monospace Equation; remove the combo minimum widths | Refs #528 (land first if ready) |
| DS-48 | 09 Chart Analysis | Start/End hint text inside fields; owns the shared `series_source_picker`; approved label: Series | DS-16 |
| DS-49 | 10 Chart Signal Analysis | Start/End hints; approved labels: Series, Method | DS-48 |
| DS-50 | 11 Chart Transform | Code row with "Insert function" dropdown and "?" button; approved label: Series | DS-48 |
| DS-51 | 12 Transform Operations | Info row, "Source columns" sub-group then `SingleList`; code row as DS-50; approved label: Type | DS-21 |
| DS-52 | 13 Preprocessing | `CheckList` + "Select all" ghost action; monospace Formula; approved label: Method | DS-21 |
| DS-53 | 14 Analysis Operations | Start/End hints; approved label: Result column | |
| DS-54 | 15 Descriptive Statistics | `CheckList` + "Select all"; primary enabled at rest; status "1 column selected" | DS-21 |
| DS-55 | 16 Statistical Tests | Approved labels: Sample column, Test | DS-18 |
| DS-56 | 17 Signal Analysis | Approved labels: Signal column, Method | |

### Phase 6: dialogs

| Id | Title | Depends | Links |
|---|---|---|---|
| DS-57 | Settings → `PNavDialog` (General / Appearance / Editor; Appearance holds Theme, Accent, Density, font size) | DS-30, DS-07 | Refs #544 |
| DS-58 | Chart Wizard → `PStepDialog` | DS-31 | coordinate with #651, #496 |
| DS-59 | Measurement analysis wizard → `PStepDialog` | DS-31 | |
| DS-60 | `ImportImagesCommand` takes prepared payloads; `redo()` replays without downloading again or minting new ids (bug, regression test) | – | |
| DS-61 | Image import queue service (local): supported-format check, duplicate check against the target gallery, folder expansion, per-item status | DS-60 | |
| DS-62 | Image URL download worker: background thread, progress, cancel, timeout, size limit; results applied on the main thread | DS-61 | |
| DS-63 | Image import dialog 1e (scope below) | DS-62, DS-29, DS-27, DS-17 | |
| DS-64 | Data import dialog on `DialogScaffold` (single page kept) | DS-29 | Refs #545 |
| DS-65 | Rename and confirm dialogs: replace the 6 `QInputDialog.getText` calls; `UiController` error/warning/info message boxes on the scaffold | DS-29 | Refs #501 |
| DS-66 | Small item dialogs: New Dataset, Add Rows/Columns, About, Snapshot DPI, Gallery Destination Picker, Add Series | DS-29 | |
| DS-67 | Create or Open Project and Project Details | DS-29 | |
| DS-68 | `BaseAnalysisDialog` (Derivative, Integral, Smoothing) onto `PDialog` + scaffold | DS-29 | |
| DS-69 | Explore Data, Create Visualization, statistics test info dialog | DS-29 | |
| DS-70 | Note pickers: image, table, chart | DS-29 | |
| DS-71 | Note Artefacts and Export Sketch | DS-29 | |
| DS-72 | Examples dialog and example cards | DS-29 | Refs #650 |
| DS-73 | Help window and Getting Started steps | DS-29 | Refs #582, #650 |
| DS-74 | Image editor and lightbox | DS-29 | |
| DS-75 | Every dialog fits a 1280×720 available area (audit; scroll or resize the ones that do not, e.g. Project Details 640×720, Import 720×540, Measurement 780×560) | DS-57…DS-74 | |

**DS-63 scope (1e):** "From files" / "From URL" underline tabs sharing one queue. From files: drop zone ("Drop images
or folders here") with Browse… and Add folder…. From URL (not drawn in the mock): URL field + Add button that appends
to the queue. Queue header "n in queue · n problem(s)" with Remove problems and Clear all. Rows: thumbnail ("URL"
placeholder for URL items, "!" for errors), name, "size · width×height", progress bar + "Downloading n%",
"Already in this gallery — will be skipped" (`warning`), "Unsupported format" (`danger`), ✕ on every row. "Import into"
combo (label beside) including a new-gallery entry. "Copy files into project" checkbox, checked by default, with the
line "Off: images stay linked and break if the originals move." Footer summary "n will import, n skipped, n
downloading"; Cancel stops downloads; primary "Import N images", disabled when N is 0.

### Phase 7: main area and chrome

| Id | Title | Depends | Links |
|---|---|---|---|
| DS-76 | Main tab bar, tab header menu and floating tab window | DS-32 | Refs #562 |
| DS-77 | Menu bar, menus and context menus from tokens (one app-wide `QMenu` rule replaces `build_context_menu_stylesheet`); menus stay plain text | DS-08 | |
| DS-78 | Visible splitter handles everywhere else: tab container panes, note editor, sketch layers, help window | DS-33 | |
| DS-79 | Dataset tab: table, headers, delegates, action row | DS-20 | |
| DS-80 | Chart tab: editor toolbar, navigation toolbar, status frame, empty state | DS-20 | Refs #583 |
| DS-81 | Note tab: editor toolbar and preview | DS-20 | |
| DS-82 | Sketch tab: tool bar, property bar, layer panel | DS-20 | |
| DS-83 | Image gallery tab: token and component restyle only | DS-20 | |
| DS-84 | Welcome tab restyle | DS-32 | Refs #281 |

### Phase 8: cleanup

| Id | Title | Depends |
|---|---|---|
| DS-85 | Guard test: no hex colour literals or widget-local `setStyleSheet` in `pandaplot/gui` outside an allowlist (chart data colours); docs (ARCHITECTURE theming section, AGENTS.md design-system rules) | all migration |
| DS-86 | Remove `SectionHeader`, legacy token aliases and `get_surface_palette()` | all migration |

## 10. Out of scope

- Image gallery redesign (options 1c/1d): a later design pass.
- Removing Apply/Revert from Chart Properties: #332 (footer slot keeps it simple).
- Panel content changes beyond 7.4; new panel features.
- Moving the Storybook onto `pyside6-storybook`: #580, parked until this milestone closes.
- Native file and colour pickers (`QFileDialog`, `QColorDialog`) stay native.
- Status bar and notifications redesign: #277. Welcome window redesign: #281 (DS-84 restyles only).
- A high-contrast theme.

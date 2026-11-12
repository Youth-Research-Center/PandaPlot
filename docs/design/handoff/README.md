# Handoff: PandaPlot component system + side-panel restyle

## Overview
A unified component system for PandaPlot (PySide6): design tokens, 15 shared widgets restyled or added, dialog/tab/panel-shell patterns, multi-select lists, and the restyle of all 17 side panels. Goal: one consistent look in light and dark, visible keyboard focus, WCAG-AA contrast, and a single place (tokens + QSS) that drives styling.

**Hard rule: styling only.** No panel may change its sections, fields, values, order or buttons — except the approved "redundant label" removals listed in Task 9.

## About the design files
`design_files/*.dc.html` are **design references built in HTML** — open them in a browser to see every option, state and theme. They are not code to ship. Recreate them in PandaPlot's existing stack: **PySide6 widgets + global QSS from `ThemeManager.build_stylesheet`**, following the repo's patterns (dynamic properties like `[primary="true"]`, `set_tokens()` on widgets, stories in `pandaplot_storybook`).

The `0N_*/` folders contain **draft Python** written against the repo layout but **never executed**. Treat it as a strong starting point: fix imports, adapt to real signatures, keep public APIs backward-compatible.

## Fidelity
**High-fidelity.** Colours, sizes, radii, spacing and states are final. Match them exactly. Where QSS can't express something (focus ring outside the border), use the helper described.

## Repo map (what changes)
| Repo path | Change |
|---|---|
| `pandaplot/services/theme/theme_manager.py` | New token set + appended QSS blocks; expose `current_tokens()` |
| `pandaplot/gui/components/common/p_button.py` | Replace (3a roles + FocusRing) |
| `.../common/slider_with_spinbox.py` | Replace (3d) |
| `.../common/value_combo_box.py` | Replace; absorbs `drop_down_combo_box.py` (delete after) |
| `.../common/card.py`, `section_header.py` | Replace with Card (2b) / CollapsibleSection (2d) |
| `.../common/` new files | `containers.py`, `navigation.py`, `multiselect.py`, `panel_form.py`, `focus_ring.py` |
| `.../common/segmented_control.py`, `chip_row.py`, `toggle_switch.py` | Restyle only (selected = `accent_sel_bg/text`; toggle focusable) |
| `pandaplot_storybook/` | Tokens story; state-matrix stories per component; remove local contrast overrides |
| side panels under `pandaplot/gui/` | Rebuild bodies with `PanelForm` (Task 9) |

---

## Tasks (do in order; one PR each)

### Task 1 — Tokens + base QSS
Source: `01_tokens/design_tokens.py`, `01_tokens/README.md`. Reference: `Step 1 - Tokens and Audit` (picks 1bL/1bD, 1eL/1eD, 1hL/1hD, Default density).
- Replace `get_design_tokens()` body; keep legacy keys mapped (list in file) so untouched widgets still work.
- Merge base rules: control height, focus, disabled, chip/segment fixes.
- Add `current_tokens()` accessor.
- Delete Storybook-local contrast overrides in `color_contrast.py`; extend `test_color_contrast.py` to all 7 pairs × 2 themes.
- Add `tokens_story.py`.

**Acceptance**
- [ ] App launches in light and dark; accent is teal `#0E7C86` / `#11808A`.
- [ ] Contrast test passes: text/surface ≥4.5, muted/surface ≥4.5, on_accent/accent ≥4.5, sel_text/sel_bg ≥4.5, danger/surface ≥4.5, border_control/surface ≥3, focus/surface ≥3.
- [ ] No widget visually broken (legacy keys resolve).

### Task 2 — FocusRing
Source: `04_controls/controls.py` (`FocusRing`), `01_tokens/README.md` § Focus ring.
- Keyboard-only (Tab/Backtab/Shortcut focus reasons). 2px `focus` colour, 1px outside the control, radius = control radius + 2. **Border colour never changes on focus.**
- Destructive buttons use `danger` for the ring.

**Acceptance**
- [ ] Tabbing through a panel shows a ring on every button, field, combo, spinbox; mouse click shows none.
- [ ] Ring never clips (reserve 3px via parent spacing/margins).

### Task 3 — Controls
Source: `04_controls/`. Reference: `Step 3 - Controls` (3a, 3d, 3g; 3i as `searchable=True`).
- `PButton(text, role="primary|secondary|ghost|destructive", icon=False, on_click=None, enabled=True)`; height = `control_h` (26).
- `SliderWithSpinbox(min, max, step, decimals, unit)`; 4px track, 14px knob (2px accent border when hover/pressed), 58px spinbox with unit suffix, no arrows; `set_mixed()` → "—", fill/knob hidden.
- `ValueComboBox(items, searchable=False, placeholder="")`; popup always opens below; selected row `accent_sel_bg/text`, hover `bg_inset`; `currentValue()/setCurrentValue()`; `set_mixed()` → italic "Mixed".
- Delete `drop_down_combo_box.py` after replacing usages.

**Acceptance**
- [ ] Storybook PButton story shows 5 roles × 5 states (rest/hover/pressed/focus/disabled) matching Step 3 · 3a.
- [ ] A row with button + combo + spinbox aligns to one 26px height.
- [ ] Slider identical on Windows/macOS/Linux (no native groove).

### Task 4 — Containers
Source: `02_containers/`. Reference: `Step 2 - Containers A` (2b, 2d, 2h).
- `Card`: bg_inset, transparent 1px border reserved; selected = accent_sel_bg + accent border; margins 12, spacing 6. No layout shift between states.
- `CollapsibleSection(title)`: CAPS 10.5px/700/1px letter-spacing, left arrow; accent 6px dot + "Reset" ghost when modified; "Reset" also on hover; optional right-side toggle or action.
- `SubGroup(title)`: 11.5px/600 `text_secondary` + `border_subtle` hairline; no indent.

**Acceptance**
- [ ] `ContainersStory` matches Step 2A states in both themes.

### Task 5 — Navigation, shell, dialogs
Source: `03_navigation/`. Reference: `Step 2 - Containers B`.
- `PTabWidget` (2j underline) everywhere; `PRailTabs` (2l) **Settings only**.
- `PanelShell(title)` (2m): header (title 13/600 + close), scroll body (header divider appears once scrolled), always-visible `DirtyFooter` (buttons disabled when clean; status text hidden <300px).
- Dialogs **by purpose**: `PDialog` small/confirm (2p) · `PNavDialog` Settings (2q) · `PStepDialog(steps)` Chart Wizard & Import (2r). Shared title 15/600, margins 14, footer with platform button order.

**Acceptance**
- [ ] Chart Properties uses PTabWidget; Settings uses PNavDialog; Chart Wizard uses PStepDialog with Back/Next/Finish + step dots (done=accent fill ✓, current=sel_bg + accent border, todo=border_control).

### Task 6 — Multi-select
Source: `05_multiselect/`. Reference: `Step 4 - Multi-select` (4a1, 4b2, 4c1).
- `CheckList`: tri-state "All", checkbox-only state (no row tint), count "n of N".
- `ChipSelect`: single 26px line, chips `accent_sel_bg/text`, "+N" overflow, popover = filter + CheckList; Backspace removes last.
- `DualList`: Available | › ‹ » | Selected (drag to reorder). **Dialogs only (≥280px).**
- Add `:/icons/check-white.svg`, `:/icons/dash-white.svg`.
- `ChipRow`: replace hardcoded `#FFFFFF` selected text with `accent_sel_text` on `accent_sel_bg`.

### Task 7 — Restyle remaining widgets
`SegmentedControl` (selected = sel_bg/sel_text 600, inner radius 3, remove leaking `border-left` rule, no width shift on select), `ToggleSwitch` (focusable, Space toggles, off track `toggle_off`, knob `knob`, disabled = accent_disabled), `ColorSwatchRow`, `LineStylePicker`, `BusySpinner` pick up tokens only.

### Task 8 — Storybook coverage
One story per component with a **state matrix** (not single instance) and a Light/Dark toggle. Tokens story first in the list.

### Task 9 — Side panels (one PR per panel)
Source: `06_panel_layout/`. Reference: `Step 6 - Panels Before After` (AFTER column; Tweaks switch theme and 260/360 width).
Opened directly in a browser, the file has no Tweaks panel and shows the defaults (Dark, 260 px). To see another variant, run this in the browser's developer console: `__dcSetProps(__dcRootName(), {theme: "Light", width: "360"})` (`theme`: `"Dark"` or `"Light"`; `width`: `"260"` or `"360"`).
- Structure: `PanelShell` → (`PTabWidget`) → `CollapsibleSection` → `Card` → `PanelForm`.
- Row rules: label above + control indented 10px; toggles & key/value inline; paired fields share one line; help text muted 11px aligned to control; sub-groups via `SubGroup`; lists/outputs full-width.
- Lists: has "Select all" → `CheckList`; single-select → `SingleList` (highlighted row, no checkbox).
- **Approved content exception — drop label + indent (keep as accessibleName):** single Series field in Input (Chart Properties·Style, Chart Analysis, Chart Signal Analysis, Chart Transform); Sample column (Statistical Tests); Signal column (Signal Analysis); Method (Preprocessing, Chart Signal Analysis, Signal Analysis); Type (Transform Operations); Test (Statistical Tests); Result column (Analysis Operations › Output).
- Checklist of all 17 panels in `06_panel_layout/README.md`.

**Acceptance (per panel)**
- [ ] Side-by-side with Step 6 AFTER at 260 and 360px, light and dark — matches.
- [ ] Same sections/fields/values/order/buttons as BEFORE (diff only the approved labels).
- [ ] Keyboard: Tab order top→bottom, ring visible, sections toggle with Space/Enter.

---

## Design tokens (final)
| Token | Light | Dark |
|---|---|---|
| bg_canvas | #FBFBFC | #1F2123 |
| bg_surface | #FFFFFF | #2A2C2E |
| bg_inset | #F4F5F8 | #242628 |
| border_panel | #E5E6EA | #3A3D40 |
| border_control | #C9CDD5 | #5A5E64 |
| border_subtle | #ECEEF2 | #33363A |
| text_primary | #1C1E26 | #E2E2E2 |
| text_secondary | #3F4350 | #C7CAD1 |
| text_muted | #6B7280 | #A3A9B3 |
| text_disabled | #AEB2BC | #5B6270 |
| danger | #C82333 | #F07171 |
| toggle_off | #C9CDD5 | #4A4D52 |
| knob | #FFFFFF | #E8E9EB |
| accent | #0E7C86 | #11808A |
| accent_hover | #0B6C75 | #14909B |
| accent_pressed | #095C63 | #0C6E77 |
| accent_sel_bg | #E3F4F5 | #163A3E |
| accent_sel_text | #0A5F67 | #8FDDE3 |
| focus | #0E7C86 | #3FB6C1 |
| on_accent | #FFFFFF | #FFFFFF |
| accent_disabled | mix(accent, bg_surface, 0.55) | same |

- **Radius:** control 4 · inner (segment) 3 · chip 4 · card 6
- **Density (default):** control_h 26 · pad_x 8 · button_pad_x 12 · row_gap 6 · font 12px. Compact 22/6/10/4/12, Comfortable 30/10/14/8/13.
- **Space:** 2 · 4 · 6 · 8 · 12 · 16 · 24
- **Type (px):** caption 11 · label/value 12 · section 10.5 (700, +1px tracking, CAPS) · sub-group 11.5 (600) · panel title 13 (600) · dialog title 15 (600). UI font = system (Segoe UI / SF / system-ui).
- **Shadows:** none (QSS can't; borders/fills only). Dialog chrome shadow comes from the OS.
- **Known follow-up:** default chart series colour 3 `#2B7A8C` is close to teal — nudge (e.g. `#2F6FB0`).

## Assets
- New: `check-white.svg`, `dash-white.svg` (10px, white glyphs) for checkbox indicators.
- No other images/icons introduced; existing icons unchanged.

## Files
- `README.md` (this file) · per-task `0N_*/README.md` + draft `.py`
- `design_files/Step 1 - Tokens and Audit.dc.html` — audit + token options (picked: 1bL/1bD, 1eL/1eD, 1hL/1hD)
- `design_files/Step 2 - Containers A.dc.html` — Card / Section / Sub-group (picked 2b, 2d, 2h)
- `design_files/Step 2 - Containers B.dc.html` — Tabs / Shell / Dialogs (picked 2j + 2l Settings, 2m, 2p/2q/2r by purpose)
- `design_files/Step 3 - Controls.dc.html` — PButton / Slider / Dropdown (picked 3a, 3d, 3g + 3i)
- `design_files/Step 4 - Multi-select.dc.html` — CheckList / ChipSelect / DualList (picked 4a1, 4b2, 4c1)
- `design_files/Step 5 - Unified Screens.dc.html` — showcase (sample content, not a spec)
- `design_files/Step 6 - Panels Before After.dc.html` — **the panel spec**: all 17 panels, before vs after
- Open any `.dc.html` directly in a browser (keep `support.js` alongside).
- `screenshots/*.png` — full-page captures of each design file (1x) for quick reference without a browser. Step 6 is captured in dark at 260px; open the HTML to switch theme/width.

## Suggested Claude Code prompts
1. "Read `design_handoff_components/README.md`. Do **Task 1** only. Keep legacy token keys working. Run the app and `pytest`. Show me the acceptance checklist results."
2. Repeat per task: "Do **Task N** from the handoff README…"
3. Panels: "Do **Task 9** for panel *16 Statistical Tests*. Compare against `design_files/Step 6 - Panels Before After.dc.html` #p16 AFTER. Don't change content beyond the approved label list."

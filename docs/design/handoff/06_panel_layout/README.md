# Step 6 — Panel layout rules (approved)

Applies to every side panel (260–360px). Visual reference: `Step 6 - Panels Before After.dc.html` (AFTER column).

## Scope
Styling only. Every panel keeps its sections, fields, values, order and buttons. One approved exception: redundant labels (below).

## Structure per panel
`PanelShell` (2m) → `PTabWidget` if tabbed (2j) → per section `CollapsibleSection` (2d, CAPS title, toggle or ghost action on the right) → `Card` (2b inset) → `PanelForm`.
A section with a toggle and no rows renders header only (chevron ▸).

## Row rules (`PanelForm`)
| Row | Layout |
|---|---|
| Field (dropdown, text, number, slider, colour, segmented) | Label above, control on its own line, **indented 10px**, label→control gap 3px, row gap 8px |
| Toggle, read-only key/value | **Inline**: label left, control right |
| Paired fields (Range min/max) | One label, both controls share the indented line |
| Help text | Muted 11px under its field, aligned with the control (no indent if the field is bare) |
| Sub-group (ERROR BARS, NUMERIC COLUMNS…) | 2h: sentence-case label + hairline, optional ghost action ("Select all") |
| Lists, output areas, code editor, tree | Full width, no label |

## Redundant labels (approved exception)
Drop the label — and the indent — when it only repeats the section or panel title. Keep it as `accessibleName`.
- Single field in an **Input** section: Series (Chart Properties·Style, Chart Analysis, Chart Signal Analysis, Chart Transform), Sample column (Statistical Tests), Signal column (Signal Analysis)
- Method picker in a **Method** section: Method (Preprocessing, Chart Signal Analysis, Signal Analysis), Type (Transform Operations), Test (Statistical Tests)
- Analysis Operations › Output › Result column

## Lists
- Has "Select all" (multi-select) → `CheckList` (4a1): Preprocessing, Descriptive Statistics
- Single-select → `SingleList`, highlighted row, no checkboxes: Transform Operations › Source columns

## Footer
Status text shown at ≥ 300px, hidden at 260px (unchanged rule). Secondary = 3a outlined, disabled when nothing to act on; primary = 3a solid, `accent_disabled` when disabled.

## Apply
1. Add `panel_form.py` next to `containers.py`; append `panel_form_qss(tokens)` to `build_stylesheet`.
2. Rebuild each panel's body with `PanelForm` (see `build_statistical_tests` example).
3. Update the panel's status in Step 6 (`STATUS` map) as it lands.

## Migration checklist (Step 6 order)
- [ ] 01 Project Explorer
- [ ] 02 Search Notes
- [ ] 03–07 Chart Properties · Chart / Data / Style / Axes / Legend
- [ ] 08 Curve Fitting
- [ ] 09 Chart Analysis
- [ ] 10 Chart Signal Analysis
- [ ] 11 Chart Transform
- [ ] 12 Transform Operations
- [ ] 13 Preprocessing
- [ ] 14 Analysis Operations
- [ ] 15 Descriptive Statistics
- [ ] 16 Statistical Tests
- [ ] 17 Signal Analysis

# Step 2B — Tabs, panel shell, dialogs (approved)

| Use | Component | Option |
|---|---|---|
| Chart Properties, Wizard pages, any in-panel tabs | `PTabWidget` | 2j underline |
| Settings only | `PRailTabs` | 2l vertical rail |
| Every side panel | `PanelShell` | 2m classic footer (wraps existing `DirtyFooter`) |
| Small dialogs, confirms, rename, export | `PDialog` | 2p standard |
| Settings, large multi-section dialogs | `PNavDialog` | 2q sidebar nav (shares 2l rail style) |
| Multi-step flows: New chart wizard, Import | `PStepDialog` | 2r stepper |

All three dialogs share one base (`PDialog`): same title, margins, footer, and button order — they differ only in the middle (plain / nav / stepper), so they still read as one family.

## Apply
1. Add `navigation.py` to `gui/components/common/` (adjust the two relative imports).
2. Append `nav_qss(tokens)` to `ThemeManager.build_stylesheet`.
3. Migrate: Chart Properties `QTabWidget` → `PTabWidget`; side panels → `PanelShell`; Chart Wizard → `PStepDialog`; Settings → `PNavDialog`.
4. Storybook: one story per class with the states from Step 2B (selected/hover/focus/disabled/overflow; clean/dirty/scrolled; default/validation error).

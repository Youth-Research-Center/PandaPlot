# Panel inventory goldens

Each `.txt` file records what one side panel or Chart Properties tab contains: one line per control, in focus-chain
(Tab) order, written by `panel_inventory()` in `tests/gui/panel_inventory.py`:

```
role | "label or accessible name" | value=... items=[...] range=a..b decimals=n suffix="..." hidden disabled
```

Roles describe what a control does, not its class: `button`, `checkable`, `combo`, `choice` (segmented control),
`number`, `slider`, `text`, `list`, `color`, `tabs`, `group` and `label`. A label that names a form field is not listed
on its own; it appears as that field's label. `hidden` and `disabled` are relative to the panel, so a control inside
a collapsed or inactive section is still recorded. Scroll bars, and the Chart Properties tab selector combo that
replaces the tab bar only when the tabs do not fit, depend on the window size and are left out.

`tests/e2e/test_panel_inventory_goldens.py` builds the panels in the real window with a fixed project (dataset
`Measurements` and line chart `Signal over time`): the dataset tab is active for the dataset panels, and the chart tab
for the chart panels and the five Chart Properties tabs. Label text is compared case-insensitively. Everything else,
including values, items and order, must match exactly.

## When a migration PR changes a panel

1. Regenerate the goldens:

   ```bash
   PANDAPLOT_UPDATE_GOLDENS=1 QT_QPA_PLATFORM=offscreen uv run pytest -n 0 tests/e2e/test_panel_inventory_goldens.py
   ```

2. Review `git diff tests/e2e/panel_inventory/`. The diff may only contain the changes the design-system spec allows
   (`docs/design/design-system.md`):
   - a redundant label dropped and kept as the control's accessible name, for the fields listed in §7.4: a separate
     `label` line may disappear, and the field's own line then carries that text as its label;
   - tab-order moves caused by `PanelShell`'s close button and footer (§3);
   - a role change where a control is replaced by one with the same content, for example a column list becoming a
     check list. The items, values and order stay the same.

   Anything else (a missing or renamed field, a changed default, range, decimals, suffix or combo item, a reordered
   control) is a content change and does not belong in a migration PR.
3. Commit the regenerated goldens with the migration and list the remaining differences in the PR description.

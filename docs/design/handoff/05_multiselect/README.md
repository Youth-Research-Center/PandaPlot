# Step 4 — Multi-select (approved: recommended)

| Use | Component | Option |
|---|---|---|
| Series visibility, legend entries, layers — short lists that stay on screen | `CheckList` | 4a1 plain rows |
| Filters / "apply to" pickers in dense side panels | `ChipSelect` | 4b2 single line, "+N" |
| Ordered or long selections — wizard Y columns, export order. **Dialogs only (≥ 280px)** | `DualList` | 4c1 arrow buttons |

`ChipSelect` reuses `CheckList` in its popup, so 4a and 4b share one row delegate and checkbox style.
`ChipRow` (single-select) stays for now; its selected style should switch from hardcoded `#FFFFFF` to `accent_sel_bg` / `accent_sel_text` to match chips here.

## Apply
1. Add `multiselect.py` to `gui/components/common/`.
2. Add `:/icons/check-white.svg` and `:/icons/dash-white.svg` (10px glyphs) to resources.
3. Append `multiselect_qss(tokens)` to `build_stylesheet`.
4. Storybook: `CheckList` (none / partial / all / disabled), `ChipSelect` (empty / overflow / open), `DualList` (empty / partial / reorder).

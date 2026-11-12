# Step 3 — Controls (approved: recommended)

- **3a PButton** — solid primary, outlined secondary/icon, ghost = accent text, destructive = red outline. Height = `control_h`.
- **3d SliderWithSpinbox** — styled 4px track + 14px knob; 58px spinbox, no arrows, unit suffix; `set_mixed()` hides fill/knob and shows "—"; `step` snaps both.
- **3g ValueComboBox** — outlined field, popup always below, selected row `accent_sel_bg`, hover `bg_inset`. `DropDownComboBox` is merged in — delete it after migration. `searchable=True` = 3i variant for long lists.
- **FocusRing** — keyboard-only 2px ring 1px outside the control; borders never change on focus. Attach to PButton, fields, combos, slider spinbox.

## Apply
1. Replace `p_button.py`, `slider_with_spinbox.py`, `value_combo_box.py` with the classes in `controls.py` (APIs compatible: `PButton(text, role=…, on_click=…, enabled=…)`, `currentValue()`).
2. Expose `current_tokens()` from `ThemeManager` (used by FocusRing colour).
3. Append `controls_qss(tokens)` to `build_stylesheet`.
4. Storybook: extend `p_button_story.py` with the 5-role × 5-state grid; add mixed/disabled toggles to slider and combo stories.

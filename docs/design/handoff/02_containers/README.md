# Step 2A — Containers (approved)

- **2b Card**: bg_inset fill, transparent 1px border reserved; hover tints, selected = accent_sel_bg + accent border, focus = focus border. Margins 12, spacing 6.
- **2d CollapsibleSection**: uppercase 10.5px/700/1px label, left arrow, accent 6px dot + "Reset" when modified, "Reset" also on hover. Replaces `SectionHeader` + manual show/hide.
- **2h SubGroup**: 11.5px/600 text_secondary label + border_subtle hairline; no indent.

## Apply
1. Replace `gui/components/common/card.py` with `Card` from `containers.py` (API compatible: `Card()` still works).
2. Add `CollapsibleSection`, `SubGroup` to `gui/components/common/`.
3. Append `containers_qss(tokens)` to `ThemeManager.build_stylesheet`.
4. Register `ContainersStory` in the Storybook.

Note: with 2b, cards inside sections sit on bg_surface panels; in light the inset (#F4F5F8) vs canvas (#FBFBFC) step is small — place cards on bg_surface, not bg_canvas.

## Scope rule — styling only
Migration must not change panel **content**: keep every existing section, field, label text and ordering. Only swap widgets for their styled equivalents (Card, CollapsibleSection, SubGroup, PButton, …) one-for-one. The screens in "Step 5 - Unified Screens" are a showcase with sample content, not a spec for panel contents.

## Label layout (side panels)
Side panels (260–360px): label above, control on its own line, indented 10px (`QVBoxLayout` per row, spacing 3; control row `contentsMargins(10,0,0,0)`). Paired fields (Range min/max) share the control line.
Dialogs (Settings, Wizard, small dialogs): label beside control (`QFormLayout`, label column fixed).

## Approved content exception — redundant labels
Drop a field's label (and its indent) when it only repeats the section or panel title: the single field in an **Input** section (Series, Sample column, Signal column) and the method picker inside a **Method** section (Method, Type, Test). Also Analysis Operations › Output › Result column. Applies to: Chart Properties·Style, Chart Analysis, Chart Signal Analysis, Chart Transform, Transform Operations, Preprocessing, Analysis Operations, Statistical Tests, Signal Analysis. Keep the label as the field's accessible name (`setAccessibleName`).

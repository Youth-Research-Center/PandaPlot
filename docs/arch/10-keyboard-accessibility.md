# Keyboard focus and accessible controls

Status: proposal for review, not an implemented accessibility fix.

Related: [#339](https://github.com/Youth-Research-Center/PandaPlot/issues/339).
This document addresses the request for an app-wide approach before changing
ToggleSwitch. It does not close #339 or claim screen-reader validation.

## Current gaps

The audit uses main at `22e9158` (September 30, 2026).

- `gui/components/common/toggle_switch.py` paints a bare QWidget. It has no
  focus policy or key handler and stores checked state separately from Qt's
  button model. Existing tests only check knob coordinates.
- `PButton` inherits QPushButton and already has Qt button behavior. Focus
  support should be preserved rather than replaced with app-wide key routing.
- `sidebar/icon_bar.py` creates panel buttons from icon text. Semantic names
  need to be supplied independently of the displayed glyph.
- `StyleTab._field_row` places a QLabel beside a field without a buddy or
  accessible-name association. Repeated labels such as "Match line" also need
  the group context, for example "Markers: match line color".
- `PanelArea.show_panel` switches the stacked widget; sidebar collapse hides
  it. There is no explicit focus handoff for these transitions.
- ThemeManager's global stylesheet has no explicit `:focus` rules. A custom
  painted control cannot rely on Qt drawing a focus indicator for it.

An offscreen check of the current ToggleSwitch reports `NoFocus`, accessible
`Role.Client`, no checkable state and no name. Space does not toggle it.
A stock QCheckBox reports `Role.CheckBox`, checkable state and the supplied
text as its name; Space updates both its value and accessible checked state.
These are Qt interface checks, not tests with a native screen reader.

## Ownership

| Layer | Responsibility |
| --- | --- |
| Shared controls | Focus policy, activation, state, role and focus rendering |
| Form/panel builders | Context-specific names, label buddies and local tab order |
| Sidebar/tab containers | Focus handoff when content changes or disappears |
| ThemeManager | Visible focus treatment in light and dark themes |
| Tests and manual checks | Traversal, signals, accessible interface and platform behavior |

Keep WidgetExtension's event-subscription lifecycle unchanged. Keyboard focus
is a widget concern, not a reason to make decorative containers focusable or
change EventBus subscriptions. Do not add a global filter that intercepts
Space, Enter, Tab or arrow keys: it would conflict with text editors, table
editing, menus and Qt's dialog handling.

## Shared ToggleSwitch

Use a QCheckBox-derived control with the existing pill paint treatment.
QCheckBox supplies Qt's checkable role, checked-state model and button
activation. A generic QWidget with only `setAccessibleName` is insufficient:
it still lacks the checkable semantics required by #339.

- Retain the `checked=` constructor, `isChecked()`, keyword-compatible
  `setChecked(checked=...)`, `toggled(bool)` and `set_tokens()` contract.
  Use Qt's checked state as the single source of truth; do not keep `_checked`
  or a second signal. Existing signal-blocked model-to-view updates must work.
- Use StrongFocus so the switch can be reached by Tab and mouse focus.
  Let Qt handle Space, clicks and disabled behavior. Add explicit Enter and
  keypad Enter activation, consume those events so a parent dialog's default
  action does not fire, and ignore key auto-repeat for that activation.
- Preserve the pill appearance, but allow room for a visible focus ring.
  Repaint on focus changes. Check the new size and clipping in existing forms,
  at high DPI and in both themes before landing the change.
- Keep disabled controls non-interactive and expose their disabled state.
  Calling `setChecked` programmatically still emits only on an actual change.
- Require a meaningful accessible name at each use. Where a visible label is
  available, use it as the source; for repeated fields include the section
  context. Do not give all switches the same fallback name "Toggle".

This changes a QWidget subclass to a QCheckBox subclass. Audit call sites,
Qt stylesheet selectors and storybook rendering for inherited behavior,
not only the public Python methods. Prefer this native base over a custom
QAccessible factory; revisit only if native platform checks show a real gap.

## Traversal and labels

Keep Qt's per-window Tab/Shift+Tab traversal. Inputs and actionable controls
participate; labels, cards, spacers and decorative widgets do not. Start with
construction order and use local `QWidget.setTabOrder` only where that order
differs from the visible form order. Rebuild local order after dynamic fields
are added; never build one fixed app-wide chain across hidden panels.

Use QLabel buddies for field accelerators where suitable. Names must describe
the action or setting, not the icon glyph or current on/off value. Icon-only
buttons need an explicit name such as "Chart properties" or "Settings".
Tooltips remain help text, not the only accessibility mechanism. Keep native
text editing, combo-box arrow behavior and table navigation unchanged.

## Panel and dialog transitions

- Switching panels by keyboard should keep focus on the triggering navigation
  button unless the action explicitly requests entry into the new panel.
  For explicit entry, restore the last still-visible, enabled focus target in
  that panel; otherwise use its first suitable control.
- If a panel is hidden or the sidebar collapses while focus is inside it, move
  focus to its visible navigation button. Do not let an unrelated background
  event steal focus when the user is editing elsewhere.
- When a tab closes, use the surviving active tab's appropriate control, or
  the visible workspace entry point if no document remains.
- Keep modal dialogs within Qt's normal focus scope. Restore focus to a live
  opener when they close. Test Enter on a toggle separately from the dialog's
  default action and Escape cancellation.

These container changes are follow-up work. They are not prerequisites for
using Qt's native checkable behavior in ToggleSwitch, but need tests before
claiming keyboard access across the application.

## Delivery sequence

1. Review this design and agree on the native checkable base and focus handoff
   rules. This document-only PR should reference #339, not close it.
2. Implement the shared ToggleSwitch, name its existing uses, update the
   storybook, and add focused regression tests. Include screenshots for focus
   and disabled states in light/dark themes.
3. Audit panel navigation, local form order, icon names and dialog restoration.
   Land those changes in small follow-ups with tests for the affected flows.

## Verification

The first implementation needs automated checks for:

- Tab/Shift+Tab reaching the switch in a real form; disabled and hidden
  switches skipped; Space, Enter and keypad Enter each changing state once.
- One `toggled` emission per state change, unchanged assignments silent,
  blocked signals remaining blocked, and no double activation from key repeat.
- QAccessible role CheckBox, a non-empty contextual name, and checkable,
  checked, disabled and focus state consistent with the widget.
- Enter on the switch not accepting a parent dialog; unrelated keys retaining
  Qt behavior; mouse activation and programmatic updates unchanged.
- Focus surviving panel switching/collapse and dynamic controls without
  escaping to a hidden widget or stealing focus from another editor.

Run existing toggle, style-panel and common-widget tests alongside these.
Inspect actual focus-ring pixels, theme contrast and layout clipping.
Then manually test native screen-reader output with NVDA on Windows and
VoiceOver on macOS, including names, role, checked state and disabled state.
Offscreen pytest and QAccessible inspection alone do not establish native
screen-reader support or cross-platform focus behavior.

## References

- [Qt keyboard focus](https://doc.qt.io/qt-6/focus.html)
- [Qt accessibility](https://doc.qt.io/qt-6/accessible.html)
- [Qt abstract button behavior](https://doc.qt.io/qt-6/qabstractbutton.html)

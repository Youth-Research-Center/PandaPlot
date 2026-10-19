# Keyboard focus and accessible controls

Status: plan for review. The `ToggleSwitch` keyboard base is already
implemented; the remaining items below are not.

Related: [#339](https://github.com/Youth-Research-Center/PandaPlot/issues/339).
This document sets the app-wide approach for keyboard focus and accessible
controls. It does not close #339 or claim screen-reader validation.

## Current state

Snapshot of `main` at `a38f2774` (October 3, 2026). Trim or update this
section as the follow-ups below land; the rest of the document is the plan.

Already in place:

- `gui/components/common/toggle_switch.py` is a checkable `QAbstractButton`
  with `StrongFocus`, a painted focus ring, Space and Enter/Return activation,
  and `toggled(bool)` driven by Qt's own checked state. An offscreen check
  reports `Role.CheckBox` and checkable state.
  `tests/gui/components/common/test_toggle_switch.py` covers focus, keyboard
  activation, accessible state and `toggled` emission.
- `PButton` inherits QPushButton and already has Qt button behavior. Focus
  support should be preserved rather than replaced with app-wide key routing.

Still open:

- Nearly all of the 35 `ToggleSwitch` uses have no accessible name
  (`density_fill_toggle` in `style_tab.py` is a rare exception), so a screen
  reader announces an unnamed check box.
- `ToggleSwitch` handles Enter/Return itself. Native check boxes do not toggle
  on Enter, and Qt forwards Enter to a dialog's default button, so pressing
  Enter on a switch in a dialog flips it instead of accepting. See
  [Shared ToggleSwitch](#shared-toggleswitch).
- `sidebar/icon_bar.py` creates panel buttons from icon text. Semantic names
  need to be supplied independently of the displayed glyph; a tooltip alone
  is not an accessible name.
- `StyleTab._field_row` places a QLabel beside a field without a buddy or
  accessible-name association (`setBuddy` is not used anywhere). Repeated
  labels such as "Match line" also need the group context, for example
  "Markers: match line color".
- `PanelArea.show_panel` switches the stacked widget; sidebar collapse hides
  it. There is no explicit focus handoff for these transitions.
- ThemeManager's global stylesheet has no explicit `:focus` rules. Custom
  painted controls draw their own ring, so each theme must keep it visible.

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

Keep `ToggleSwitch` as a `QAbstractButton` with the existing pill paint
treatment. It already gets Qt's checkable role, checked-state model, Space
activation and disabled behavior. Unlike a `QCheckBox` subclass it is not
matched by `QCheckBox` or `QCheckBox::indicator` selectors (for example those
in `chart_wizard.py`), so theme rules for check boxes cannot leak into the
painted control. Switch to `QCheckBox` only if native checks show a real gap.
A custom `QAccessible` factory is not needed for the same reason.

- Qt's checked state is the single source of truth; do not keep a `_checked`
  field or a second signal. Signal-blocked model-to-view updates must keep
  working, and a programmatic `setChecked` emits only on an actual change.
- **Space only.** Remove the Enter/Return handler. Native check boxes do not
  toggle on Enter, and Qt forwards Enter to the parent dialog's default
  button, so handling it makes a dialog's Enter flip a toggle instead of
  accepting. Issue #339 does not ask for Enter. Enter and keypad Enter must
  leave the switch unchanged and reach the dialog.
- **`setChecked` signature.** `setChecked` is a Qt slot that can be connected
  positionally (`toggled.connect(other.setChecked)`). The keyword-only
  override (`setChecked(self, *, checked)`) raises `TypeError` for such a
  connection. Today every caller uses `setChecked(checked=...)` and none
  connects the slot directly, so nothing breaks. Keep it that way: connect
  through a lambda or a named method, and state in the implementation PR
  whether the override stays or is dropped in favor of `# noqa: FBT003` at
  positional call sites.
- **Painting and layout.** The control paints itself, so it must also own its
  geometry: keep `sizeHint` and the fixed size matching the pill, restrict
  `hitButton` to the pill so clicks outside it do not toggle, and repaint on
  focus changes. If the focus ring needs room beyond the pill, check clipping
  in existing forms, at high DPI and in both themes.
- **Focus policy.** `StrongFocus` also accepts focus on click, so clicking a
  switch takes focus from a text field being edited. That matches other
  buttons; use `TabFocus` instead if it proves disruptive in the forms.
- **Role.** Qt has no switch role, so assistive technology announces a check
  box with a checked state, not a switch. This is acceptable; docs and tests
  must not claim switch semantics.
- Require a meaningful accessible name at each use. Where a visible label is
  available, use it as the source; for repeated fields include the section
  context. Do not give all switches the same fallback name "Toggle". This is
  how the AGENTS.md rule is met for this control: custom-painted controls need
  `setAccessibleName`/`setAccessibleDescription` and must be focusable and
  activatable.

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
the ToggleSwitch fixes, but need tests before claiming keyboard access across
the application.

## Delivery sequence

1. Review this plan. This document-only PR references #339, not closes it.
2. Fix `ToggleSwitch`: remove the Enter handler, cover `hitButton` and
   `sizeHint`, name every existing use, update the storybook, and add focused
   regression tests. Include screenshots for focus and disabled states in
   light and dark themes.
3. Audit panel navigation, local form order, icon names and dialog restoration.
   Land those changes in small follow-ups with tests for the affected flows.

## Verification

Automated checks for the ToggleSwitch fixes:

- Tab/Shift+Tab reaching the switch in a real form; disabled and hidden
  switches skipped; Space changing state once; Enter and keypad Enter leaving
  it unchanged.
- One `toggled` emission per state change, unchanged assignments silent,
  blocked signals remaining blocked, and no double activation from key repeat.
- QAccessible role CheckBox (not a switch role), a non-empty contextual name,
  and checkable, checked, disabled and focus state consistent with the widget.
- Enter on the switch accepting the parent dialog through its default button;
  unrelated keys retaining Qt behavior; clicks outside the pill not toggling;
  mouse activation and programmatic updates unchanged.
- Focus surviving panel switching/collapse and dynamic controls without
  escaping to a hidden widget or stealing focus from another editor.

Run existing toggle, style-panel and common-widget tests alongside these.
Inspect actual focus-ring pixels, theme contrast and layout clipping.

Then test native screen-reader output, including names, role, checked state,
disabled state and Tab reachability:

| Platform | Screen reader | Notes |
| --- | --- | --- |
| Windows | NVDA, Narrator | Qt exposes the UI Automation bridge by default. |
| macOS | VoiceOver | Tab may skip buttons and check boxes unless "Full Keyboard Access" is on in System Settings. Confirm the switch behaves like other buttons and is not unreachable. |
| Ubuntu | Orca | Qt reaches Orca through AT-SPI, which needs the accessibility bus and may need `QT_ACCESSIBILITY=1`. Check X11 and Wayland sessions and the focus ring under the system theme. |

Offscreen pytest and QAccessible inspection alone do not establish native
screen-reader support or cross-platform focus behavior. The macOS and Ubuntu
rows are expectations to confirm, not results from this audit; Space, Enter
and Tab behavior was exercised offscreen on Windows only.

## References

- [Qt keyboard focus](https://doc.qt.io/qt-6/focus.html)
- [Qt accessibility](https://doc.qt.io/qt-6/accessible.html)
- [Qt abstract button behavior](https://doc.qt.io/qt-6/qabstractbutton.html)

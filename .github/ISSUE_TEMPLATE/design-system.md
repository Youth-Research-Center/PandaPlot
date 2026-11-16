---
name: Design system task
about: One PR-sized step of the design-system milestone (see docs/design/design-system.md)
title: "[DS-NN] "
labels: []
---

## Goal
<!-- One or two sentences: what changes for users or developers once this lands. -->

## Scope
<!-- Spec section (docs/design/design-system.md §…) and handoff option id (docs/design/handoff/, e.g. Step 3 · 3a). -->
-

## Acceptance
- [ ] Content unchanged (spec §3); for panels, the DS-02 inventory golden diff shows only the allowed changes
- [ ] New components: Storybook state-matrix story (states x light/dark x density) and pytest-qt tests
- [ ] Screenshots in the PR description for any change to the look, light and dark: before and after for existing UI, the Storybook state matrix for a new component; migration PRs at 240 / 300 / 360 / 480 px (spec §3)
- [ ] Keyboard: Tab order, focus ring visible, Space/Enter activation
- [ ] `uv run ruff check .` and `QT_QPA_PLATFORM=offscreen uv run pytest` for the touched areas pass
- [ ] CHANGELOG entry under `## [Unreleased]` (`### Changed` for migrations; none for Storybook-only components)

## Dependencies
<!-- Issues that must be merged first. -->
-

## References
<!-- Closes #… / Refs #… -->
-

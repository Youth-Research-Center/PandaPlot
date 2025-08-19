# TASK-009 Styling / Theming Unification Plan

Status: Draft (Revision 2)
Author: Assistant
Scope: Replace scattered inline `setStyleSheet` calls with a centralized, token‑driven theming system integrated with `ThemeManager`.

---
## 1. Problem Statement
Styles (QSS) are currently duplicated across many widgets (`setStyleSheet` in dialogs, tabs, panels, buttons, labels). This increases maintenance effort, causes inconsistent look, and complicates future theme expansion (dark / high contrast / custom accent). Some inline styles are dynamic and should remain (e.g. transient status colouring, accent preview), but most static structure / color / spacing can be centralized.

---
## 2. Objectives
1. Single source of truth for palette, typography, spacing, border radii.
2. ThemeManager generates and applies global stylesheet derived from design tokens + active theme + accent.
3. Eliminate 80–90% of per‑widget `setStyleSheet` calls (target: reduce >100 occurrences to <15).
4. Provide extension mechanism for feature‑specific partial QSS (e.g. Home/Welcome tab rich sections) without breaking global consistency.
5. Support Light / Dark now; allow adding HighContrast later with minimal new code.

Non‑Goals (this task): dynamic chart color palette logic, accessibility auditing, runtime downloadable themes.

---
## 3. Design Overview

### 3.0 Revision Notes
This revision incorporates review feedback on performance optimization, SOLID separation, and PySide/Qt best practices:
* Introduced explicit separation of concerns (TokenResolver, StylesheetBuilder, ThemeApplicator) to keep `ThemeManager` slim.
* Added stylesheet hashing + early return, and optional debounce for rapid consecutive config changes.
* Removed unsupported CSS (e.g. `filter: brightness(...)`) in favor of a computed hover color.
* Clarified palette vs. QSS responsibilities (base colors via QPalette; shape / variants via QSS).
* Added dynamic property refresh helper plan (`refresh_widget_style`).
* Added performance and risk mitigations for large tables / views.

### 3.1 Design Tokens
Create a Python module `pandaplot/gui/theme/tokens.py` exposing immutable structures (dataclasses or TypedDict) for:
```
ColorTokens: background_base, background_alt, panel, panel_border, text_primary,
             text_muted, success, warning, danger, accent, accent_hover
FontTokens:  base_family, mono_family, size_base, size_small, size_title
Metrics:     radius_sm, radius_md, padding_xs, padding_sm, padding_md, spacing_sm, spacing_md
```
Tokens selected based on current repeated constants (e.g. `#6c757d`, `#28a745`, `#dc3545`, `#ffc107`).

Two base palettes (Light, Dark). Accent overrides inserted from config. High contrast can later add another palette without touching consumers.

### 3.2 QSS Template Files
Add directory `pandaplot/resources/styles/` containing:
* `base.qss` – Generic reset + core widgets (QWidget, QLabel, QFrame, QPushButton, QTabBar, QScrollArea, QTreeView, QTableView, QLineEdit, QTextEdit).
* `components.qss` – Shared component selectors using object names / dynamic properties.
* `welcome_tab.qss` – Example of a feature‑specific partial (kept because of unique layout visuals).

Use placeholder syntax `{{token.path}}` inside QSS templates, rendered via simple string replacement (no heavy templating dependency). Unsupported CSS properties will be excluded to avoid silent no-ops in Qt:
```
QPushButton {
  background-color: {{colors.accent}};
  border: 1px solid {{colors.accent}};
  border-radius: {{metrics.radius_md}}px;
  padding: 4px 10px;
  color: white;
}
QPushButton:hover {
  background-color: {{colors.accent_hover}}; /* Precomputed hover color */
}
QPushButton[variant="secondary"] {
  background-color: {{colors.panel}};
  color: {{colors.text_primary}};
  border: 1px solid {{colors.panel_border}};
}
```

### 3.3 Object Names & Properties
Replace inline `setStyleSheet` variations with semantic tagging:
```
label.setProperty("text-role", "muted")
status_label.setProperty("status", "success")
button.setProperty("variant", "danger")
```
Global QSS rules target these:
```
QLabel[text-role="muted"] { color: {{colors.text_muted}}; }
QLabel[status="success"], .status-success { color: {{colors.success}}; font-weight: bold; }
```
Backward compatibility: add helper `apply_status_style(widget, status)` generating property + optional class name for transitional period.

### 3.4 Theme System Architecture (Refined)
Introduce small focused collaborators:
* `TokenResolver` – Given `Theme` + accent + (future overrides), returns structured token dict.
* `StylesheetBuilder` – Accepts token dict + ordered template paths + optional partials; performs substitution + hashing cache.
* `ThemeApplicator` – Applies QPalette (base/window/text colors) and sets the global font size; then applies the computed stylesheet.
* `ThemeManager` – Orchestrates: listens to `config.*` events, debounces updates (e.g. 50ms window), compares new `ThemeContext` hash, then uses above collaborators; emits `theme.changed` only on actual visual change.

Flow:
`config.updated` -> ThemeManager collects change -> (debounce) -> TokenResolver -> StylesheetBuilder (hash skip) -> ThemeApplicator -> emit `theme.changed`.

Palette vs QSS:
* Palette: high-level roles (Window, WindowText, Base, Text, Button, ButtonText) for platform consistency & accessibility.
* Stylesheet: variants (primary/secondary/danger), spacing, radii, status colors, property-driven overrides.

### 3.5 Dynamic Property Refresh Helper
Provide helper `refresh_widget_style(widget)` performing `style().unpolish/polish` only when a dynamic property affecting styling changes (e.g., status label moving from `warning` → `success`). Callers use it sparingly to avoid unnecessary polish cycles.

### 3.6 Partial Registry
Provide optional registration API:
```
ThemeManager.register_partial("welcome_tab", path_or_callable)
```
Feature modules (e.g. WelcomeTab) can register a specific partial only if loaded. Keeps startup lean.

---
## 4. Migration Strategy

| Phase | Goal | Actions | Success Metric |
|-------|------|---------|----------------|
| 1 | Inventory & Classification | Script (or manual) categorize existing `setStyleSheet` uses into: standard, status, dynamic, feature-specific | 100% lines categorized |
| 2 | Token Definition | Introduce tokens module; map existing hex/values → tokens | All repeated values tokenized |
| 3 | Base & Components QSS | Draft `base.qss` + `components.qss`; apply via ThemeManager | App renders with new styles, no functional regressions |
| 4 | Replace Simple Inline Styles | Remove trivial `setStyleSheet` (solid color, font weight) in tabs/panels | Reduce inline occurrences by ≥50% |
| 5 | Add Status / Variant Properties | Refactor status labels/buttons to property-driven styling | Status color logic uses properties only |
| 6 | Debounce & Hash Optimization | Introduce update debounce & stylesheet hash skip | Measured theme apply time stable (< baseline) |
| 7 | Feature Partials | Migrate Welcome/Home tab to partial QSS (keep bespoke layout CSS) | Inline style lines in WelcomeTab reduced ≥80% |
| 8 | Cleanup & Guardrails | Lint rule / grep check in CI to flag new inline styles (except allowlist) | CI blocks unapproved inline additions |

Rollback: Each phase commits separately; if regressions appear, revert latest phase only.

---
## 5. Detailed Refactors

### 5.1 Buttons
Current: Many custom per-button style blocks.
Plan: Provide variants (`primary`, `secondary`, `danger`, `warning`, `success`, `link`) via `variant` property; states (hover, pressed, disabled) defined once.

### 5.2 Status Labels
Current: Repeated `color: #28a745` etc.
Plan: `status` property + shared rule set. Dynamic updates: change property then call small helper `refresh_widget_style(widget)` (which does `widget.style().unpolish/polish` if needed).

### 5.3 Panels / Frames
Current: Many frames define background, border.
Plan: Classify frames by role: `panel`, `toolbar`, `statusbar`, `header`. Set objectName or property; target in QSS.

### 5.4 Fonts & Typography
Move font sizing from per-widget CSS to global font (via ThemeManager) plus selective modifiers:
```
QLabel[role="title"] { font-size: {{fonts.size_title}}pt; font-weight:600; }
QLabel[role="muted"] { color: {{colors.text_muted}}; font-size: {{fonts.size_small}}pt; }
```
Inline font size usage removed except for temporary measurement or rich text content areas.

### 5.5 Accent Color Usage
Where buttons or icons depend on accent, rely on template referencing `{{colors.accent}}`; dynamic change triggers full stylesheet rebuild (already cheap). Avoid setting accent through per-button inline style.

### 5.6 Dynamic Highlight / Transient States
Allowed inline or helper-based (e.g. highlighting a changed value cell). Documented exception list:
* Temporary error highlight (e.g. flash red background)
* Data-driven color previews (chart color swatches)
* User-selected accent preview button in Settings Dialog.

Maintain an `INLINE_STYLE_ALLOWLIST` in a small module for grep-based lint script.

---
## 6. File / Module Additions
```
pandaplot/
  gui/
    theme/
      __init__.py
      tokens.py              # Theme token definitions
      qss_loader.py          # Template loader + substitution
      helpers.py             # apply_status_style, refresh_widget_style
  resources/
    styles/
      base.qss
      components.qss
      welcome_tab.qss (optional)
scripts/
  validate_styles.py         # CI helper to list new inline style usages
```

---
## 7. ThemeManager Changes (Refined API Surface)
New internal collaborators (not all exported):
```
TokenResolver.resolve(theme: Theme, accent: str) -> Tokens
StylesheetBuilder.build(tokens: Tokens, partials: list[str]) -> str
ThemeApplicator.apply(palette_tokens, stylesheet: str, font_size: int) -> None
```
`ThemeManager` gains:
```
set_debounce_interval(ms: int = 50)
register_partial(name: str, path_or_callable)
force_reapply()  # bypass hash skip (dev mode)
```
Deprecated responsibility: constructing raw QSS strings inline. All moved to templates + builder.

---
## 8. Testing Strategy
1. Unit: token substitution (no placeholder left unfilled) + placeholder detection regex.
2. Unit: hover color derivation (accent → accent_hover) deterministic & within contrast bounds.
3. Unit: builder hash cache skip (call count instrumentation or timing proxy) when no token/template change.
4. Unit: helpers apply correct properties (e.g. `apply_status_style('success')`).
5. Integration (Qt minimal): dummy QLabel status toggling triggers style change after refresh helper.
6. Snapshot (optional): hash of generated QSS compared against baseline per theme (update snapshot intentionally when tokens evolve).
7. Lint: script asserts max inline style count threshold.
8. Performance micro-benchmark (optional): measure applying stylesheet vs baseline to detect regressions.

---
## 9. Performance Considerations
* Rebuild stylesheet only on token or template hash change (hash includes theme + accent + font size + template mtimes).
* Debounce rapid consecutive config updates (window ~50ms) to batch user changes in Settings dialog.
* Precompute hover accent color (HSL/HSV adjust) to avoid unsupported CSS filters.
* Avoid deep descendant selectors; keep selectors shallow (1–2 levels) to reduce matching cost.
* Minimize QSS applied to high-row-count views (QTableView) — rely on palette & delegates rather than per-cell CSS.
* Skip full rebuild for font size only changes if palette + stylesheet unaffected (optional optimization path).
* Provide timing hooks (dev mode) to log stylesheet build + apply durations for regression tracking.

---
## 10. Risks & Mitigations
| Risk | Impact | Mitigation |
|------|--------|------------|
| Missing selector coverage leads to visual regressions | Medium | Phase-by-phase migration + visual smoke test checklist |
| Over-tokenization adds noise | Low | Start minimal; add tokens only when reused ≥3 times |
| Unintended dark mode contrast issues | High | Contrast check utility (WCAG AA) + manual QA |
| Developers reintroduce inline styles | Medium | CI lint + documented allowlist |
| Debounce delays perceived instant feedback | Low | Keep interval small (≤50ms) + allow `force_reapply()` in dev |
| Hash collisions extremely unlikely but possible | Low | Use robust hash (SHA256) over sorted token JSON + template mtimes |
| Large QSS monolith slows polish | Medium | Split templates logically; apply only necessary partials |

---
## 11. Rollout Checklist (Per Phase PR)
1. Update docs (plan + CHANGELOG section).
2. Run lint script; confirm allowed inline count within phase threshold.
3. Generate QSS diff summary (lines added/removed) & record stylesheet hash.
4. Manual verify Light/Dark switching + accent change + status label property toggle.
5. Run tests (unit + integration + optional performance benchmark) – all pass.
6. Confirm no unsupported CSS warnings (grep for forbidden properties list).

---
## 12. Acceptance Criteria
* Global stylesheet defines buttons (variants), labels (status + muted), panels, tab headers, editors via templates.
* Inline stylesheet count reduced ≥80% from baseline (tracked in lint script history).
* Accent, theme, and interface font size changes coalesce (max one apply within 50ms window) and reflect visually.
* Adding new theme (e.g. `solarized`) needs only: palette token entry + optional partial; no component refactors.
* No unsupported CSS properties present in final QSS (automated check passes).
* Status label property change updates appearance with helper (no inline style usage for statuses).
* Average stylesheet rebuild+apply time remains below defined threshold (e.g. <30ms on reference machine) across themes.

---
## 13. Next Immediate Steps
1. Implement `TokenResolver`, `StylesheetBuilder`, `ThemeApplicator` skeleton + tests (hashing & substitution).
2. Extract existing inline QSS from ThemeManager into `base.qss` & `components.qss` (one PR).
3. Implement debounce & hash comparison logic in ThemeManager.
4. Add lint script & baseline inline style count (store baseline in CI artifact / docs).
5. Introduce status property styling for one component (DatasetTab) as pilot.
6. Expand property-based styling to remaining status labels/buttons.

---
## 14. Open Questions
* Do we want per-user custom token override file (`~/.pandaplot/theme.json`)? (Deferred)
* Should chart color cycles integrate with tokens now or later? (Later / separate task)
* Dark mode system detection (currently theme=system -> light); need OS query? (Separate small enhancement.)

---
## 15. Appendix: Sample Token JSON (Conceptual)
```json
{
  "light": {
    "colors": {
      "background_base": "#ffffff",
      "background_alt": "#f5f5f5",
      "panel": "#ffffff",
      "panel_border": "#dee2e6",
      "text_primary": "#212529",
      "text_muted": "#6c757d",
      "success": "#28a745",
      "warning": "#ffc107",
      "danger": "#dc3545",
      "accent": "#007bff",
      "accent_hover": "#0056b3"
    },
    "fonts": { "size_base": 12, "size_small": 10, "size_title": 18 },
    "metrics": { "radius_sm": 3, "radius_md": 4, "padding_sm": 4, "padding_md": 8, "spacing_sm": 6, "spacing_md": 12 }
  }
}
```

---
End of Plan.

# Development Task Backlog

Estimates use Fibonacci story points (1,2,3,5,8,13). 1 = trivial, 13 = epic (likely needs splitting). Tags (<=5) indicate primary areas.

| # | Title | Description | Estimate | Tags |
|---|-------|-------------|----------|------|
| 1 | Dataset Import Wizard | Guided multi-step UI to import CSV/Excel with delimiter & header detection. | 5 | gui, data-import, ux, models |
| 2 | Multi-Axis Chart Support | Allow charts with primary/secondary Y axes and axis linking. | 5 | gui, chart, analysis, ux |
| 3 | Enhanced Zoom/Pan Toolbar | Add rectangular zoom, reset, axis scale presets, keyboard shortcuts. | 3 | gui, ux, chart |
| 4 | Project Autosave & Recovery | Periodic autosave + crash recovery flow with recent versions list. | 5 | storage, project, reliability, ux |
| 5 | Persistent Undo/Redo Stack | Serialize command history into project file for session restore. | 8 | command-pattern, storage, project, architecture |
| 6 | Statistical Tests Module | Add ANOVA, t-test, chi-square with result view + export. | 8 | analysis, models, gui, export |
| 7 | Advanced Curve Fitting | Nonlinear fit (Levenberg–Marquardt) + confidence bands + residual plots. | 8 | analysis, models, chart |
| 8 | Embedded Scripting Console | In-app Python console sandboxed with project context injection. | 8 | gui, scripting, extensibility, security |
| 9 | Plugin Discovery & Loader | Folder-based plugin auto-discovery, metadata & enable/disable UI. | 8 | plugin, architecture, extensibility |
|10 | Event Bus Profiling | Instrument & profile event dispatch latency; add diagnostics panel. | 3 | event-system, performance, diagnostics |
|11 | Theming System | Light/dark + custom palette persistence; apply to all widgets/charts. | 5 | gui, ux, theming |
|12 | Internationalization Setup | i18n framework (gettext or Qt) + resource extraction pipeline. | 5 | gui, localization, build, docs |
|13 | PDF/LaTeX Report Export | Generate analysis report with charts & stats to PDF/LaTeX. | 8 | export, analysis, gui, report |
|14 | Bulk CSV/Excel Import | Multi-file import with schema inference & merge preview. | 5 | data-import, models, gui, ux |
|15 | Data Transformation Pipeline | Chainable ops (filter, normalize, derive columns) w/ preview. | 8 | analysis, models, gui, pipeline |
|16 | Chart Template System | Save/load reusable chart style & layout presets. | 5 | chart, gui, storage |
|17 | Unified Error Handling | Central error dialog, structured logs, user-friendly messages. | 3 | reliability, logging, gui |
|18 | Update Check Mechanism | Version check against GitHub releases + changelog dialog. | 3 | infrastructure, ux, networking |
|19 | Async Storage Layer | Refactor IO to async (where beneficial) to keep UI responsive. | 8 | storage, performance, architecture |
|20 | Command Pattern Test Coverage | Raise command-related unit test coverage >90%. | 3 | testing, command-pattern, quality |
|21 | Performance Benchmark Suite | Add micro/functional benchmarks (load project, render chart). | 5 | performance, testing, ci |
|22 | Cross-Platform Packaging | Build scripts for Windows (MSI), macOS (.app), Linux (AppImage). | 13 | packaging, distribution, build, ci |
|23 | Interactive Onboarding Tour | Guided highlights of core UI functions for first-time users. | 5 | ux, gui, onboarding |
|24 | High-DPI Layout Scaling | Auto-detect DPI & adjust fonts/padding; add user overrides. | 3 | gui, ux, responsiveness |
|25 | Telemetry Opt-In Module | Anonymous usage metrics (feature hits) with clear opt-in/out. | 5 | analytics, privacy, architecture, gui |
|26 | Add Type Hints (Core Models) | Introduce missing type hints in models to improve IDE support. | 2 | quality, typing, models |
|27 | Pre-Commit Hooks Setup | Add black, isort, flake8/mypy hooks via pre-commit config. | 2 | tooling, quality, ci |
|28 | Faster CI PyTest Flags | Optimize pytest config (add -q, disable slow plugins). | 1 | ci, testing, performance |
|29 | Docstring Coverage Pass | Ensure public APIs in `analysis` have docstrings. | 2 | docs, analysis, quality |
|30 | Logging Context Enrichment | Include project name & active item id in log records. | 2 | logging, diagnostics, infrastructure |
|31 | Centralized Version Const | Single `__version__` source used across app & about dialog. | 1 | build, metadata, maintenance |
|32 | Error Dialog Copy Button | Add copy-to-clipboard button for stack traces. | 1 | gui, ux, diagnostics |
|33 | Keyboard Shortcuts Help | Simple shortcuts cheat sheet dialog (F1). | 2 | gui, ux, accessibility |
|34 | Basic Accessibility Audit | Check tab order & add accessible names to key widgets. | 3 | accessibility, gui, ux |
|35 | Event Bus Unit Tests | Add edge tests (no subscribers, exception in handler). | 2 | testing, event-system, quality |
|36 | Event Handler WeakRefs | Use weakrefs to avoid subscriber memory leaks. | 3 | event-system, memory, architecture |
|37 | Dataset Preview Sorting | Enable column sort in import/preview tables. | 2 | gui, data-import, ux |
|38 | Graceful Ctrl+C Exit | Handle SIGINT for clean shutdown & save prompt. | 2 | reliability, cli, project |
|39 | Lightweight Profiling Script | Script to profile project load & first chart render. | 3 | performance, diagnostics, tooling |
|40 | Chart Export DPI Option | Add DPI field to image export dialog. | 1 | gui, chart, export |
|41 | Recent Projects Menu | Track last 5 opened projects in File menu. | 2 | gui, project, ux |
|42 | Unsaved Changes Indicator | Asterisk in window title when project dirty. | 1 | gui, project, ux |
|43 | Refactor Magic Numbers | Replace scattered constants with named module constants. | 2 | refactor, quality, maintenance |
|44 | Lightweight Plugin Example | Provide minimal sample plugin in `examples/` folder. | 2 | plugin, docs, extensibility |
|45 | Memory Usage Snapshot Tool | Simple command to log object counts & RSS usage. | 3 | diagnostics, performance, tooling |
|46 | Graceful Matplotlib Backend Check | Detect unsupported backend and fallback with warning. | 2 | chart, robustness, gui |
|47 | CI Cache Poetry/Uv | Enable dependency caching to reduce build time. | 2 | ci, performance, build |
|48 | In-App Update Channel Pref | Setting for stable vs prerelease update checks. | 2 | ux, settings, infrastructure |
|49 | Command Pallette MVP | Quick action launcher (Ctrl+Shift+P) for common commands. | 3 | gui, ux, productivity |
|50 | Auto-Focus First Field Dialogs | Set initial focus on primary input in dialogs. | 1 | ux, gui, polish |

## Suggested Near-Term Sequence
1. Foundation improvements: 17, 20, 10
2. UX & usability: 3, 1, 16, 11
3. Analysis depth: 6, 7, 15
4. Extensibility: 9, 8
5. Persistence & reliability: 4, 5, 19
6. Distribution & growth: 18, 22, 23, 25

## Notes
- Task 22 (Packaging) is an epic; split per platform when starting.
- Telemetry (25) must strictly respect opt-in and anonymization.
- Async storage (19) should be preceded by lightweight profiling to validate bottlenecks.
- Keep each task Definition of Done explicit in issues (tests, docs, lint, review).

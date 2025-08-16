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

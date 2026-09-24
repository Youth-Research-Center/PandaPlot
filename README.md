# PandaPlot

PandaPlot is an open-source, Python-based desktop application for scientific data visualization and analysis. It is designed to be an educational tool for learning and applying data analysis concepts.

## Features

- Hierarchical project management for datasets, charts, and notes
- Interactive charting with live-updating graphs, area fills, and a graph creation wizard
- Dataset import, including an Excel multi-sheet import wizard
- Mathematical analysis: derivatives, integrals, smoothing, interpolation, and curve fitting
- Descriptive statistics and guided statistical testing
- Signal analysis tools
- Rich notes with LaTeX rendering, PDF export, and full-text search
- Tab splitting and floating windows for flexible layouts
- Light/dark theming throughout the UI

See [docs/USER_GUIDE.md](docs/USER_GUIDE.md) for usage details and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for an overview of the codebase.

## Setup
We use [uv](https://docs.astral.sh/uv/getting-started/installation/) to manage our Python environment. Requires Python 3.12+. To set up the project, run the following command:

```bash
uv sync
```

## Running the Application
To run the PandaPlot application, execute the following command from the root directory of the project:

```bash
uv run python -m pandaplot.app
```

## Packaging and Deployment
PandaPlot uses `pyside6-deploy` (and Nuitka) to create standalone executables/installers.

To test the deployment configuration without compiling:
```bash
uv run python scripts/build_installer.py --dry-run
```

To build the executable installer locally:
```bash
uv run python scripts/build_installer.py
```

On Windows, the packaged executable runs without a console window (`--windows-console-mode=disable` in `pysidedeploy.spec`); logs still go to `~/.pandaplot/application.log` for debugging (set `PANDAPLOT_DEBUG=1` for verbose file logging).

### GitHub Actions Release Workflow
Builds are triggered manually via GitHub Actions under the **Actions** tab -> **Build Release Installer** workflow (`workflow_dispatch`), with two inputs:
- `dry_run`: inspect the deploy commands without compiling (skips the release step entirely)
- `version`: the tag to publish under (e.g. `v1.0.0`); required unless `dry_run` is set

The workflow compiles installers across Linux, Windows, and macOS, then publishes them all to a single [GitHub Release](../../releases) under that tag, with SHA256 checksums for every installer listed in the release notes (see [CHANGELOG.md](CHANGELOG.md) for what to move from `Unreleased` into a versioned entry before running a release — the workflow pulls that section into the release notes automatically).

### Troubleshooting Notes
- **`dumpbin` Warning (Windows)**: You may see `RuntimeWarning: [DEPLOY] Unable to find dumpbin...`. `dumpbin.exe` is a Visual Studio C++ tool used by `pyside6-deploy` to automatically scan binary dependencies. On developer environments without MSVC in PATH, `pyside6-deploy` falls back to the Qt modules listed in `pysidedeploy.spec` (`modules = Core,Gui,Widgets`), which works as intended. In GitHub Actions, the `ilammy/msvc-dev-cmd` action initializes the MSVC toolchain (including `dumpbin`).

## Running Tests
```bash
uv run pytest
uv run pytest --verbose
uv run pytest --cov
uv run pytest --cov=pandaplot --cov-report=html
```

## Component Storybook

`pandaplot_storybook/` is a standalone sub-project for previewing shared PySide6 widgets (e.g. `PButton`) in isolation, with light/dark theme switching. See [pandaplot_storybook/README.md](pandaplot_storybook/README.md) for setup and usage.

## Linting and Static Analysis

```bash
uv run ruff check .
uv run bandit -r pandaplot
uv run pip-audit
uv run vulture pandaplot
```

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on how to contribute to this project.


## License

PandaPlot is licensed under the [MIT License](LICENSE).

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

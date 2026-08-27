# Contributing to PandaPlot

Contributions are welcome! If you would like to contribute to PandaPlot, please follow these steps:

1.  Fork the repository.
2.  Create a new branch for your feature or bug fix.
3.  Set up your environment with [uv](https://docs.astral.sh/uv/getting-started/installation/) (requires Python 3.12+):
    ```bash
    uv sync
    ```
4.  Make your changes.
5.  Run the tests to ensure everything is working correctly:
    ```bash
    pytest
    ```
6.  Run linting and static analysis checks:
    ```bash
    ruff check .
    bandit -r pandaplot
    pip-audit
    vulture pandaplot
    ```
7.  Submit a pull request.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for an overview of the codebase, and [pandaplot_storybook/README.md](pandaplot_storybook/README.md) if you're working on shared PySide6 widgets.

## Coding conventions

- Prefer keyword arguments for boolean parameters. `ruff`'s `FBT` (flake8-boolean-trap) rules are enabled to catch positional booleans in both function definitions and call sites — make boolean parameters keyword-only (`def f(x, *, enabled: bool = True)`) unless the function overrides a Qt virtual method or is invoked positionally by a Qt signal connection, in which case add a `# noqa: FBT00x` with a short comment explaining why.

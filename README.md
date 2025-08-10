# PandaPlot
PandaPlot is educational scientific visualization and analysis application built with Python. The project is open source and welcomes contribution.


## Setup
We use [uv](https://docs.astral.sh/uv/getting-started/installation/) to manage our Python environment. To set up the project, run the following commands:

```bash
uv sync
```

## Run app
Activate virtual environment and run the following command.
```
python -m pandaplot.app
```

## Run tests
```bash
pytest
pytest --verbose
pytest --cov
```
# PandaPlot

PandaPlot is an open-source, Python-based desktop application for scientific data visualization and analysis. It is designed to be an educational tool for learning and applying data analysis concepts.


## Setup
We use [uv](https://docs.astral.sh/uv/getting-started/installation/) to manage our Python environment. To set up the project, run the following commands:

```bash
uv sync
```

## Running the Application
To run the PandaPlot application, execute the following command from the root directory of the project:

```bash
python -m pandaplot.app
```

## Running Tests
```bash
pytest
pytest --verbose
pytest --cov
```

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on how to contribute to this project.


## License

PandaPlot is licensed under the [MIT License](LICENSE).

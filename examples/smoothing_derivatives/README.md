# Smoothing and derivatives

Generate the example from the repository root:

```sh
uv run python examples/smoothing_derivatives/create_smoothing_example.py
```

Open `smoothing_derivatives.pplot` in PandaPlot. The project contains one dataset,
three charts (raw data, Savitzky-Golay smoothing, and the first derivative of the
smoothed signal), and a note with the Analysis panel steps and parameter guidance.
`smoothing_derivatives.png` is a preview of the same data.

The synthetic data uses a fixed random seed. The clean signal and its analytical
derivative are reference curves. The generator uses PandaPlot's `AnalysisEngine`,
with window length 51, polynomial order 3 and the central derivative method.

A longer smoothing window removes more noise but can flatten short features.
A shorter window preserves detail but leaves more noise. Polynomial order controls
the local fitted curve; it must be smaller than the window length. Differentiation
amplifies remaining noise, and endpoint artifacts should not be treated as real
features. The project note suggests comparisons to try in the Analysis panel.

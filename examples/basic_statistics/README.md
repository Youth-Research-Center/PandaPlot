# Basic Statistics

Generate the example from the repository root:

```sh
uv run python examples/basic_statistics/create_basic_statistics_example.py
```

Open `basic_statistics.pplot` in PandaPlot (Help > Open Example Project). The project follows a synthetic class of
120 students in three groups. It contains:

- **Class measurements** (student id, group, age, height, weight, shoe size, hours of sleep) and **Height by group**
  (one column per group, for the box plot).
- Results that the Descriptive Statistics and Statistical Tests panels create with **Add to Project**: descriptive
  statistics and a written report, two Pearson correlations and a Spearman correlation.
- A **Correlation matrix (Pearson r)** table built by the script with the same Pearson test.
- Five charts (height and age histograms, a box plot of height by group, and two scatter plots) and a set of
  Markdown notes that explain each step.

The data uses a fixed random seed (`numpy.random.default_rng(35)`), so every run produces the same tables. The
generator calls `DescriptiveStatsEngine` and `StatsEngine` directly, so the results equal what the panels produce.

Known limits of the app that shape this example: the Descriptive Statistics panel has no mode (#638), there is no
correlation-matrix feature (#639), heatmaps need numeric axes (#640) and box plots cannot group by a column (#641).

The examples-browser metadata (summary, description, section, level, tags, featured charts, start note and data
credit) is set in the generator script, not in the `.pplot` file by hand.

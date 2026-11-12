# Basic Statistics

Generate the example from the repository root:

```sh
uv run python examples/basic_statistics/create_basic_statistics_example.py
```

Open `basic_statistics.pplot` in PandaPlot (Help > Open Example Project). The project is a beginner-friendly statistics
course, written for students who are new to statistics, around a synthetic class of 120 students in three groups. Every
tool is explained with what it is, when to use it, how to read it, what it shows in this class and common mistakes.

The project tree starts with two notes, **Start here** (an overview and a "which tool when?" table) and **Glossary**
(a one-line definition of every technical word), followed by six folders:

- **0 The data**: the note "About the data", **Class measurements** (student id, group, age, height, weight, shoe size,
  hours of sleep) and **Height by group** (one column per group, for the box plot).
- **1 Descriptive statistics**: a note, the results of the Descriptive Statistics panel (a dataset and a written report).
- **2 Histograms**: a note and the height and age histograms.
- **3 Box plots**: a note and a box plot of height by group.
- **4 Correlation**: two notes ("Scatter plots and correlation" and "Is it real? p-values, Pearson or Spearman,
  causation"), two scatter plots, two Pearson correlations and a Spearman correlation made with the Statistical Tests
  panel, and a **Correlation matrix (Pearson r)** table built by the script with the same Pearson test.
- **5 Try it yourself**: warm-ups, exercises and two challenges (one-way ANOVA and Kruskal-Wallis).

When a learner clicks **Add to Project**, the Descriptive Statistics panel puts its results next to the source dataset and
the Statistical Tests panel puts its results at the top level of the project tree. The bundled results sit in the folder of
the step that uses them instead, and the notes tell learners where their own copies appear.

Every number about the class that the notes quote is computed by the generator from the data and the engines' results and
is checked by `tests/examples/test_basic_statistics_example.py`. That test file also checks that the committed
`basic_statistics.pplot` equals a fresh generation, so regenerate it after any change to the script.

The data uses a fixed random seed (`numpy.random.default_rng(35)`), so every run produces the same tables. The
generator calls `DescriptiveStatsEngine` and `StatsEngine` directly, so the results equal what the panels produce.

Known limits of the app that shape this example: the Descriptive Statistics panel has no mode (#638), there is no
correlation-matrix feature (#639), heatmaps need numeric axes (#640) and box plots cannot group by a column (#641).

The examples-browser metadata (summary, description, section, level, tags, featured charts, start note and data
credit) is set in the generator script, not in the `.pplot` file by hand.

"""
Basic Statistics Example
Demonstrates statistical analysis using PandaPlot.
"""

import numpy as np
import pandas as pd


def create_dataset():
    """Create a synthetic dataset for statistical analysis."""
    rng = np.random.default_rng(42)

    data = pd.DataFrame({
        "Height": rng.normal(170, 10, 100),
        "Weight": rng.normal(65, 12, 100),
        "Age": rng.integers(18, 60, 100),
    })

    return data

def calculate_statistics(data):
    """Calculate basic descriptive statistics."""
    statistics = {
        "mean": data.mean(),
        "median": data.median(),
        "mode": data.mode().iloc[0],
        "standard_deviation": data.std(),
    }

    return statistics

def calculate_correlation(data):
    """Calculate the correlation between height and weight."""
    return data["Height"].corr(data["Weight"])


if __name__ == "__main__":
    data = create_dataset()

    print("Synthetic Dataset:")
    print(data.head())

    statistics = calculate_statistics(data)

    print("\nDescriptive Statistics:")
    print("\nMean:")
    print(statistics["mean"])

    print("\nMedian:")
    print(statistics["median"])

    print("\nMode:")
    print(statistics["mode"])

    print("\nStandard Deviation:")
    print(statistics["standard_deviation"])

    correlation = calculate_correlation(data)

    print("\nCorrelation between Height and Weight:")
    print(f"{correlation:.3f}")
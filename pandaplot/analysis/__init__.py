"""
Analysis module for mathematical operations on data.
"""

from .analysis_engine import AnalysisEngine
from .analysis_types import AnalysisParameters, AnalysisResult, AnalysisType, DerivativeMethod, InterpolationMethod, SmoothingMethod
from .descriptive_engine import DescriptiveStatsEngine
from .descriptive_types import DESCRIPTIVE_STATS, DescriptiveStatsResult
from .preprocessing_engine import PreprocessingEngine
from .preprocessing_types import (
    PREPROCESSING_METHODS,
    PreprocessingInfo,
    PreprocessingMethod,
    PreprocessingResult,
)
from .signal.signal_engine import SignalEngine
from .signal.signal_types import SIGNAL_ANALYSES, SignalAnalysisResult, SignalAnalysisType
from .stats_engine import StatsEngine
from .stats_types import STAT_TESTS, Alternative, InputMode, StatTestInfo, StatTestResult, StatTestType

__all__ = [
    "DESCRIPTIVE_STATS",
    "PREPROCESSING_METHODS",
    "SIGNAL_ANALYSES",
    "STAT_TESTS",
    "Alternative",
    "AnalysisEngine",
    "AnalysisParameters",
    "AnalysisResult",
    "AnalysisType",
    "DerivativeMethod",
    "DescriptiveStatsEngine",
    "DescriptiveStatsResult",
    "InputMode",
    "InterpolationMethod",
    "PreprocessingEngine",
    "PreprocessingInfo",
    "PreprocessingMethod",
    "PreprocessingResult",
    "SignalAnalysisResult",
    "SignalAnalysisType",
    "SignalEngine",
    "SmoothingMethod",
    "StatTestInfo",
    "StatTestResult",
    "StatTestType",
    "StatsEngine",
]

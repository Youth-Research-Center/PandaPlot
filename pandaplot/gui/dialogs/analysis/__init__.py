"""
Analysis dialogs for mathematical operations configuration.
"""

from .base_analysis_dialog import BaseAnalysisDialog
from .derivative_dialog import DerivativeDialog
from .integral_dialog import IntegralDialog
from .smoothing_dialog import SmoothingDialog

__all__ = [
    "BaseAnalysisDialog",
    "DerivativeDialog",
    "IntegralDialog",
    "SmoothingDialog"
]

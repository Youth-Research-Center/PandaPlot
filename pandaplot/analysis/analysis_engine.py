"""
Core analysis engine providing mathematical analysis operations.
"""

from typing import Optional

import numpy as np
import pandas as pd
from scipy.integrate import cumulative_trapezoid, trapezoid
from scipy.interpolate import CubicSpline, interp1d
from scipy.signal import savgol_filter

from .analysis_types import AnalysisParameters, AnalysisResult, AnalysisType, DerivativeMethod, InterpolationMethod, SmoothingMethod


class AnalysisEngine:
    """
    Core analysis engine providing mathematical operations on data.
    """
    
    @staticmethod
    def calculate_derivative(
        x_data: pd.Series, 
        y_data: pd.Series, 
        method: str = "central",
        start_index: int = 0,
        end_index: int = -1
    ) -> AnalysisResult:
        """
        Calculate derivative using specified method.
        
        Args:
            x_data: X-axis data
            y_data: Y-axis data
            method: Derivative method ('central', 'forward', 'backward')
            start_index: Start index for calculation
            end_index: End index for calculation
            
        Returns:
            AnalysisResult containing derivative data
        """
        # Handle data slicing
        if end_index == -1:
            end_index = len(x_data)
        
        x_slice = x_data.iloc[start_index:end_index]
        y_slice = y_data.iloc[start_index:end_index]
        
        # Calculate derivative based on method
        if method == DerivativeMethod.CENTRAL.value:
            derivative = np.gradient(y_slice, x_slice)
        elif method == DerivativeMethod.FORWARD.value:
            derivative = np.diff(y_slice) / np.diff(x_slice)
            derivative = np.append(derivative, derivative[-1])  # Pad last value
        else:  # backward
            derivative = np.diff(y_slice) / np.diff(x_slice)
            derivative = np.insert(derivative, 0, derivative[0])  # Pad first value
        
        # Calculate statistics
        statistics = {
            "min": float(np.min(derivative)),
            "max": float(np.max(derivative)),
            "mean": float(np.mean(derivative)),
            "std": float(np.std(derivative))
        }
        
        parameters = AnalysisParameters(
            method=method,
            start_index=start_index,
            end_index=end_index
        )
        
        return AnalysisResult(
            analysis_type=AnalysisType.DERIVATIVE,
            source_columns=[str(y_data.name)],
            x_data=x_slice,
            y_data=y_slice,
            result_data=pd.Series(derivative, index=x_slice.index),
            parameters=parameters,
            statistics=statistics,
            metadata={"method_used": method}
        )
    
    @staticmethod
    def calculate_integral(
        x_data: pd.Series,
        y_data: pd.Series,
        start_index: int = 0,
        end_index: int = -1
    ) -> AnalysisResult:
        """
        Calculate integral using trapezoidal rule.
        
        Args:
            x_data: X-axis data
            y_data: Y-axis data
            start_index: Start index for calculation
            end_index: End index for calculation
            
        Returns:
            AnalysisResult containing integral data
        """
        # Handle data slicing
        if end_index == -1:
            end_index = len(x_data)
        
        x_slice = x_data.iloc[start_index:end_index]
        y_slice = y_data.iloc[start_index:end_index]
        
        # Calculate cumulative integral
        try:
            integral_values = cumulative_trapezoid(y_slice, x_slice, initial=0)
            total_integral = trapezoid(y_slice, x_slice)
        except ImportError:
            # Fallback to numpy functions
            integral_values = np.cumsum((y_slice[:-1] + y_slice[1:]) / 2 * np.diff(x_slice))
            integral_values = np.insert(integral_values, 0, 0)
            total_integral = np.trapz(y_slice, x_slice)
        
        statistics = {
            "total_integral": float(total_integral),
            "final_value": float(integral_values[-1]),
            "mean_rate": float(total_integral / (x_slice.iloc[-1] - x_slice.iloc[0])) if len(x_slice) > 1 else 0.0
        }
        
        parameters = AnalysisParameters(
            start_index=start_index,
            end_index=end_index
        )
        
        return AnalysisResult(
            analysis_type=AnalysisType.INTEGRAL,
            source_columns=[str(y_data.name)],
            x_data=x_slice,
            y_data=y_slice,
            result_data=pd.Series(integral_values, index=x_slice.index),
            parameters=parameters,
            statistics=statistics,
            metadata={"method": "trapezoidal"}
        )
    
    @staticmethod
    def calculate_arc_length(
        x_data: pd.Series,
        y_data: pd.Series,
        start_index: int = 0,
        end_index: int = -1
    ) -> AnalysisResult:
        """
        Calculate cumulative arc length along curve.
        
        Args:
            x_data: X-axis data
            y_data: Y-axis data
            start_index: Start index for calculation
            end_index: End index for calculation
            
        Returns:
            AnalysisResult containing arc length data
        """
        # Handle data slicing
        if end_index == -1:
            end_index = len(x_data)
        
        x_slice = x_data.iloc[start_index:end_index]
        y_slice = y_data.iloc[start_index:end_index]
        
        # Calculate arc length
        dx = np.diff(x_slice)
        dy = np.diff(y_slice)
        arc_segments = np.sqrt(dx**2 + dy**2)
        cumulative_length = np.cumsum(arc_segments)
        cumulative_length = np.insert(cumulative_length, 0, 0)  # Start from 0
        total_length = np.sum(arc_segments)
        
        statistics = {
            "total_length": float(total_length),
            "mean_segment": float(np.mean(arc_segments)) if len(arc_segments) > 0 else 0.0,
            "max_segment": float(np.max(arc_segments)) if len(arc_segments) > 0 else 0.0
        }
        
        parameters = AnalysisParameters(
            start_index=start_index,
            end_index=end_index
        )
        
        return AnalysisResult(
            analysis_type=AnalysisType.ARC_LENGTH,
            source_columns=[str(x_data.name), str(y_data.name)],
            x_data=x_slice,
            y_data=y_slice,
            result_data=pd.Series(cumulative_length, index=x_slice.index),
            parameters=parameters,
            statistics=statistics,
            metadata={"method": "euclidean_distance"}
        )
    
    @staticmethod
    def smooth_data(
        x_data: pd.Series,
        y_data: pd.Series,
        method: str = "savgol",
        start_index: int = 0,
        end_index: int = -1,
        **kwargs
    ) -> AnalysisResult:
        """
        Smooth data using specified method.
        
        Args:
            x_data: X-axis data
            y_data: Y-axis data
            method: Smoothing method ('savgol', 'lowess', 'rolling_mean')
            start_index: Start index for smoothing
            end_index: End index for smoothing
            **kwargs: Additional parameters for smoothing methods
            
        Returns:
            AnalysisResult containing smoothed data
        """
        # Handle data slicing
        if end_index == -1:
            end_index = len(x_data)
        
        x_slice = x_data.iloc[start_index:end_index]
        y_slice = y_data.iloc[start_index:end_index]
        
        # Apply smoothing based on method
        if method == SmoothingMethod.SAVGOL.value:
            window_length = kwargs.get("window_length", min(11, len(y_slice) // 2 * 2 + 1))
            poly_order = kwargs.get("polynomial_order", min(3, window_length - 1))
            # Ensure window_length is odd and >= poly_order + 1
            if window_length % 2 == 0:
                window_length += 1
            window_length = max(window_length, poly_order + 1)
            smoothed = savgol_filter(y_slice, window_length, poly_order)
            
        elif method == SmoothingMethod.ROLLING_MEAN.value:
            window = kwargs.get("window", min(5, len(y_slice) // 4))
            smoothed = y_slice.rolling(window=window, center=True).mean().bfill().ffill()
            
        else:  # LOWESS
            try:
                from statsmodels.nonparametric.smoothers_lowess import lowess
                frac = kwargs.get("frac", 0.2)
                result = lowess(y_slice, x_slice, frac=frac)
                smoothed = result[:, 1]
            except ImportError:
                # Fallback to rolling mean if statsmodels not available
                window = kwargs.get("window", 5)
                smoothed = y_slice.rolling(window=window, center=True).mean().bfill().ffill()
        
        # Calculate statistics
        original_std = float(np.std(y_slice))
        smoothed_std = float(np.std(smoothed))
        noise_reduction = ((original_std - smoothed_std) / original_std) * 100 if original_std > 0 else 0
        
        statistics = {
            "original_std": original_std,
            "smoothed_std": smoothed_std,
            "noise_reduction_percent": noise_reduction,
            "correlation": float(np.corrcoef(y_slice, smoothed)[0, 1]) if len(y_slice) > 1 else 1.0
        }
        
        parameters = AnalysisParameters(
            method=method,
            start_index=start_index,
            end_index=end_index,
            additional_params=kwargs
        )
        
        return AnalysisResult(
            analysis_type=AnalysisType.SMOOTHING,
            source_columns=[str(y_data.name)],
            x_data=x_slice,
            y_data=y_slice,
            result_data=pd.Series(smoothed, index=x_slice.index),
            parameters=parameters,
            statistics=statistics,
            metadata={"method_used": method}
        )
    
    @staticmethod
    def interpolate_data(
        x_data: pd.Series,
        y_data: pd.Series,
        method: str = "cubic",
        num_points: Optional[int] = None,
        start_index: int = 0,
        end_index: int = -1
    ) -> AnalysisResult:
        """
        Interpolate data using specified method.
        
        Args:
            x_data: X-axis data
            y_data: Y-axis data
            method: Interpolation method ('linear', 'cubic', 'quadratic', 'nearest')
            num_points: Number of points for interpolation
            start_index: Start index for interpolation
            end_index: End index for interpolation
            
        Returns:
            AnalysisResult containing interpolated data
        """
        # Handle data slicing
        if end_index == -1:
            end_index = len(x_data)
        
        x_slice = x_data.iloc[start_index:end_index]
        y_slice = y_data.iloc[start_index:end_index]
        
        # Determine number of interpolation points
        if num_points is None:
            num_points = len(x_slice) * 2
        
        # Create new x values for interpolation
        x_new = np.linspace(x_slice.min(), x_slice.max(), num_points)
        
        # Adjust method for small datasets
        if len(x_slice) < 4 and method == InterpolationMethod.CUBIC.value:
            method = InterpolationMethod.LINEAR.value
        
        # Perform interpolation
        if method == InterpolationMethod.CUBIC.value:
            try:
                cs = CubicSpline(x_slice, y_slice)
                y_new = cs(x_new)
            except Exception:
                # Fallback to linear interpolation
                f = interp1d(x_slice, y_slice, kind="linear")
                y_new = f(x_new)
        else:
            f = interp1d(x_slice, y_slice, kind=method)
            y_new = f(x_new)
        
        statistics = {
            "original_points": len(x_slice),
            "interpolated_points": num_points,
            "x_range": float(x_slice.max() - x_slice.min()),
            "point_density_ratio": float(num_points / len(x_slice))
        }
        
        parameters = AnalysisParameters(
            method=method,
            num_points=num_points,
            start_index=start_index,
            end_index=end_index
        )
        
        return AnalysisResult(
            analysis_type=AnalysisType.INTERPOLATION,
            source_columns=[str(y_data.name)],
            x_data=pd.Series(x_new),
            y_data=y_slice,
            result_data=pd.Series(y_new),
            parameters=parameters,
            statistics=statistics,
            metadata={"method_used": method}
        )

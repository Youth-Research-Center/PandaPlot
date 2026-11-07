"""Help topics for curve fitting.

Model names, equations, parameter names and categories are read from
``FIT_DEFINITIONS`` (and the custom-function names from ``CUSTOM_FUNCTION_NAMES``)
when ``topics()`` is called. The typical-use text and the one-line meaning of
every parameter are written here.
"""

from dataclasses import dataclass
from typing import cast

from pandaplot.analysis.signal.signal_types import SignalAnalysisType
from pandaplot.services.fit.fit_service import CUSTOM_FUNCTION_NAMES, FIT_DEFINITIONS
from pandaplot.services.help.content.descriptive import DESCRIPTIVE_OVERVIEW_TOPIC_ID
from pandaplot.services.help.content.panel_defaults import FIT_POINTS
from pandaplot.services.help.content.signal import SIGNAL_TOPIC_IDS
from pandaplot.services.help.help_types import (
    FIT_TOPIC_CUSTOM,
    FIT_TOPIC_OVERVIEW,
    PANEL_TOPIC_CHART_ANALYSIS,
    PANEL_TOPIC_FIT,
    HelpCategory,
    HelpTopic,
    fit_topic_id,
)

CUSTOM_FUNCTION_NAME = "Custom Function"

FIT_MODEL_TOPIC_IDS: dict[str, str] = {
    "Linear": fit_topic_id("Linear"),
    "Quadratic": fit_topic_id("Quadratic"),
    "Cubic": fit_topic_id("Cubic"),
    "Quartic": fit_topic_id("Quartic"),
    "Quintic": fit_topic_id("Quintic"),
    "Exponential": fit_topic_id("Exponential"),
    "Exponential Decay": fit_topic_id("Exponential Decay"),
    "Exponential Growth to Maximum": fit_topic_id("Exponential Growth to Maximum"),
    "Logistic Sigmoid": fit_topic_id("Logistic Sigmoid"),
    "Gaussian Peak": fit_topic_id("Gaussian Peak"),
    "Lorentzian Peak": fit_topic_id("Lorentzian Peak"),
    "Sine": fit_topic_id("Sine"),
    "Cosine": fit_topic_id("Cosine"),
    "Damped Sine": fit_topic_id("Damped Sine"),
    "Power": fit_topic_id("Power"),
    "Logarithmic": fit_topic_id("Logarithmic"),
    CUSTOM_FUNCTION_NAME: FIT_TOPIC_CUSTOM,
}


@dataclass(frozen=True)
class _ModelText:
    """Hand-written help text for one fit model.

    Attributes:
        summary: When to use the model, in one or two sentences.
        explanation: Fuller plain-language description of the curve.
        parameters: Meaning of each parameter, as (name, meaning) pairs.
        keywords: Extra search terms.
        related: Names of related models (``FIT_DEFINITIONS`` keys).
    """

    summary: str
    explanation: str
    parameters: tuple[tuple[str, str], ...]
    keywords: tuple[str, ...] = ()
    related: tuple[str, ...] = ()


def _polynomial_parameters(*meanings: str) -> tuple[tuple[str, str], ...]:
    names = "abcdef"
    return tuple(zip(names, meanings, strict=False))


_POLYNOMIAL_NOTE = (
    "Higher degrees can follow the data more closely, but they can also start to follow the noise and swing wildly outside the "
    "measured range. Use the lowest degree that describes the data well."
)

_MODEL_TEXT: dict[str, _ModelText] = {
    "Linear": _ModelText(
        summary="Fits a straight line. Use it when y changes by the same amount for every step in x.",
        explanation=(
            "This is the simplest fit. The slope tells you how much y changes when x increases by 1, and the intercept is the "
            "value of y at x = 0. Typical uses are calibration lines, constant speed (distance against time) and Ohm's law "
            "(voltage against current).\n\n"
            "If the points curve away from the line, try a higher polynomial or one of the other models."
        ),
        parameters=_polynomial_parameters("The slope: how much y changes for each increase of 1 in x.", "The intercept: the value of y at x = 0."),
        keywords=("line", "straight line", "linear regression", "trendline", "best fit line", "slope", "intercept", "least squares"),
        related=("Quadratic", "Power"),
    ),
    "Quadratic": _ModelText(
        summary="Fits a parabola. Use it for a single smooth bend, such as a ball's height over time.",
        explanation=(
            "A quadratic has one turning point, a maximum or a minimum. If a is positive the curve opens upwards, if it is "
            "negative it opens downwards. Typical uses are projectile motion and the position of a uniformly accelerating object.\n\n"
            + _POLYNOMIAL_NOTE
        ),
        parameters=_polynomial_parameters(
            "The coefficient of x². Its sign sets whether the curve opens upwards (positive) or downwards (negative); "
            "a larger size makes the bend tighter.",
            "The coefficient of x. It shifts the turning point sideways together with a.",
            "The constant term: the value of y at x = 0.",
        ),
        keywords=("parabola", "polynomial", "degree 2", "second order", "projectile"),
        related=("Linear", "Cubic"),
    ),
    "Cubic": _ModelText(
        summary="Fits a degree-3 polynomial. Use it for data with an S-shaped wiggle: two bends at most.",
        explanation="A cubic can rise, level off, and rise again, or turn around twice.\n\n" + _POLYNOMIAL_NOTE,
        parameters=_polynomial_parameters(
            "The coefficient of x³.", "The coefficient of x².", "The coefficient of x.", "The constant term: the value of y at x = 0."
        ),
        keywords=("polynomial", "degree 3", "third order"),
        related=("Quadratic", "Quartic"),
    ),
    "Quartic": _ModelText(
        summary="Fits a degree-4 polynomial. Use it only when a lower degree clearly cannot follow the data.",
        explanation="A quartic can have up to three turning points.\n\n" + _POLYNOMIAL_NOTE,
        parameters=_polynomial_parameters(
            "The coefficient of x⁴.",
            "The coefficient of x³.",
            "The coefficient of x².",
            "The coefficient of x.",
            "The constant term: the value of y at x = 0.",
        ),
        keywords=("polynomial", "degree 4", "fourth order"),
        related=("Cubic", "Quintic"),
    ),
    "Quintic": _ModelText(
        summary="Fits a degree-5 polynomial. It is very flexible, so check that it does not just follow the noise.",
        explanation="A quintic can have up to four turning points.\n\n" + _POLYNOMIAL_NOTE,
        parameters=_polynomial_parameters(
            "The coefficient of x⁵.",
            "The coefficient of x⁴.",
            "The coefficient of x³.",
            "The coefficient of x².",
            "The coefficient of x.",
            "The constant term: the value of y at x = 0.",
        ),
        keywords=("polynomial", "degree 5", "fifth order"),
        related=("Quartic", "Cubic"),
    ),
    "Exponential": _ModelText(
        summary="Fits a curve that grows or shrinks by the same percentage for every step in x, plus a constant level.",
        explanation=(
            "Use it for unrestricted growth (b positive), such as bacteria in a nutrient-rich dish, or for decay (b negative). "
            "The curve bends more and more steeply as it grows.\n\n"
            "If you know the quantity falls towards a steady level, the Exponential Decay model is usually the better choice "
            "because its rate is kept positive."
        ),
        parameters=(
            ("a", "The scale: the size of the exponential part at x = 0, so y = a + c there."),
            ("b", "The rate. Positive means growth, negative means decay; larger sizes change faster."),
            ("c", "The offset: the level the curve approaches when b is negative and x gets large."),
        ),
        keywords=("exponential growth", "exp", "growth", "e^x", "compound"),
        related=("Exponential Decay", "Exponential Growth to Maximum", "Power"),
    ),
    "Exponential Decay": _ModelText(
        summary="Fits a quantity that falls quickly at first and then levels off towards a steady value.",
        explanation=(
            "Typical uses are radioactive decay, a hot object cooling to room temperature and a capacitor discharging. "
            "The decay rate b is kept at 0 or above by the fit.\n\n"
            "The time constant is 1/b: after that much x, the part above the final level has dropped to about 37% of its start."
        ),
        parameters=(
            ("a", "The starting amount above the final level: at x = 0 the curve is at a + c."),
            ("b", "The decay rate, kept at 0 or above. A larger value means a faster drop; 1/b is the time constant."),
            ("c", "The offset: the steady value the curve levels off at for large x."),
        ),
        keywords=("decay", "exponential decay", "half-life", "half life", "time constant", "cooling", "discharge", "radioactive"),
        related=("Exponential Growth to Maximum", "Exponential"),
    ),
    "Exponential Growth to Maximum": _ModelText(
        summary="Fits a quantity that rises quickly at first and then levels off towards a maximum.",
        explanation=(
            "Typical uses are a capacitor charging, a reaction approaching completion and learning curves. It is the mirror image "
            "of Exponential Decay. The rate b is kept at 0 or above by the fit.\n\n"
            "The curve starts at c when x = 0 and approaches a + c as x grows."
        ),
        parameters=(
            ("a", "The total rise: the curve levels off at a + c."),
            ("b", "The rate, kept at 0 or above. A larger value means the maximum is reached sooner; 1/b is the time constant."),
            ("c", "The offset: the value of y at x = 0."),
        ),
        keywords=("saturation", "charging", "approach to maximum", "asymptote", "plateau", "growth", "time constant"),
        related=("Exponential Decay", "Logistic Sigmoid"),
    ),
    "Logistic Sigmoid": _ModelText(
        summary="Fits an S-shaped step between two levels. Use it for switching, saturation and population growth with a limit.",
        explanation=(
            "The curve stays near one level, rises smoothly around the midpoint and settles at a second level. Typical uses are "
            "dose-response curves, population growth limited by food, and titration curves.\n\n"
            "A negative steepness gives a falling step instead of a rising one."
        ),
        parameters=(
            ("a", "The height of the step: the curve moves from c to a + c."),
            ("b", "The steepness: larger sizes make a sharper step. A negative value turns the step into a falling one."),
            ("x0", "The midpoint: the x value where the curve is halfway through the step."),
            ("c", "The offset: the lower level, reached far to the left of the midpoint when b is positive."),
        ),
        keywords=("sigmoid", "s-curve", "s curve", "logistic", "step", "dose response", "growth curve", "saturation"),
        related=("Exponential Growth to Maximum", "Gaussian Peak"),
    ),
    "Gaussian Peak": _ModelText(
        summary="Fits a bell-shaped peak. Use it for a single peak with symmetric, quickly fading sides.",
        explanation=(
            "Typical uses are spectral lines broadened by many small effects, measurement noise distributions and a single pulse. "
            "The width sigma is kept above 0 by the fit.\n\n"
            "The full width of the peak at half its height is about 2.355 times sigma."
        ),
        parameters=(
            ("a", "The amplitude: the height of the peak above the offset."),
            ("x0", "The centre: the x value of the top of the peak."),
            ("sigma", "The width (standard deviation), kept above 0. About two thirds of the peak's area lies within one sigma of the centre."),
            ("c", "The offset: the baseline the peak sits on."),
        ),
        keywords=("gaussian", "normal curve", "bell curve", "bell", "peak", "fwhm", "spectrum", "pulse"),
        related=("Lorentzian Peak", "Logistic Sigmoid"),
    ),
    "Lorentzian Peak": _ModelText(
        summary="Fits a peak with a narrow top and wide, slowly fading tails. Use it for resonances and many spectral lines.",
        explanation=(
            "Compared with a Gaussian peak of the same height and width, the Lorentzian has a sharper top and heavier tails. "
            "Typical uses are resonance curves and spectral lines of atoms. The width gamma is kept above 0 by the fit.\n\n"
            "If a Gaussian fit leaves the tails of your peak under-fitted, try this model."
        ),
        parameters=(
            ("a", "The amplitude: the height of the peak above the offset."),
            ("x0", "The centre: the x value of the top of the peak."),
            ("gamma", "The half width at half maximum, kept above 0: the peak has fallen to half its height at x0 ± gamma."),
            ("c", "The offset: the baseline the peak sits on."),
        ),
        keywords=("lorentzian", "lorentz", "cauchy", "resonance", "peak", "spectral line", "hwhm"),
        related=("Gaussian Peak",),
    ),
    "Sine": _ModelText(
        summary="Fits a regular wave that repeats forever with the same size. Use it for oscillations that do not fade.",
        explanation=(
            "Typical uses are alternating current, a swinging pendulum with small losses, and seasonal cycles. The frequency b is in "
            "radians per x unit, so the period (the x length of one full cycle) is 2π / b.\n\n"
            "Fitting a wave is sensitive to the starting frequency. PandaPlot estimates it from the strongest frequency in the data. "
            "If the fit does not follow the wave, check that the data covers several cycles."
        ),
        parameters=(
            ("a", "The amplitude: how far the wave rises above and falls below its middle line."),
            ("b", "The angular frequency in radians per x unit. The period is 2π / b."),
            ("c", "The phase in radians: shifts the wave left or right. At x = 0 the wave sits at a·sin(c) + d."),
            ("d", "The offset: the middle line the wave oscillates around."),
        ),
        keywords=("sin", "sinusoid", "sinusoidal", "wave", "oscillation", "periodic", "frequency", "period", "harmonic"),
        related=("Cosine", "Damped Sine"),
    ),
    "Cosine": _ModelText(
        summary="Fits a regular wave like the Sine model, but starting at its top when the phase is 0.",
        explanation=(
            "A cosine is a sine shifted by a quarter of a cycle, so the two models describe the same curves with different phase "
            "values. Choose the one whose phase is easiest to read: use Cosine when the oscillation starts at its maximum "
            "at x = 0.\n\n"
            "The frequency b is in radians per x unit, so the period is 2π / b."
        ),
        parameters=(
            ("a", "The amplitude: how far the wave rises above and falls below its middle line."),
            ("b", "The angular frequency in radians per x unit. The period is 2π / b."),
            ("c", "The phase in radians: shifts the wave left or right. At x = 0 the wave sits at a·cos(c) + d."),
            ("d", "The offset: the middle line the wave oscillates around."),
        ),
        keywords=("cos", "cosine wave", "wave", "oscillation", "periodic", "frequency", "period", "harmonic"),
        related=("Sine", "Damped Sine"),
    ),
    "Damped Sine": _ModelText(
        summary="Fits a wave whose size shrinks over time. Use it for oscillations that die out, such as a pendulum with friction.",
        explanation=(
            "The amplitude falls off exponentially while the wave keeps oscillating. Typical uses are a mass on a spring with "
            "friction, a ringing circuit and a struck tuning fork. The damping k is kept at 0 or above by the fit.\n\n"
            "The envelope of the wave shrinks by a factor of e (about 2.7) every 1/k in x."
        ),
        parameters=(
            ("a", "The starting amplitude of the wave at x = 0."),
            ("k", "The damping rate, kept at 0 or above. A larger value means the oscillation dies out sooner."),
            ("b", "The angular frequency in radians per x unit. The period is 2π / b."),
            ("c", "The phase in radians: shifts the wave left or right."),
            ("d", "The offset: the middle line the wave oscillates around and settles on."),
        ),
        keywords=("damped", "damping", "decaying oscillation", "ringing", "oscillation", "pendulum", "spring", "periodic"),
        related=("Sine", "Exponential Decay"),
    ),
    "Power": _ModelText(
        summary="Fits y = a·x^b + c. Use it when y scales with a power of x, such as area with length squared.",
        explanation=(
            "When the offset c is 0, a power law is a straight line on a log-log chart, and the exponent b is its slope. Typical uses are the area of a "
            "circle against its radius (b = 2), the period of a pendulum against its length (b = 0.5) and many scaling laws.\n\n"
            "The model needs positive x values. When you set the Fit Range yourself, its Min must be above 0."
        ),
        parameters=(
            ("a", "The scale factor in front of the power."),
            ("b", "The exponent: 1 gives a line, 2 a parabola, 0.5 a square root, negative values a curve that falls."),
            ("c", "The offset: a constant added to the result."),
        ),
        keywords=("power law", "scaling", "exponent", "allometric", "x^b", "square root", "log-log"),
        related=("Logarithmic", "Exponential", "Quadratic"),
    ),
    "Logarithmic": _ModelText(
        summary="Fits y = a·ln(x) + b. Use it for growth that keeps rising but more and more slowly.",
        explanation=(
            "Typical uses are sensor responses that saturate gradually, sound level against intensity and the diminishing "
            "returns of an extra effort. The logarithm is the natural logarithm (ln).\n\n"
            "The model needs positive x values. When you set the Fit Range yourself, its Min must be above 0."
        ),
        parameters=(
            ("a", "The scale: how much y changes each time x is multiplied by e (about 2.718)."),
            ("b", "The offset: the value of y at x = 1, where ln(x) is 0."),
        ),
        keywords=("log", "ln", "natural logarithm", "diminishing returns", "logarithm"),
        related=("Power", "Exponential Growth to Maximum"),
    ),
}


def _model_steps(name: str, category: str, description: str) -> tuple[str, ...]:
    return (
        "Open a chart tab and open the Curve Fitting panel in the sidebar.",
        "Under Data Source, choose the Chart Series to fit, or choose Custom... to pick a Dataset with an X Column and a Y Column.",
        f"Under Fit Configuration, choose the Category {category} and then the Model {name} ({description}).",
        "Click Perform Fit. The fitted parameters, their uncertainties and the Equation appear under Fit Results.",
        "Click Apply to draw the fitted curve on the chart.",
    )


def _overview_topic() -> HelpTopic:
    return HelpTopic(
        id=FIT_TOPIC_OVERVIEW,
        title="Curve fitting",
        category=HelpCategory.FITTING,
        summary=(
            "Finds the curve of a chosen shape that comes closest to your data points and reports the numbers that define it."
        ),
        steps=(
            "Open a chart tab and open the Curve Fitting panel in the sidebar.",
            "Under Data Source, choose the Chart Series to fit. Choose Custom... to pick any dataset with an X Column and a Y Column.",
            "Under Fit Configuration, choose a Category and a Model, or the Category Custom and Model Custom Function to type your own formula.",
            "Optionally set Fit Points, Show Confidence Bands, Calculate R² and the Fit Range.",
            "Click Perform Fit and read the parameters, R² and Equation under Fit Results.",
            "Click Apply to draw the fitted curve on the chart. Click Clear Results to start over.",
        ),
        explanation=(
            "A fit chooses the values of a model's parameters so that the curve passes as close as possible to the data points. "
            "PandaPlot uses non-linear least squares: it adjusts the parameters to make the sum of the squared vertical distances "
            "between points and curve as small as possible. Pick a model that matches the physics or the shape of your data, "
            "not just the one that looks closest.\n\n"
            "R² tells you how much of the variation in y the curve explains. 1 means the curve passes through every point, 0 means "
            "it does no better than a horizontal line at the average of y. A high R² does not prove that the model is right, so also "
            "look at the curve on the chart. R² is calculated when Calculate R² is checked (the default).\n\n"
            "Each fitted parameter is shown as value ± uncertainty. The uncertainty is a standard error estimated from how well the "
            "data pins the parameter down; a small one means the parameter is well determined. When it cannot be estimated, the "
            "result says '(no error estimate)'.\n\n"
            "If the series has Y error bars, they are used as the uncertainty of each point, so points with small error bars "
            "count more. This is called a weighted fit. If any error value is zero, negative or missing, the error bars are ignored "
            "and every point counts equally.\n\n"
            "Show Confidence Bands draws a shaded region around the curve in which the true curve is expected to lie with about 95% "
            "certainty. It needs more data points than the model has free parameters.\n\n"
            f"Fit Points is the number of points used to draw the smooth curve ({FIT_POINTS.default} by default). The Fit Range sets the x interval over "
            "which that curve is drawn: Auto uses the range of the data, and unchecking Auto lets you enter a Min and a Max. "
            "The fit itself still uses all valid data points of the series, so choose a custom range to extend the curve "
            "beyond the data or to draw only part of it."
        ),
        parameters=(
            ("Chart Series", "The series of the open chart whose points are fitted. Choose Custom... to pick any dataset and columns instead."),
            ("Category", "Groups the models by kind of curve, for example Polynomial, Exponential, Peak or Periodic."),
            ("Model", "The shape of the curve to fit. Each model has its own topic."),
            (
                "Fit Points",
                f"How many points are used to draw the fitted curve ({FIT_POINTS.minimum} to {FIT_POINTS.maximum}, default {FIT_POINTS.default}).",
            ),
            ("Show Confidence Bands", "Draws a band showing where the fitted curve is likely to lie (about 95% confidence). Off by default."),
            ("Calculate R²", "Reports R², the share of the variation in y that the curve explains. On by default."),
            ("Fit Range", "The x interval over which the fitted curve is drawn. Auto uses the range of the data."),
        ),
        keywords=(
            "fit", "regression", "least squares", "best fit", "trendline", "trend line", "r squared", "r2", "r-squared",
            "goodness of fit", "parameters", "uncertainty", "confidence band", "weighted fit", "error bars", "curve_fit", "fit range", "fit points",
        ),
        related=(
            PANEL_TOPIC_FIT,
            PANEL_TOPIC_CHART_ANALYSIS,
            FIT_TOPIC_CUSTOM,
            FIT_MODEL_TOPIC_IDS["Linear"],
            FIT_MODEL_TOPIC_IDS["Exponential Decay"],
            FIT_MODEL_TOPIC_IDS["Gaussian Peak"],
            DESCRIPTIVE_OVERVIEW_TOPIC_ID,
        ),
    )


def _custom_topic() -> HelpTopic:
    names = ", ".join(CUSTOM_FUNCTION_NAMES)
    return HelpTopic(
        id=FIT_TOPIC_CUSTOM,
        title="Custom function fit",
        category=HelpCategory.FITTING,
        summary="Fits a formula you type yourself, for cases the built-in models do not cover.",
        steps=(
            "Open a chart tab and open the Curve Fitting panel in the sidebar.",
            "Under Fit Configuration, choose the Category Custom and the Model Custom Function.",
            "In Function, type a formula in x, for example a*x**2 + b*x + c. The Functions button inserts a function name for you.",
            "In Parameters, list the names of the quantities to find, separated by commas, for example a, b, c.",
            (
                "Optionally, in Define parameters values, fix some parameters to known numbers, for example b=2.1, c=1. Those are "
                "not fitted; the rest are."
            ),
            "Click Perform Fit, then Apply to draw the curve on the chart.",
        ),
        explanation=(
            "Write the formula with x as the variable and one name for every number the fit should find. Use * for "
            "multiplication and ** for powers, so x squared is x**2.\n\n"
            f"These functions can be used by name: {names}. Note that log is the natural logarithm. np (NumPy) is also available, "
            "so np.pi gives π.\n\n"
            "Every parameter that is not fixed starts at 1, so formulas whose parameters are far from 1 may need help: fix the "
            "ones you know, or choose a built-in model that estimates its own starting values. At least one parameter must "
            "remain free, and every name in the formula must be either x, a listed parameter, one of the function names or np."
        ),
        parameters=(
            ("Function", "The formula to fit, written in x and your parameter names. Example: a*exp(-b*x) + c."),
            ("Parameters", "The names of the numbers to find, separated by commas. Example: a, b, c."),
            ("Define parameters values", "Optional. Parameters held at a fixed value instead of being fitted, written name=value and separated by commas."),
            ("Functions", "A menu that inserts one of the allowed function names into the formula."),
        ),
        keywords=("custom", "formula", "own equation", "user defined", "user-defined", "expression", "fixed parameters", "model"),
        related=(FIT_TOPIC_OVERVIEW, PANEL_TOPIC_FIT, FIT_MODEL_TOPIC_IDS["Exponential Decay"], FIT_MODEL_TOPIC_IDS["Sine"]),
    )


def _model_topic(name: str) -> HelpTopic:
    definition = FIT_DEFINITIONS[name]
    text = _MODEL_TEXT[name]
    meanings = dict(text.parameters)
    category = cast(str, definition["category"])
    description = cast(str, definition["description"])
    equation = cast(str, definition["equation"])
    parameter_names = cast(list[str], definition["parameters"])
    siblings = [other for other, other_definition in FIT_DEFINITIONS.items() if other != name and other_definition["category"] == category]
    related_models = list(dict.fromkeys([*text.related, *siblings]))
    related = [PANEL_TOPIC_FIT, FIT_TOPIC_OVERVIEW, *(FIT_MODEL_TOPIC_IDS[other] for other in related_models)]
    if category == "Periodic":
        related.append(SIGNAL_TOPIC_IDS[SignalAnalysisType.FFT])
    return HelpTopic(
        id=FIT_MODEL_TOPIC_IDS[name],
        title=f"{name} fit",
        category=HelpCategory.FITTING,
        summary=text.summary,
        steps=_model_steps(name, category, description),
        explanation=text.explanation,
        parameters=tuple((parameter, meanings[parameter]) for parameter in parameter_names),
        formula=f"y = {equation}",
        keywords=(name.lower(), *text.keywords),
        related=tuple(related),
    )


def topics() -> list[HelpTopic]:
    """Return the help topics of this module.

    Returns:
        The curve fitting overview, one topic per ``FIT_DEFINITIONS`` model and the custom function topic.
    """
    return [_overview_topic(), *(_model_topic(name) for name in FIT_DEFINITIONS), _custom_topic()]

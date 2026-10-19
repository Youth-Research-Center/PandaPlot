"""Shared safe-expression engine for transform-style features.

Used by the dataset Transform panel (TransformController), the chart
Transform panel (TransformChartSeriesCommand, #268) and persisted formula
columns (#154) so all of them validate and evaluate expressions through one
implementation instead of several.

Expressions are user-authored -- and, for formula columns, come back out of
project files -- so evaluation never trusts the caller to have vetted them:

* :func:`compile_expression` checks the parsed syntax tree against an
  allowlist (no private attributes, no file/pickle/eval entry points, no
  generator expressions, ...).
* :func:`evaluate_expression` runs the result with no builtins beyond the ones
  :func:`build_safe_globals` hands out, and with ``np`` / ``pd`` wrapped so
  that they never yield a module.

This is a guard against the introspection and file/import routes into the
interpreter, not a sandbox against everything pandas and numpy objects can do;
open project files from sources you trust.
"""

import ast
import inspect
import re
from types import CodeType
from typing import Any

import numpy as np
import pandas as pd


class UnsafeExpressionError(ValueError):
    """Raised for an expression that uses syntax or names outside the supported dialect."""


_DANGEROUS_PATTERNS = [
    r"\bimport\b", r"\bexec\b", r"\beval\b", r"\b__.*__\b",
    r"\bopen\b", r"\bfile\b", r"\bwith\b.*open",
    r"\bos\.\b", r"\bsys\.\b", r"\bsubprocess\b",
    r"\bglobals\b", r"\blocals\b", r"\bvars\b",
    r"\bdir\b", r"\bgetattr\b", r"\bsetattr\b", r"\bdelattr\b",
]

_PANDAS_FUNCTIONS = [
    "to_datetime", "to_numeric", "isna", "notna", "cut", "qcut",
    "concat", "merge", "pivot_table", "crosstab",
]

_NUMPY_FUNCTIONS = [
    "sqrt", "log", "log10", "exp", "sin", "cos", "tan",
    "mean", "median", "std", "var", "percentile", "quantile",
    "floor", "ceil", "round", "absolute", "sign",
]

# Syntax the expression dialect may use. Everything else -- assignment and
# walrus, await/yield, generator expressions (their frames reach the caller's
# globals), star-args -- is rejected. Operator nodes are matched by their
# abstract base classes.
_ALLOWED_NODES: tuple[type[ast.AST], ...] = (
    ast.Expression, ast.Constant, ast.Name, ast.expr_context,
    ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare, ast.IfExp,
    ast.operator, ast.unaryop, ast.boolop, ast.cmpop,
    ast.Call, ast.keyword, ast.Attribute, ast.Subscript, ast.Slice,
    ast.Tuple, ast.List, ast.Dict, ast.Set,
    ast.ListComp, ast.SetComp, ast.DictComp, ast.comprehension,
    ast.Lambda, ast.arguments, ast.arg,
    ast.JoinedStr, ast.FormattedValue,
)

# Attributes refused wherever they appear -- by the syntax-tree check and by the
# np / pd proxies -- on top of anything starting with an underscore.
_BLOCKED_ATTRIBUTES = frozenset({
    # str.format / str.format_map walk "{0.attr[key]}" lookups from inside the
    # string, which would bypass the attribute checks. f-strings are the
    # supported way to format text: their expressions are checked like any other.
    "format", "format_map",
    # Frame and code introspection (reaching the caller's globals and builtins).
    "gi_frame", "gi_code", "gi_yieldfrom", "cr_frame", "cr_code", "cr_await",
    "ag_frame", "ag_code", "f_back", "f_builtins", "f_globals", "f_locals",
    "tb_frame", "tb_next",
    # Evaluating further code.
    "eval", "query",
    # Entry points into matplotlib (figures can be saved anywhere), jinja2 (via
    # Styler) and ctypes -- none of which a formula has any use for.
    "plot", "hist", "boxplot", "style", "savefig", "ctypes",
    # File access and (de)serialisation on pandas and numpy objects.
    "load", "loadtxt", "genfromtxt", "fromfile", "fromregex", "memmap", "DataSource",
    "save", "savez", "savez_compressed", "savetxt", "tofile", "dump",
    "ExcelFile", "ExcelWriter", "HDFStore",
    "to_pickle", "to_csv", "to_excel", "to_json", "to_hdf", "to_sql", "to_parquet",
    "to_feather", "to_clipboard", "to_stata", "to_xml", "to_orc", "to_latex",
    "to_html", "to_markdown", "to_gbq",
    # to_string(buf=<path>) writes to the filesystem like the to_* writers above.
    "to_string",
})

# Methods that accept a method *name* as a string and look it up with getattr
# (``x.agg("to_csv", path_or_buf=...)``), which would reach a blocked attribute
# without it ever appearing as an attribute in the syntax tree. A string could
# also come from the data itself (``x.agg(x.iloc[0])``), so these calls may only
# be given a callable the checker can see: a lambda or an np/pd/math function.
_NAME_DISPATCH_METHODS = frozenset({"agg", "aggregate", "apply", "transform"})
_CALLABLE_MODULE_ROOTS = frozenset({"np", "pd", "math"})


def _is_blocked_attribute(name: str) -> bool:
    return name.startswith(("_", "read_")) or name in _BLOCKED_ATTRIBUTES


class _ModuleProxy:
    """A module as an expression sees it: attributes, but never another module.

    numpy and pandas import os, sys and friends, so handing out the real
    module would let ``np.testing`` or ``pd.io.common.os`` walk to them. This
    is enforced on the value, at runtime, because no static check on the
    syntax tree can follow ``[np][0].testing`` or ``(lambda m: m.io)(pd)``.
    Submodules named in ``allowed_submodules`` come back as proxies of their
    own, which allow none.
    """

    __slots__ = ("_allowed_submodules", "_module", "_name")

    def __init__(self, module: Any, name: str, allowed_submodules: frozenset[str] = frozenset()):
        self._module = module
        self._name = name
        self._allowed_submodules = allowed_submodules

    def __getattr__(self, attribute: str) -> Any:
        if _is_blocked_attribute(attribute):
            raise UnsafeExpressionError(f"Access to '{attribute}' is not allowed in an expression")
        value = getattr(self._module, attribute)
        if inspect.ismodule(value):
            if attribute not in self._allowed_submodules:
                raise UnsafeExpressionError(f"Access to '{self._name}.{attribute}' is not allowed in an expression")
            return _ModuleProxy(value, f"{self._name}.{attribute}")
        return value

    def __dir__(self) -> list[str]:
        return [name for name in dir(self._module) if not _is_blocked_attribute(name)]


def build_safe_globals() -> dict[str, Any]:
    """Build the globals dict used to eval() a transform expression.

    :func:`evaluate_expression` always strips ``__builtins__`` from whatever it
    is given, so these names are the only builtins an expression can reach.
    """
    safe_globals: dict[str, Any] = {
        "pd": _ModuleProxy(pd, "pd"),
        "np": _ModuleProxy(np, "np", frozenset({"random", "linalg"})),
        "abs": abs,
        "min": min,
        "max": max,
        "sum": sum,
        "len": len,
        "round": round,
        "int": int,
        "float": float,
        "str": str,
        "bool": bool,
        "list": list,
        "dict": dict,
        "range": range,
        "enumerate": enumerate,
        "zip": zip,
        # Pure value builtins: no I/O, no introspection.
        "all": all,
        "any": any,
        "divmod": divmod,
        "pow": pow,
        "reversed": reversed,
        "set": set,
        "sorted": sorted,
        "tuple": tuple,
    }
    for func_name in _PANDAS_FUNCTIONS:
        if hasattr(pd, func_name):
            safe_globals[func_name] = getattr(pd, func_name)
    for func_name in _NUMPY_FUNCTIONS:
        if hasattr(np, func_name):
            safe_globals[func_name] = getattr(np, func_name)
    return safe_globals


def validate_expression(expression: str) -> tuple[bool, str]:
    """Validate a transform expression for safety and syntax.

    Returns (is_valid, error_message); error_message is "" when valid.
    """
    if not expression.strip():
        return False, "Function code cannot be empty"

    for pattern in _DANGEROUS_PATTERNS:
        if re.search(pattern, expression, re.IGNORECASE):
            return False, f"Potentially unsafe operation detected: {pattern}"

    try:
        compile_expression(expression)
    except SyntaxError as e:
        return False, f"Syntax error: {e}"
    except UnsafeExpressionError as e:
        return False, str(e)
    except Exception as e:  # noqa: BLE001 -- Validating an untrusted, user-authored expression -- arbitrary/unknown exceptions are expected here
        return False, f"Code validation error: {e}"

    return True, ""


def _is_private(name: str) -> bool:
    """A leading underscore marks interpreter/library internals; a lone ``_`` is the usual throwaway name."""
    return name.startswith("_") and name != "_"


def _check_node(node: ast.AST) -> None:
    """Raise UnsafeExpressionError if ``node`` is outside the allowed dialect."""
    if not isinstance(node, _ALLOWED_NODES):
        raise UnsafeExpressionError(f"{type(node).__name__} is not allowed in an expression")

    if isinstance(node, ast.Name) and _is_private(node.id):
        raise UnsafeExpressionError(f"The name '{node.id}' is not allowed in an expression")
    if isinstance(node, ast.arg) and _is_private(node.arg):
        raise UnsafeExpressionError(f"The name '{node.arg}' is not allowed in an expression")

    if isinstance(node, ast.Attribute) and _is_blocked_attribute(node.attr):
        raise UnsafeExpressionError(f"Access to '{node.attr}' is not allowed in an expression")

    if isinstance(node, ast.Call):
        _check_dispatch_call(node)


def _is_visible_callable(node: ast.expr) -> bool:
    """A lambda, or a plain ``np.mean`` / ``pd.to_numeric``-style attribute chain."""
    if isinstance(node, ast.Lambda):
        return True
    while isinstance(node, ast.Attribute):
        node = node.value
    return isinstance(node, ast.Name) and node.id in _CALLABLE_MODULE_ROOTS


def _check_dispatch_call(node: ast.Call) -> None:
    """Refuse string-based method dispatch (``x.agg("to_csv")``) and anything that could smuggle one in."""
    if not (isinstance(node.func, ast.Attribute) and node.func.attr in _NAME_DISPATCH_METHODS):
        return
    func_args = [*node.args[:1], *(kw.value for kw in node.keywords if kw.arg == "func")]
    unpacked = any(kw.arg is None for kw in node.keywords)
    if unpacked or len(func_args) != 1 or not _is_visible_callable(func_args[0]):
        raise UnsafeExpressionError(
            f"'{node.func.attr}' must be given a lambda or a numpy/pandas function, not a method name or computed value",
        )


def compile_expression(expression: str) -> CodeType:
    """Parse ``expression``, check it against the allowlist, and compile it.

    Compile once and pass the result to :func:`evaluate_expression` when the
    same expression is evaluated many times (e.g. once per row).

    Raises:
        SyntaxError: If the expression does not parse.
        UnsafeExpressionError: If it uses syntax, names or attributes outside
            the supported dialect.
    """
    tree = ast.parse(expression.strip(), mode="eval")
    for node in ast.walk(tree):
        _check_node(node)
    return compile(tree, "<transform>", "eval")


def evaluate_expression(
    expression: str | CodeType, local_vars: dict[str, Any], safe_globals: dict[str, Any] | None = None,
) -> Any:
    """Evaluate a transform expression against local_vars.

    The expression is checked here, not only by the caller: it may have come
    out of a project file. Builtins are removed explicitly (eval would
    otherwise inject the real ones into a globals dict that lacks the key),
    and ``safe_globals`` is copied rather than modified.

    Callers are expected to catch whatever exception this raises (e.g.
    SyntaxError, UnsafeExpressionError, NameError, TypeError) themselves.

    Raises:
        SyntaxError: If the expression does not parse.
        UnsafeExpressionError: If it is outside the supported dialect.
    """
    code = compile_expression(expression) if isinstance(expression, str) else expression
    if safe_globals is None:
        safe_globals = build_safe_globals()
    # Code objects are expected to come from compile_expression, i.e. to have been through the allowlist.
    return eval(code, {**safe_globals, "__builtins__": {}}, local_vars)


def get_transformation_templates() -> dict[str, list[dict[str, str]]]:
    """Predefined transform-expression templates by category, used by the
    "Insert function" menu in both the dataset and chart Transform panels."""
    return {
        "Math Operations": [
            {"name": "Multiply by 2", "code": "x * 2", "description": "Double the values"},
            {"name": "Square", "code": "x ** 2", "description": "Square the values"},
            {"name": "Square Root", "code": "np.sqrt(x)", "description": "Square root of values"},
            {"name": "Logarithm", "code": "np.log(x)", "description": "Natural logarithm"},
            {"name": "Normalize (Z-score)", "code": "(x - x.mean()) / x.std()", "description": "Standardize to mean=0, std=1"},
        ],
        "String Operations": [
            {"name": "Uppercase", "code": "x.str.upper()", "description": "Convert to uppercase"},
            {"name": "Lowercase", "code": "x.str.lower()", "description": "Convert to lowercase"},
            {"name": "Strip whitespace", "code": "x.str.strip()", "description": "Remove leading/trailing whitespace"},
            {"name": "Extract numbers", "code": "x.str.extract(r'(\\d+)').astype(float)", "description": "Extract numeric values"},
            {"name": "String length", "code": "x.str.len()", "description": "Length of each string"},
        ],
        "Date/Time Operations": [
            {"name": "Parse datetime", "code": "pd.to_datetime(x)", "description": "Convert to datetime"},
            {"name": "Extract year", "code": "pd.to_datetime(x).dt.year", "description": "Extract year component"},
            {"name": "Extract month", "code": "pd.to_datetime(x).dt.month", "description": "Extract month component"},
            {"name": "Day of week", "code": "pd.to_datetime(x).dt.dayofweek", "description": "Day of week (0=Monday)"},
            {"name": "Format date", "code": "pd.to_datetime(x).dt.strftime('%Y-%m-%d')", "description": "Format as YYYY-MM-DD"},
        ],
        "Statistical Operations": [
            {"name": "Rank", "code": "x.rank()", "description": "Rank values (1 = smallest)"},
            {"name": "Percentile rank", "code": "x.rank(pct=True)", "description": "Percentile rank (0-1)"},
            {"name": "Rolling mean", "code": "x.rolling(3).mean()", "description": "3-period rolling average"},
            {"name": "Cumulative sum", "code": "x.cumsum()", "description": "Cumulative sum"},
            {"name": "Lag/Shift", "code": "x.shift(1)", "description": "Shift values by 1 period"},
        ],
    }

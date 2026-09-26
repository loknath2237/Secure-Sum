"""
math_engine.py
Safe parsing of user-entered mathematical functions using SymPy.
Never uses raw eval(). Provides:
  - validate_function(): parse + sanity check
  - make_numeric_function(): fast NumPy-vectorized callable via lambdify
  - exact_integral(): symbolic definite integral when possible

SECURITY NOTE: sympy.parsing.sympy_parser.parse_expr, even with
evaluate=True and a restricted local_dict, ultimately compiles the input
through Python's own parser/eval machinery. Constructs like
__import__('os').system(...) are technically valid Python expression
syntax and can execute arbitrary code before SymPy ever sees a symbol.
We therefore run a strict character/token whitelist BEFORE parsing:
only digits, the variable x, arithmetic operators, parentheses, dots,
commas, spaces, and a fixed set of function-name letters are allowed.
Anything else (double underscores, quotes, brackets, semicolons, etc.)
is rejected outright, closing off attribute/import-based escapes.
"""

import re
import sympy as sp
from sympy.parsing.sympy_parser import (
    parse_expr,
    standard_transformations,
    implicit_multiplication_application,
    convert_xor,
)

x = sp.symbols("x")

_TRANSFORMATIONS = standard_transformations + (
    implicit_multiplication_application,
    convert_xor,
)

# Explicit whitelist of allowed names in the expression namespace.
_ALLOWED_LOCALS = {
    "x": x,
    "sin": sp.sin,
    "cos": sp.cos,
    "tan": sp.tan,
    "exp": sp.exp,
    "log": sp.log,
    "ln": sp.log,
    "sqrt": sp.sqrt,
    "pi": sp.pi,
    "e": sp.E,
    "Abs": sp.Abs,
    "abs": sp.Abs,
}


class FunctionValidationError(Exception):
    pass


# Only these characters may appear in a raw function string at all.
# Letters are needed for function names (sin, cos, sqrt, exp, log, ln, pi, e, x)
# but we separately verify every alphabetic run is a whitelisted name below,
# which blocks dunder/attribute-access tricks like __import__ or os.system.
_ALLOWED_CHARS_RE = re.compile(r"^[0-9a-zA-Z\s\+\-\*/\^\(\)\.\,]*$")
_ALPHA_RUN_RE = re.compile(r"[a-zA-Z_]+")
_ALLOWED_NAMES = set(_ALLOWED_LOCALS.keys())


def _pre_validate_raw_string(cleaned):
    """Character/token whitelist applied BEFORE any parsing occurs."""
    if not _ALLOWED_CHARS_RE.match(cleaned):
        raise FunctionValidationError("Please enter a valid mathematical function.")

    for name in _ALPHA_RUN_RE.findall(cleaned):
        if name not in _ALLOWED_NAMES:
            raise FunctionValidationError(
                f"Unknown term '{name}'. Please enter a valid mathematical function."
            )

    # Defense in depth: explicitly block double underscores regardless of
    # the character whitelist above (dunder attribute-access escapes).
    if "__" in cleaned:
        raise FunctionValidationError("Please enter a valid mathematical function.")


def validate_function(expr_str):
    """
    Safely parse a user-supplied function string into a SymPy expression.
    Raises FunctionValidationError with a friendly message on failure.
    """
    if not expr_str or not expr_str.strip():
        raise FunctionValidationError("Please enter a valid mathematical function.")

    cleaned = expr_str.strip().replace("^", "**")

    # Hard whitelist check BEFORE parsing - closes off code-injection escapes
    # such as __import__('os').system(...) which are otherwise syntactically
    # valid input to SymPy's parser.
    _pre_validate_raw_string(cleaned)

    try:
        expr = parse_expr(
            cleaned,
            local_dict=_ALLOWED_LOCALS,
            transformations=_TRANSFORMATIONS,
            evaluate=True,
        )
    except FunctionValidationError:
        raise
    except Exception:
        raise FunctionValidationError("Please enter a valid mathematical function.")

    # parse_expr can legitimately return a plain Python/SymPy number
    # (e.g. input "5" or "2+3") which has no .free_symbols - treat as constant.
    expr = sp.sympify(expr)

    # Reject anything containing symbols outside our whitelist (e.g. y, z)
    free_symbols = expr.free_symbols
    if free_symbols - {x}:
        raise FunctionValidationError(
            "Function may only use the variable 'x' (e.g. x^2 + 2*x + 1)."
        )

    return expr


def make_numeric_function(expr):
    """Convert a validated SymPy expression into a fast NumPy-vectorized function."""
    try:
        f = sp.lambdify(x, expr, modules=["numpy"])
        # sanity test call
        test = f(1.0)
        float(test)
        return f
    except Exception:
        raise FunctionValidationError(
            "This function cannot be evaluated numerically. Please try another."
        )


def exact_integral(expr, a, b):
    """
    Attempt to compute the exact definite integral symbolically.
    Returns (value_or_None, available_bool).
    """
    try:
        result = sp.integrate(expr, (x, sp.Float(a), sp.Float(b)))
        value = complex(result)
        if abs(value.imag) > 1e-9:
            return None, False
        val = float(value.real)
        if not (val == val) or val in (float("inf"), float("-inf")):  # NaN/inf check
            return None, False
        return val, True
    except Exception:
        return None, False

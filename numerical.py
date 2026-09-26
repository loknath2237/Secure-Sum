"""
numerical.py
Numerical integration methods for SecureSum.
Implements Trapezoidal, Simpson 1/3, Simpson 3/8, and Midpoint rules.
All methods operate on a safe, pre-validated callable f(x).
"""

import time
import numpy as np


def _timed(func):
    """Wrap a rule so it also returns eval count + execution time."""
    def wrapper(f, a, b, n):
        start = time.perf_counter()
        result, evals = func(f, a, b, n)
        elapsed = time.perf_counter() - start
        return {
            "result": float(result),
            "evaluations": int(evals),
            "execution_time": round(elapsed, 6),
        }
    return wrapper


@_timed
def trapezoidal_rule(f, a, b, n):
    """Composite Trapezoidal Rule over n subintervals."""
    n = max(1, int(n))
    x = np.linspace(a, b, n + 1)
    y = f(x)
    h = (b - a) / n
    result = h * (0.5 * y[0] + 0.5 * y[-1] + np.sum(y[1:-1]))
    return result, n + 1


@_timed
def simpson_one_third(f, a, b, n):
    """Composite Simpson's 1/3 Rule. Requires even n (auto-adjusted)."""
    n = max(2, int(n))
    if n % 2 != 0:
        n += 1  # Simpson 1/3 needs an even number of subintervals
    x = np.linspace(a, b, n + 1)
    y = f(x)
    h = (b - a) / n
    result = (h / 3) * (
        y[0] + y[-1] + 4 * np.sum(y[1:-1:2]) + 2 * np.sum(y[2:-1:2])
    )
    return result, n + 1


@_timed
def simpson_three_eighth(f, a, b, n):
    """Composite Simpson's 3/8 Rule. Requires n to be a multiple of 3 (auto-adjusted)."""
    n = max(3, int(n))
    if n % 3 != 0:
        n += (3 - n % 3)
    x = np.linspace(a, b, n + 1)
    y = f(x)
    h = (b - a) / n
    total = y[0] + y[-1]
    for i in range(1, n):
        total += (3 if i % 3 != 0 else 2) * y[i]
    result = (3 * h / 8) * total
    return result, n + 1


@_timed
def midpoint_rule(f, a, b, n):
    """Composite Midpoint Rule over n subintervals."""
    n = max(1, int(n))
    h = (b - a) / n
    midpoints = a + h * (np.arange(n) + 0.5)
    y = f(midpoints)
    result = h * np.sum(y)
    return result, n


METHOD_MAP = {
    "trapezoidal": trapezoidal_rule,
    "simpson13": simpson_one_third,
    "simpson38": simpson_three_eighth,
    "midpoint": midpoint_rule,
}

METHOD_LABELS = {
    "trapezoidal": "Trapezoidal Rule",
    "simpson13": "Simpson 1/3 Rule",
    "simpson38": "Simpson 3/8 Rule",
    "midpoint": "Midpoint Rule",
}


def run_method(method_key, f, a, b, n):
    """Run the requested numerical method by key."""
    if method_key not in METHOD_MAP:
        raise ValueError(f"Unknown numerical method: {method_key}")
    return METHOD_MAP[method_key](f, a, b, n)

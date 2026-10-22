"""Independent verification of numeric / algebraic answers with SymPy.

The model proposes an ``expected_answer``; the child's answer is compared to it *here*, not by the
model, so a wrong model verdict cannot mark a correct child wrong.

Both strings are untrusted (one comes from a child, one from a model that read a photo), so before
anything reaches SymPy we apply a strict grammar: a character whitelist, a length cap, only tiny
integer exponents, no names except a short allow-list, no attribute access, and ``parse_expr`` runs
with an empty ``__builtins__``. Equivalence of expressions is decided by numeric sampling instead of
``simplify`` (bounded cost) and the whole check runs under a wall-clock timeout — a pathological
input yields «uncertain», never a hung worker.
"""

from __future__ import annotations

import random
import re
import threading
from dataclasses import dataclass, field

import sympy
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

_ALLOWED = re.compile(r"^[0-9a-zA-Zа-яА-ЯёЁ\s+\-*/^().,;:=<>≤≥√π%°]+$")
_MAX_LEN = 120
_MAX_DIGITS = 12
_MAX_POWERS = 2
_MAX_EXPONENT = 20
_TIMEOUT_SECONDS = 2.0
_VARIABLES = ("x", "y", "z", "a", "b", "n", "t")
_ALLOWED_NAMES = {"sqrt", "pi", "e", *_VARIABLES}
_TRANSFORMATIONS = standard_transformations + (implicit_multiplication_application, convert_xor)
_LOCALS = {
    "pi": sympy.pi,
    "e": sympy.E,
    "sqrt": sympy.sqrt,
    **{name: sympy.Symbol(name) for name in _VARIABLES},
}
# parse_expr evaluates generated code: give it no builtins and only the sympy names the
# transformations can emit (Integer/Float/Rational/Symbol/Mul/Add/Pow).
_GLOBALS = {
    "__builtins__": {},
    "Integer": sympy.Integer,
    "Float": sympy.Float,
    "Rational": sympy.Rational,
    "Symbol": sympy.Symbol,
    "Mul": sympy.Mul,
    "Add": sympy.Add,
    "Pow": sympy.Pow,
    "sqrt": sympy.sqrt,
    "pi": sympy.pi,
    "E": sympy.E,
}
_UNIT_WORDS = (
    "см",
    "дм",
    "мм",
    "м",
    "км",
    "кг",
    "г",
    "т",
    "л",
    "мл",
    "мин",
    "ч",
    "с",
    "сек",
    "руб",
    "сом",
    "тыйын",
    "шт",
    "штук",
    "штуки",
    "градус",
    "градусов",
    "градуса",
    "cm",
    "mm",
    "m",
    "km",
    "kg",
    "g",
    "l",
    "ml",
)
_UNIT_SUFFIX = re.compile(r"(\d)\s*(" + "|".join(sorted(_UNIT_WORDS, key=len, reverse=True)) + r")\.?$")
_PREFIX = re.compile(r"^(ответ|жооп|итого|получается|получится)\s*[:\-—]?\s*", re.I)


@dataclass
class MathVerdict:
    verdict: str  # correct | incorrect | uncertain
    confidence: float
    details: dict = field(default_factory=dict)


class UnsafeExpression(ValueError):
    pass


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------
def _basic_clean(raw: str) -> str:
    text = raw.strip().lower()
    text = text.replace("×", "*").replace("·", "*").replace("÷", "/").replace("−", "-")
    text = re.sub(r"(\d),(\d)", r"\1.\2", text)  # decimal comma; "2, 3" keeps its list comma
    text = text.replace("√", "sqrt").replace("π", "pi").replace("^", "**").replace("°", "")
    text = re.sub(r"\s+", " ", text).strip()
    text = _PREFIX.sub("", text)
    return text.rstrip(".")


def _strip_units(text: str) -> str:
    previous = None
    while previous != text:
        previous = text
        text = _UNIT_SUFFIX.sub(r"\1", text).strip()
        tokens = text.split(" ")
        while tokens and tokens[-1] in _UNIT_WORDS:
            tokens.pop()
        text = " ".join(tokens).strip()
    return text


def _split_set(text: str) -> list[str]:
    """Several roots/answers: "2; 3", "2, -2", "x=2 и x=-2". Decimal commas were already converted."""
    parts = re.split(r"\s*;\s*|,\s+|\s+и\s+|\s+жана\s+|\s+or\s+|\s+или\s+", text)
    return [p.strip() for p in parts if p.strip()]


def _guard(expr: str) -> str:
    """Reject anything outside the tiny grammar school answers need. Returns the cleaned expression."""
    if not expr or len(expr) > _MAX_LEN or "__" in expr or not _ALLOWED.match(expr):
        raise UnsafeExpression("unsafe or empty expression")
    if re.search(r"[а-яА-ЯёЁ]", expr):
        raise UnsafeExpression("words left after unit stripping")
    cleaned = expr.strip()
    if re.search(r"\d\s+\d", cleaned) or re.search(r"\d\s+[a-z]\b\s+\d", cleaned):
        raise UnsafeExpression("several numbers side by side")
    if re.search(r"(?<!\d)\.|\.(?!\d)", cleaned):
        raise UnsafeExpression("dot outside a decimal number")
    for name in re.findall(r"[a-zA-Z]+", cleaned):
        if name not in _ALLOWED_NAMES:
            raise UnsafeExpression(f"name not allowed: {name}")
    if any(len(run) > _MAX_DIGITS for run in re.findall(r"\d+", cleaned)):
        raise UnsafeExpression("number too long")
    if len(re.findall(r"\*\*", cleaned)) > _MAX_POWERS:
        raise UnsafeExpression("too many powers")
    if re.search(r"\*\*\s*\(?\s*-?\d+\s*\)?\s*\*\*", cleaned):
        raise UnsafeExpression("chained powers")
    for match in re.finditer(r"\*\*\s*(\(?\s*-?\d{1,2}\s*\)?)", cleaned):
        if abs(int(re.sub(r"[^\d-]", "", match.group(1)))) > _MAX_EXPONENT:
            raise UnsafeExpression("exponent too large")
    if re.search(r"\*\*\s*(?!\(?\s*-?\d{1,2}\s*\)?)", cleaned):
        raise UnsafeExpression("exponent must be a small integer")
    return cleaned


def _prepare_part(text: str) -> str:
    """Units, percents and mixed numbers are resolved per part, before the grammar guard."""
    text = _strip_units(text)
    if text.endswith("%"):
        if not re.fullmatch(r"-?[\d.]+%", text):
            raise UnsafeExpression("percent in an expression")
        text = f"({text[:-1]})/100"
    mixed = re.fullmatch(r"(-?\d+) (\d+)/(\d+)", text)
    if mixed:
        whole, num, den = mixed.groups()
        sign = "-" if whole.startswith("-") else ""
        text = f"{sign}({abs(int(whole))}+{num}/{den})"
    return text


def _parse(expr: str):
    cleaned = _guard(_prepare_part(expr))
    return parse_expr(
        cleaned, local_dict=_LOCALS, global_dict=_GLOBALS, transformations=_TRANSFORMATIONS, evaluate=True
    )


def _form(part: str):
    """Classify one answer part: ("value", expr) or ("equation", lhs - rhs, symbol)."""
    if part.count("=") > 1:
        raise UnsafeExpression("too many '='")
    if "=" in part:
        lhs_s, rhs_s = (side.strip() for side in part.split("=", 1))
        lhs, rhs = _parse(lhs_s), _parse(rhs_s)
        if lhs.is_Symbol and not rhs.free_symbols:
            return ("value", rhs)  # x = 4
        if rhs.is_Symbol and not lhs.free_symbols:
            return ("value", lhs)  # 4 = x
        symbols = lhs.free_symbols | rhs.free_symbols
        if len(symbols) != 1:
            raise UnsafeExpression("equation must have exactly one unknown")
        return ("equation", lhs - rhs, next(iter(symbols)))
    return ("value", _parse(part))


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------
def _close(a: float, b: float, tolerance: float) -> bool:
    return abs(a - b) <= max(1e-9, tolerance * max(abs(a), abs(b)))


def _as_real(value) -> float:
    number = complex(value.evalf(15))
    if abs(number.imag) > 1e-9:
        raise UnsafeExpression("complex value")
    return number.real


def _values_equal(expected, given, tolerance: float) -> bool:
    if expected.is_Rational and given.is_Rational:
        return bool(expected == given)  # integers and fractions compare exactly
    return _close(_as_real(expected), _as_real(given), tolerance)


def _expressions_equal(expected, given, tolerance: float) -> tuple[bool, dict]:
    """Numeric equality for constants; sampled equality for expressions with variables."""
    symbols = sorted(expected.free_symbols | given.free_symbols, key=str)
    if not symbols:
        return _values_equal(expected, given, tolerance), {"method": "numeric"}
    rng = random.Random(42)  # noqa: S311 - deterministic sampling, not security
    checked = 0
    for _ in range(8):
        point = {s: sympy.Rational(rng.randint(-70, 70), 10) for s in symbols}
        try:
            e_val = _as_real(expected.subs(point))
            g_val = _as_real(given.subs(point))
        except (TypeError, ValueError, ZeroDivisionError, UnsafeExpression):
            continue
        if not _close(e_val, g_val, 1e-6):
            return False, {"method": "sampled"}
        checked += 1
        if checked >= 4:
            break
    if checked < 2:
        raise UnsafeExpression("could not evaluate enough sample points")
    return True, {"method": "sampled", "points": checked}


def _solutions(expression, symbol) -> list:
    roots = sympy.solve(expression, symbol)
    if not roots:
        raise UnsafeExpression("no solutions")
    return roots


def _sets_equal(expected: list, given: list, tolerance: float) -> bool:
    if len(expected) != len(given):
        return False
    exp_sorted = sorted(_as_real(v) for v in expected)
    giv_sorted = sorted(_as_real(v) for v in given)
    return all(_close(a, b, tolerance) for a, b in zip(exp_sorted, giv_sorted, strict=True))


def _compare_single(expected_form, given_form, tolerance: float) -> tuple[bool, dict]:
    kind_e, kind_g = expected_form[0], given_form[0]
    if kind_e == "value" and kind_g == "value":
        return _expressions_equal(expected_form[1], given_form[1], tolerance)
    if kind_e == "equation" and kind_g == "equation":
        roots_e = _solutions(expected_form[1], expected_form[2])
        roots_g = _solutions(given_form[1], given_form[2])
        return _sets_equal(roots_e, roots_g, tolerance), {"method": "equation"}
    if kind_e == "equation":  # expected "2*x = 8", child answered "4"
        return _sets_equal(_solutions(expected_form[1], expected_form[2]), [given_form[1]], tolerance), {
            "method": "equation"
        }
    return _sets_equal([expected_form[1]], _solutions(given_form[1], given_form[2]), tolerance), {
        "method": "equation"
    }


def _verify(expected: str, given: str, tolerance: float) -> MathVerdict:
    exp_text = _basic_clean(expected)
    giv_text = _basic_clean(given)
    if not giv_text:
        return MathVerdict("uncertain", 0.0, {"reason": "empty"})

    exp_parts = _split_set(exp_text)
    giv_parts = _split_set(giv_text)
    if len(exp_parts) > 1 or len(giv_parts) > 1:
        if len(exp_parts) != len(giv_parts):
            return MathVerdict(
                "incorrect", 0.9, {"reason": "set_size", "expected": len(exp_parts), "given": len(giv_parts)}
            )
        exp_vals = [_form(p) for p in exp_parts]
        giv_vals = [_form(p) for p in giv_parts]
        if any(f[0] != "value" or f[1].free_symbols for f in (*exp_vals, *giv_vals)):
            raise UnsafeExpression("sets must contain plain values")
        ok = _sets_equal([f[1] for f in exp_vals], [f[1] for f in giv_vals], tolerance)
        return MathVerdict("correct" if ok else "incorrect", 0.95, {"method": "set"})

    ok, details = _compare_single(_form(exp_text), _form(giv_text), tolerance)
    confidence = 0.98 if details.get("method") == "numeric" else 0.9
    return MathVerdict("correct" if ok else "incorrect", confidence, details)


def verify_math(expected: str, given: str, *, tolerance: float = 1e-6) -> MathVerdict:
    """Compare a child's answer to the expected one. Never raises, never waits longer than the timeout."""
    result: dict = {}

    def worker() -> None:
        try:
            result["value"] = _verify(expected, given, tolerance)
        except UnsafeExpression as exc:
            result["value"] = MathVerdict("uncertain", 0.0, {"reason": "unsafe", "error": str(exc)[:80]})
        except Exception as exc:  # noqa: BLE001 - any parse failure means "cannot verify formally"
            result["value"] = MathVerdict(
                "uncertain", 0.0, {"reason": "parse_error", "error": type(exc).__name__}
            )

    # A daemon thread cannot block process exit even if SymPy ignores us; the guard above makes
    # that theoretical, the timeout makes it harmless.
    thread = threading.Thread(target=worker, name="math-verify", daemon=True)
    thread.start()
    thread.join(_TIMEOUT_SECONDS)
    if thread.is_alive() or "value" not in result:
        return MathVerdict("uncertain", 0.0, {"reason": "timeout"})
    return result["value"]

"""Rule-based arithmetic quizzes for maths topics.

Used by the Demo provider (no AI key) so the self-check flow works end to end with *real*, verifiable
questions instead of placeholders. Generators are picked by topic keywords, then by grade.
"""

from __future__ import annotations

import random
from fractions import Fraction

from .base import QuizRequest
from .schemas import QuizQuestion, QuizSpec

T = {
    "ru": {
        "calc": "Вычисли: {expr}",
        "compare": "Какая дробь больше?",
        "percent": "Найди {p}% от {n}.",
        "solve": "Реши уравнение: {eq}. Чему равен x?",
        "missing": "Какое число пропущено: {expr}?",
        "title": "Проверь себя: {topic}",
        "because": "{expr} = {ans}.",
        "fraction_rule": "Из дробей с одинаковым знаменателем больше та, у которой больше числитель.",
        "fraction_rule_num": "Из дробей с одинаковым числителем больше та, у которой знаменатель меньше.",
        "percent_rule": "1% от {n} — это {one}; значит {p}% — это {one} × {p} = {ans}.",
        "solve_rule": "Перенесём число в другую часть: x = {rhs} {op} {a} = {ans}.",
        "hint_calc": "Посчитай по действиям, не спеши.",
        "hint_compare": "Сравни числители и знаменатели.",
        "hint_percent": "Сначала найди 1%, потом умножь.",
        "hint_solve": "Что нужно сделать с обеими частями, чтобы x остался один?",
    },
    "ky": {
        "calc": "Эсепте: {expr}",
        "compare": "Кайсы бөлчөк чоң?",
        "percent": "{n} санынын {p}% табыңыз.",
        "solve": "Теңдемени чыгар: {eq}. x эмнеге барабар?",
        "missing": "Кайсы сан калып калган: {expr}?",
        "title": "Өзүңдү текшер: {topic}",
        "because": "{expr} = {ans}.",
        "fraction_rule": "Бөлүмү бирдей бөлчөктөрдүн ичинен алымы чоңу чоң болот.",
        "fraction_rule_num": "Алымы бирдей бөлчөктөрдүн ичинен бөлүмү кичинеси чоң болот.",
        "percent_rule": "{n} санынын 1% — {one}; демек {p}% — {one} × {p} = {ans}.",
        "solve_rule": "Санды башка жакка өткөрөбүз: x = {rhs} {op} {a} = {ans}.",
        "hint_calc": "Аракеттер боюнча шашпай эсепте.",
        "hint_compare": "Алымдарын жана бөлүмдөрүн салыштыр.",
        "hint_percent": "Адегенде 1% тап, анан көбөйт.",
        "hint_solve": "x жалгыз калышы үчүн эки жагына тең эмне кылуу керек?",
    },
}


def _t(lang: str, key: str, **kw: object) -> str:
    table = T.get(lang, T["ru"])
    return table[key].format(**kw)


def _choice_from_number(
    prompt: str, answer: int, explanation: str, hint: str, rng: random.Random
) -> QuizQuestion:
    distractors = {answer + d for d in (-10, -2, -1, 1, 2, 10) if answer + d >= 0 and answer + d != answer}
    options = [answer, *rng.sample(sorted(distractors), k=min(3, len(distractors)))]
    rng.shuffle(options)
    return QuizQuestion(
        kind="choice",
        prompt=prompt,
        options=[str(o) for o in options],
        correct_option=options.index(answer),
        explanation=explanation,
        hint=hint,
    )


def _add_sub(lang: str, rng: random.Random, limit: int) -> QuizQuestion:
    a, b = rng.randint(1, limit), rng.randint(1, limit)
    if rng.random() < 0.5:
        expr, ans = f"{a} + {b}", a + b
    else:
        a, b = max(a, b), min(a, b)
        expr, ans = f"{a} − {b}", a - b
    return QuizQuestion(
        kind="number",
        prompt=_t(lang, "calc", expr=expr),
        answer=str(ans),
        explanation=_t(lang, "because", expr=expr, ans=ans),
        hint=_t(lang, "hint_calc"),
    )


def _mult_div(lang: str, rng: random.Random, *, choice: bool) -> QuizQuestion:
    a, b = rng.randint(2, 9), rng.randint(2, 9)
    if rng.random() < 0.5:
        expr, ans = f"{a} × {b}", a * b
    else:
        expr, ans = f"{a * b} : {a}", b
    explanation = _t(lang, "because", expr=expr, ans=ans)
    if choice:
        return _choice_from_number(_t(lang, "calc", expr=expr), ans, explanation, _t(lang, "hint_calc"), rng)
    return QuizQuestion(
        kind="number",
        prompt=_t(lang, "calc", expr=expr),
        answer=str(ans),
        explanation=explanation,
        hint=_t(lang, "hint_calc"),
    )


def _two_step(lang: str, rng: random.Random) -> QuizQuestion:
    a, b, c = rng.randint(2, 9), rng.randint(2, 9), rng.randint(1, 20)
    expr, ans = f"{a} × {b} + {c}", a * b + c
    return QuizQuestion(
        kind="number",
        prompt=_t(lang, "calc", expr=expr),
        answer=str(ans),
        explanation=_t(lang, "because", expr=f"{a} × {b} + {c} = {a * b} + {c}", ans=ans),
        hint=_t(lang, "hint_calc"),
    )


def _compare_fractions(lang: str, rng: random.Random) -> QuizQuestion:
    """Two fractions shown exactly as generated (no reduction), so the rule in the explanation matches."""
    if rng.random() < 0.5:
        d = rng.randint(3, 12)
        n1, n2 = rng.sample(range(1, d), 2)
        pairs = [(n1, d), (n2, d)]
        rule = _t(lang, "fraction_rule")
    else:
        n = rng.randint(1, 5)
        d1, d2 = rng.sample(range(n + 1, 13), 2)
        pairs = [(n, d1), (n, d2)]
        rule = _t(lang, "fraction_rule_num")
    options = [f"{n}/{d}" for n, d in pairs]
    values = [Fraction(n, d) for n, d in pairs]
    correct = 0 if values[0] > values[1] else 1
    return QuizQuestion(
        kind="choice",
        prompt=_t(lang, "compare"),
        options=options,
        correct_option=correct,
        explanation=f"{options[correct]} > {options[1 - correct]}. {rule}",
        hint=_t(lang, "hint_compare"),
    )


def _percent(lang: str, rng: random.Random) -> QuizQuestion:
    n = rng.choice([50, 80, 100, 120, 200, 250, 300, 400, 500])
    p = rng.choice([5, 10, 20, 25, 50])
    ans = n * p // 100
    one = Fraction(n, 100)
    one_text = str(one.numerator) if one.denominator == 1 else f"{one.numerator}/{one.denominator}"
    return QuizQuestion(
        kind="number",
        prompt=_t(lang, "percent", p=p, n=n),
        answer=str(ans),
        explanation=_t(lang, "percent_rule", n=n, one=one_text, p=p, ans=ans),
        hint=_t(lang, "hint_percent"),
    )


def _equation(lang: str, rng: random.Random) -> QuizQuestion:
    a = rng.randint(1, 20)
    if rng.random() < 0.5:
        x = rng.randint(1, 20)
        eq, rhs, op, ans = f"x + {a} = {x + a}", x + a, "−", x
    else:
        x = rng.randint(a, a + 20)
        eq, rhs, op, ans = f"x − {a} = {x - a}", x - a, "+", x
    return QuizQuestion(
        kind="number",
        prompt=_t(lang, "solve", eq=eq),
        answer=str(ans),
        explanation=_t(lang, "solve_rule", rhs=rhs, op=op, a=a, ans=ans),
        hint=_t(lang, "hint_solve"),
    )


def _negatives(lang: str, rng: random.Random) -> QuizQuestion:
    a, b = rng.randint(-15, 15), rng.randint(1, 15)
    op = rng.choice(["+", "−"])
    ans = a + b if op == "+" else a - b
    expr = f"({a}) {op} {b}" if a < 0 else f"{a} {op} {b}"
    return QuizQuestion(
        kind="number",
        prompt=_t(lang, "calc", expr=expr),
        answer=str(ans),
        explanation=_t(lang, "because", expr=expr, ans=ans),
        hint=_t(lang, "hint_calc"),
    )


def _pick_generators(request: QuizRequest) -> list:
    text = " ".join([request.topic_name, request.topic_description, *request.keywords]).lower()
    if any(k in text for k in ("дроб", "бөлчөк")):
        return [
            _compare_fractions,
            _compare_fractions,
            lambda lang, rng: _mult_div(lang, rng, choice=True),
            _compare_fractions,
        ]
    if any(k in text for k in ("процент", "пайыз")):
        return [_percent, _percent, _percent, lambda lang, rng: _mult_div(lang, rng, choice=True)]
    if any(k in text for k in ("уравнен", "теңдеме")):
        return [_equation, _equation, _equation, _two_step]
    if any(k in text for k in ("отрицат", "терс сан", "целые", "бүтүн сан")):
        return [_negatives, _negatives, _negatives, _two_step]
    if any(k in text for k in ("умнож", "делен", "көбөйт", "бөлүү", "таблиц")):
        return [
            lambda lang, rng: _mult_div(lang, rng, choice=False),
            lambda lang, rng: _mult_div(lang, rng, choice=True),
            _two_step,
            _two_step,
        ]
    g = request.grade_number
    if g <= 1:
        return [lambda lang, rng: _add_sub(lang, rng, 10)] * 4
    if g <= 2:
        return [
            lambda lang, rng: _add_sub(lang, rng, 100),
            lambda lang, rng: _add_sub(lang, rng, 100),
            lambda lang, rng: _mult_div(lang, rng, choice=True),
        ]
    if g <= 4:
        return [
            lambda lang, rng: _mult_div(lang, rng, choice=False),
            lambda lang, rng: _mult_div(lang, rng, choice=True),
            _two_step,
        ]
    if g <= 6:
        return [_two_step, _compare_fractions, _percent, lambda lang, rng: _mult_div(lang, rng, choice=True)]
    return [_equation, _negatives, _percent, _two_step]


def build_math_quiz(request: QuizRequest, *, seed: int | None = None) -> QuizSpec:
    rng = random.Random(seed)  # noqa: S311 - quiz variety, not security
    generators = _pick_generators(request)
    questions: list[QuizQuestion] = []
    prompts: set[str] = set()
    i = 0
    while len(questions) < request.count and i < 40:
        gen = generators[i % len(generators)]
        question = gen(request.language, rng)
        i += 1
        signature = question.prompt + "|" + "|".join(question.options) + "|" + question.answer
        if signature in prompts:
            continue
        prompts.add(signature)
        questions.append(question)
    return QuizSpec(title=_t(request.language, "title", topic=request.topic_name), questions=questions)

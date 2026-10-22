import pytest

from ai.anthropic_provider import parse_turn, split_visible
from ai.verifiers.math import verify_math


@pytest.mark.parametrize(
    ("expected", "given", "verdict"),
    [
        ("4", "4", "correct"),
        ("4", "x = 4", "correct"),
        ("4", "Ответ: 4", "correct"),
        ("4", "4,0", "correct"),
        ("4", "4 см", "correct"),
        ("0.75", "3/4", "correct"),
        ("3/4", "0,75", "correct"),
        ("1.5", "1 1/2", "correct"),
        ("2*x + 3", "3 + 2x", "correct"),
        ("2*x + 3", "2x+4", "incorrect"),
        ("2; 3", "3, 2", "correct"),
        ("2; 3", "2", "incorrect"),
        ("5", "6", "incorrect"),
        ("25", "25%", "incorrect"),
        ("0.25", "25%", "correct"),
        ("4", "не знаю", "uncertain"),
        ("4", "", "uncertain"),
        ("4", "__import__('os').system('x')", "uncertain"),
        ("4", "4" * 300, "uncertain"),
    ],
)
def test_verify_math(expected, given, verdict):
    assert verify_math(expected, given).verdict == verdict


def test_split_visible_holds_back_partial_tag():
    visible, seen = split_visible("Привет <me", False)
    assert visible == "Привет " and seen is False
    visible, seen = split_visible("Привет <meta>{", False)
    assert visible == "Привет " and seen is True


def test_parse_turn_extracts_meta_and_tolerates_garbage():
    raw = 'Шаг один.\n<meta>{"check_question":"Сколько?","expected_answer":"8","answer_kind":"number","steps":[{"title":"A","content":"B"}]}</meta>'
    turn = parse_turn(raw)
    assert turn.message == "Шаг один."
    assert turn.expected_answer == "8" and turn.answer_kind == "number" and turn.steps[0].title == "A"

    broken = parse_turn("Текст <meta>{not json")
    assert broken.message == "Текст"
    assert broken.answer_kind == "none" and broken.uncertainty_note

    plain = parse_turn("Просто текст без меты")
    assert plain.message == "Просто текст без меты" and plain.expected_answer is None

"""Prompt for short self-check quizzes on a curriculum topic (3–5 questions, structured output)."""

from __future__ import annotations

from ai.base import QuizRequest
from ai.prompts.tutor import LANGUAGE_NAMES

QUIZ_SYSTEM = """Ты составляешь короткую проверку по одной теме школьной программы Кыргызстана для конкретного класса.

Правила:
1. Ровно столько вопросов, сколько запрошено. Вопросы только по этой теме, по возрастанию сложности, без повторов.
2. Типы вопросов: "choice" (2–4 варианта, ровно один верный, correct_option — индекс верного), "number" (ответ — число или
   короткое выражение, поле answer), "short" (одно-два слова, поле answer; в accepted — допустимые варианты написания).
   Для математики и точных наук предпочитай "number" и "choice"; для языков и гуманитарных — "choice" и "short".
3. Формулировки — на языке ребёнка, по возрасту, без подсказки ответа в тексте вопроса, без «все ответы верны».
4. explanation — 1–2 предложения: почему верен правильный ответ (его можно назвать), понятно ребёнку этого класса.
5. hint — одна короткая подсказка без ответа.
6. Не придумывай факты. Если тема требует материалов, которых у тебя нет (конкретный текст, картинка), задай вопрос
   на понимание понятия, а не на пересказ.
7. Никаких тем вне школьной программы, никакого насилия, политики, религии и личных данных."""


def build_quiz_prompt(request: QuizRequest) -> str:
    language = LANGUAGE_NAMES.get(request.language, "русском")
    parts = [
        f"Класс: {request.grade_number}. Предмет: {request.subject_name}. Тема: «{request.topic_name}».",
        f"Количество вопросов: {request.count}. Язык вопросов и объяснений: {language}.",
    ]
    if request.topic_description:
        parts.append("Описание темы из программы:\n" + request.topic_description.strip())
    if request.keywords:
        parts.append("Ключевые слова темы: " + ", ".join(request.keywords[:12]))
    if request.subject_notes:
        parts.append("Особенности предмета: " + request.subject_notes.strip())
    parts.append("Составь проверку по правилам из системного сообщения.")
    return "\n\n".join(parts)

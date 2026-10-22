"""Provider-independent handling of a streamed tutor turn.

The model writes the visible markdown first and a ``<meta>{json}</meta>`` tail last. These helpers
hold back a half-typed tag while streaming and split the final text into message + validated meta.
"""

from __future__ import annotations

import json
import logging

from pydantic import ValidationError

from .schemas import MAX_TURN_MESSAGE, TutorMeta, TutorTurn

logger = logging.getLogger("umnydrug.ai")

META_OPEN = "<meta>"
META_CLOSE = "</meta>"
META_INVALID_NOTE = "Структурированные данные ответа не прошли проверку."


def split_visible(buffer: str, meta_seen: bool) -> tuple[str, bool]:
    """Return the part of ``buffer`` that is safe to show (everything before ``<meta>``).

    While the tag has not appeared yet we hold back any suffix that could be the start of it, so a
    half-typed ``<me`` never reaches the screen.
    """
    if meta_seen:
        return buffer.split(META_OPEN, 1)[0], True
    idx = buffer.find(META_OPEN)
    if idx >= 0:
        return buffer[:idx], True
    hold = 0
    for k in range(min(len(META_OPEN) - 1, len(buffer)), 0, -1):
        if META_OPEN.startswith(buffer[-k:]):
            hold = k
            break
    return buffer[: len(buffer) - hold], False


def parse_turn(raw: str) -> TutorTurn:
    """Split the model output into the visible message and the validated meta block."""
    visible = raw
    meta = TutorMeta()
    idx = raw.rfind(META_OPEN)
    if idx >= 0:
        visible = raw[:idx].rstrip()
        tail = raw[idx + len(META_OPEN) :]
        close = tail.rfind(META_CLOSE)
        payload = tail[:close] if close >= 0 else tail
        try:
            meta = TutorMeta.model_validate(json.loads(payload.strip()))
        except (json.JSONDecodeError, ValidationError) as exc:
            detail = exc.error_count() if isinstance(exc, ValidationError) else "json"
            logger.warning("tutor meta rejected: %s", detail, extra={"event": "ai.meta_invalid"})
            meta = TutorMeta(uncertainty_note=META_INVALID_NOTE)
    if not visible.strip():
        visible = "Давай разберёмся вместе. С чего начнём?"
    if len(visible) > MAX_TURN_MESSAGE:
        visible = visible[: MAX_TURN_MESSAGE - 1] + "…"
    return TutorTurn(message=visible, **meta.model_dump())

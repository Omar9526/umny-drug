"""Server-Sent Events helpers for streamed tutor turns."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterable, Iterator

from asgiref.sync import sync_to_async
from django.http import StreamingHttpResponse
from rest_framework.renderers import BaseRenderer

_DONE = object()


def sse_event(data: dict, event: str | None = None) -> bytes:
    head = f"event: {event}\n" if event else ""
    return (head + "data: " + json.dumps(data, ensure_ascii=False) + "\n\n").encode("utf-8")


async def _aiter(events: Iterator[bytes]) -> AsyncIterator[bytes]:
    """Drive a synchronous generator chunk by chunk from the event loop.

    Under ASGI, Django would otherwise consume a sync iterator *completely* before sending anything
    (no streaming). Each ``next()`` runs in the thread-sensitive executor so ORM access stays legal.
    """
    try:
        while True:
            chunk = await sync_to_async(next, thread_sensitive=True)(events, _DONE)
            if chunk is _DONE:
                return
            yield chunk
    finally:
        await sync_to_async(events.close, thread_sensitive=True)()


def sse_response(events: Iterable[bytes], *, asgi: bool = False) -> StreamingHttpResponse:
    content = _aiter(iter(events)) if asgi else events
    response = StreamingHttpResponse(content, content_type="text/event-stream; charset=utf-8")
    response["Cache-Control"] = "no-cache, no-transform"
    response["X-Accel-Buffering"] = "no"
    return response


def is_asgi(request) -> bool:
    """True when served by the ASGI handler (gunicorn+uvicorn in production), False under WSGI/runserver."""
    base = getattr(request, "_request", request)
    return hasattr(base, "scope")


class EventStreamRenderer(BaseRenderer):
    """Lets DRF content negotiation accept ``Accept: text/event-stream``.

    The streamed body is produced by ``sse_response`` directly; this renderer only serialises
    non-stream responses (validation errors) as JSON so the client can still read them.
    """

    media_type = "text/event-stream"
    format = "sse"
    charset = "utf-8"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if data is None:
            return b""
        return json.dumps(data, ensure_ascii=False).encode("utf-8")

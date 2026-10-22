from __future__ import annotations

import io
import json

from PIL import Image


def parse_sse(response) -> list[tuple[str, dict]]:
    """Collect (event, data) pairs from a StreamingHttpResponse."""
    raw = b"".join(response.streaming_content).decode("utf-8")
    events = []
    for block in raw.strip().split("\n\n"):
        event = "message"
        data = None
        for line in block.split("\n"):
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data = json.loads(line[5:].strip())
        if data is not None:
            events.append((event, data))
    return events


def png_bytes(size=(320, 320), color=(255, 255, 255)) -> bytes:
    image = Image.new("RGB", size, color)
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()

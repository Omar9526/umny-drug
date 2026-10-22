"""Validation and normalisation of uploaded homework photos.

Every image is decoded with Pillow, auto-oriented, converted to RGB, downscaled and re-encoded as
JPEG. Re-encoding strips EXIF (GPS, device ids) and neutralises malformed files; the original
bytes are never stored.
"""

from __future__ import annotations

import hashlib
import io
import warnings
from dataclasses import dataclass

from django.conf import settings
from PIL import Image, ImageOps, UnidentifiedImageError

try:  # HEIC/HEIF from iPhones
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:  # pragma: no cover
    pass

ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
ALLOWED_FORMATS = ["JPEG", "PNG", "WEBP", "HEIF"]
MAX_SIDE = 10_000
# Decompression-bomb guard: refuse instead of decoding hundreds of MB.
Image.MAX_IMAGE_PIXELS = getattr(settings, "MAX_IMAGE_PIXELS", 40_000_000)
warnings.simplefilter("error", Image.DecompressionBombWarning)
STORED_MAX_SIDE = 2000
MODEL_MAX_SIDE = 1568  # recommended upper bound for vision input
MIN_SIDE = 200


class ImageValidationError(ValueError):
    def __init__(self, message: str, code: str = "invalid_image"):
        super().__init__(message)
        self.code = code


@dataclass
class ProcessedImage:
    data: bytes
    width: int
    height: int
    sha256: str
    mime_type: str = "image/jpeg"

    @property
    def size_bytes(self) -> int:
        return len(self.data)


def _max_bytes() -> int:
    return settings.MAX_UPLOAD_IMAGE_MB * 1024 * 1024


def process_upload(django_file) -> ProcessedImage:
    size = getattr(django_file, "size", None)
    if size is not None and size > _max_bytes():
        raise ImageValidationError(
            f"Файл больше {settings.MAX_UPLOAD_IMAGE_MB} МБ. Сделай фото поменьше или сожми его.",
            code="too_large",
        )
    content_type = (getattr(django_file, "content_type", "") or "").lower()
    if content_type and content_type not in ALLOWED_MIME:
        raise ImageValidationError(
            "Поддерживаются только фото JPEG, PNG, WebP и HEIC.", code="unsupported_type"
        )

    raw = django_file.read()
    if len(raw) > _max_bytes():
        raise ImageValidationError(f"Файл больше {settings.MAX_UPLOAD_IMAGE_MB} МБ.", code="too_large")
    try:
        probe = Image.open(io.BytesIO(raw), formats=ALLOWED_FORMATS)
        width, height = probe.size
        if max(width, height) > MAX_SIDE or width * height > Image.MAX_IMAGE_PIXELS:
            raise ImageValidationError(
                "Фото слишком большое. Сними его заново или уменьши.", code="too_large"
            )
        probe.verify()
        image = Image.open(io.BytesIO(raw), formats=ALLOWED_FORMATS)
        if image.format == "JPEG":
            image.draft("RGB", (STORED_MAX_SIDE, STORED_MAX_SIDE))
        image.load()
    except ImageValidationError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ImageValidationError(
            "Фото слишком большое. Сними его заново или уменьши.", code="too_large"
        ) from exc
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ImageValidationError(
            "Не удалось прочитать изображение. Попробуй другое фото.", code="corrupt"
        ) from exc

    image = ImageOps.exif_transpose(image) or image
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    elif image.mode == "L":
        image = image.convert("RGB")
    if min(image.size) < MIN_SIDE:
        raise ImageValidationError(
            "Фото слишком маленькое, текст не разобрать. Сними крупнее.", code="too_small"
        )
    image.thumbnail((STORED_MAX_SIDE, STORED_MAX_SIDE), Image.Resampling.LANCZOS)

    out = io.BytesIO()
    image.save(out, format="JPEG", quality=88, optimize=True)
    data = out.getvalue()
    return ProcessedImage(
        data=data, width=image.width, height=image.height, sha256=hashlib.sha256(data).hexdigest()
    )


def for_model(data: bytes) -> bytes:
    """Downscale a stored JPEG for the vision model when it exceeds the recommended size."""
    image = Image.open(io.BytesIO(data))
    if max(image.size) <= MODEL_MAX_SIDE:
        return data
    image.thumbnail((MODEL_MAX_SIDE, MODEL_MAX_SIDE), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=85, optimize=True)
    return out.getvalue()

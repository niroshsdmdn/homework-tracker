"""Shrink phone photos before upload so they load fast and save Drive space."""
from __future__ import annotations

import io

from PIL import Image, ImageOps

try:  # iPhone HEIC photos
    from pillow_heif import register_heif_opener

    register_heif_opener()
except Exception:  # pragma: no cover
    pass

MAX_SIDE = 1800


def prepare_photo(data: bytes) -> bytes:
    """Turn the photo upright, resize to at most MAX_SIDE pixels, save as JPEG."""
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img)
    if img.mode != "RGB":
        img = img.convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85, optimize=True)
    return out.getvalue()

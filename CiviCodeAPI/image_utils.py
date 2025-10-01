import io
import os
from typing import Tuple

from PIL import Image, ImageOps

try:
    import pillow_heif  # type: ignore
    pillow_heif.register_heif_opener()
except Exception:
    # If pillow-heif isn't available, HEIC won't be decoded; we'll best-effort fallback
    pillow_heif = None  # type: ignore


def _to_jpeg_bytes(img: Image.Image, quality: int = 85) -> bytes:
    buf = io.BytesIO()
    # Ensure mode compatible with JPEG
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def normalize_image_for_web(
    content: bytes,
    filename: str,
    reported_content_type: str | None,
) -> Tuple[bytes, str, str]:
    """
    Normalize uploaded images to a browser-friendly format.

    - Convert HEIC/HEIF to JPEG.
    - Pass through JPEG/PNG/WebP/GIF.
    - For unknown-but-image payloads, convert to JPEG.
    - Preserve non-image files as-is.

    Returns: (bytes, filename, content_type)
    """
    ct = (reported_content_type or "").lower()
    ext = os.path.splitext(filename or "")[1].lower()

    def with_jpg_name() -> str:
        base, _ = os.path.splitext(filename or "upload")
        return f"{base}.jpg"

    # Fast-path for known browser-safe types
    if ct in ("image/jpeg", "image/png", "image/webp", "image/gif"):
        return content, filename, ct

    # HEIC/HEIF by content-type or extension
    if ct in ("image/heic", "image/heif") or ext in (".heic", ".heif"):
        try:
            img = Image.open(io.BytesIO(content))
            img = ImageOps.exif_transpose(img)
            jpeg = _to_jpeg_bytes(img)
            return jpeg, with_jpg_name(), "image/jpeg"
        except Exception:
            # Fallthrough to generic attempt below
            pass

    # Attempt to open with PIL: if it's an image of any kind, convert to JPEG
    try:
        img = Image.open(io.BytesIO(content))
        img = ImageOps.exif_transpose(img)
        jpeg = _to_jpeg_bytes(img)
        return jpeg, with_jpg_name(), "image/jpeg"
    except Exception:
        # Not an image or unreadable. Keep original bytes and mark content type if known.
        return content, filename, (ct or "application/octet-stream")

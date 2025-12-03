import io
import os
import json
from datetime import datetime
from typing import Dict, Tuple

from PIL import ExifTags, Image, ImageOps, ImageDraw, ImageFont

try:
    import pillow_heif  # type: ignore
    pillow_heif.register_heif_opener()
except Exception:
    # If pillow-heif isn't available, HEIC won't be decoded; we'll best-effort fallback
    pillow_heif = None  # type: ignore


_EXIF_TAGS = {v: k for k, v in ExifTags.TAGS.items()}
_GPS_TAGS = {v: k for k, v in ExifTags.GPSTAGS.items()}


def _ratio_to_float(value) -> float | None:
    try:
        if hasattr(value, "numerator") and hasattr(value, "denominator"):
            return float(value.numerator) / float(value.denominator)
        num, den = value
        return float(num) / float(den) if den else None
    except Exception:
        return None


def _dms_to_degrees(dms) -> float | None:
    try:
        deg = _ratio_to_float(dms[0])
        minutes = _ratio_to_float(dms[1])
        seconds = _ratio_to_float(dms[2])
        if deg is None or minutes is None or seconds is None:
            return None
        return deg + (minutes / 60.0) + (seconds / 3600.0)
    except Exception:
        return None


def _parse_exif_datetime(raw) -> str | None:
    if raw is None:
        return None
    try:
        if isinstance(raw, bytes):
            raw = raw.decode(errors="ignore")
        text = str(raw).strip()
        for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(text, fmt).isoformat()
            except Exception:
                continue
        return text or None
    except Exception:
        return None


def _extract_exif_payload(img: Image.Image) -> Tuple[bytes | None, Dict]:
    """
    Return (exif_bytes, metadata_summary) for an image.

    metadata_summary includes GPS (lat/lng/alt) and capture timestamps if present.
    """
    metadata: Dict = {}
    exif_bytes = None
    try:
        exif = img.getexif()
    except Exception:
        exif = None

    if exif:
        try:
            exif_bytes = exif.tobytes()
        except Exception:
            exif_bytes = None

        gps_info = None
        gps_key = _EXIF_TAGS.get("GPSInfo")
        if gps_key is not None:
            try:
                gps_info = exif.get_ifd(gps_key)
            except Exception:
                gps_info = exif.get(gps_key)

        if gps_info:
            lat = _dms_to_degrees(gps_info.get(_GPS_TAGS.get("GPSLatitude")))
            lat_ref = gps_info.get(_GPS_TAGS.get("GPSLatitudeRef"))
            lon = _dms_to_degrees(gps_info.get(_GPS_TAGS.get("GPSLongitude")))
            lon_ref = gps_info.get(_GPS_TAGS.get("GPSLongitudeRef"))
            alt = _ratio_to_float(gps_info.get(_GPS_TAGS.get("GPSAltitude")))

            if lat is not None and isinstance(lat_ref, str) and lat_ref.upper() == "S":
                lat = -lat
            if lon is not None and isinstance(lon_ref, str) and lon_ref.upper() == "W":
                lon = -lon

            gps_summary = {
                "latitude": lat,
                "longitude": lon,
                "altitude": alt,
            }
            # Remove empty entries
            gps_summary = {k: v for k, v in gps_summary.items() if v is not None}
            if gps_summary:
                metadata["gps"] = gps_summary

        dt_original = exif.get(_EXIF_TAGS.get("DateTimeOriginal"))
        dt_generic = exif.get(_EXIF_TAGS.get("DateTime"))
        capture_time = _parse_exif_datetime(dt_original or dt_generic)
        if capture_time:
            metadata["captured_at"] = capture_time

        make = exif.get(_EXIF_TAGS.get("Make"))
        model = exif.get(_EXIF_TAGS.get("Model"))
        orientation = exif.get(_EXIF_TAGS.get("Orientation"))
        basic = {
            "make": str(make) if make else None,
            "model": str(model) if model else None,
            "orientation": int(orientation) if orientation else None,
        }
        basic = {k: v for k, v in basic.items() if v is not None}
        if basic:
            metadata["exif"] = basic

    if metadata:
        metadata["source"] = "normalize_image_for_web"
    return exif_bytes, metadata


def _format_stamp_text(metadata: Dict) -> str | None:
    parts = []
    captured = metadata.get("captured_at")
    if captured:
        try:
            ts = datetime.fromisoformat(captured)
            parts.append(ts.strftime("%Y-%m-%d %H:%M:%S"))
        except Exception:
            parts.append(str(captured))
    gps = metadata.get("gps") or {}
    lat = gps.get("latitude")
    lon = gps.get("longitude")
    if lat is not None and lon is not None:
        parts.append(f"{lat:.5f}, {lon:.5f}")
    if not parts:
        return None
    return " | ".join(parts)


def _draw_stamp(img: Image.Image, text: str) -> Image.Image:
    """
    Draw a semi-transparent footer with the provided text on the image.
    """
    if not text:
        return img
    base = img.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = ImageFont.load_default()

    padding = 12
    margin = 12
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_w = text_bbox[2] - text_bbox[0]
    text_h = text_bbox[3] - text_bbox[1]

    x = margin
    y = base.height - text_h - padding - margin
    rect = (x - padding, y - padding, x + text_w + padding, y + text_h + padding)
    draw.rectangle(rect, fill=(0, 0, 0, 160))
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))

    combined = Image.alpha_composite(base, overlay)
    return combined.convert("RGB")


def _to_jpeg_bytes(img: Image.Image, quality: int = 85, exif_bytes: bytes | None = None) -> bytes:
    buf = io.BytesIO()
    # Ensure mode compatible with JPEG
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    save_kwargs = {"format": "JPEG", "quality": quality}
    if exif_bytes:
        save_kwargs["exif"] = exif_bytes
    img.save(buf, **save_kwargs)
    return buf.getvalue()


def normalize_image_for_web(
    content: bytes,
    filename: str,
    reported_content_type: str | None,
) -> Tuple[bytes, str, str, Dict]:
    """
    Normalize uploaded images to a browser-friendly format.

    - Convert HEIC/HEIF to JPEG.
    - Pass through JPEG/PNG/WebP/GIF.
    - For unknown-but-image payloads, convert to JPEG.
    - Preserve non-image files as-is.

    Returns: (bytes, filename, content_type, metadata_dict)
    """
    ct = (reported_content_type or "").lower()
    ext = os.path.splitext(filename or "")[1].lower()
    metadata: Dict = {}
    exif_bytes: bytes | None = None

    def with_jpg_name() -> str:
        base, _ = os.path.splitext(filename or "upload")
        return f"{base}.jpg"

    # Fast-path for known browser-safe types
    if ct in ("image/jpeg", "image/png", "image/webp", "image/gif"):
        try:
            img = Image.open(io.BytesIO(content))
            img = ImageOps.exif_transpose(img)
            exif_bytes, metadata = _extract_exif_payload(img)
            stamp_text = _format_stamp_text(metadata)
            if stamp_text:
                img = _draw_stamp(img, stamp_text)
                jpeg = _to_jpeg_bytes(img, exif_bytes=exif_bytes)
                stamped_name = filename if filename.lower().endswith((".jpg", ".jpeg")) else with_jpg_name()
                return jpeg, stamped_name, "image/jpeg", metadata
        except Exception:
            pass
        return content, filename, ct, metadata

    # HEIC/HEIF by content-type or extension
    if ct in ("image/heic", "image/heif") or ext in (".heic", ".heif"):
        try:
            img = Image.open(io.BytesIO(content))
            img = ImageOps.exif_transpose(img)
            exif_bytes, metadata = _extract_exif_payload(img)
            stamp_text = _format_stamp_text(metadata)
            if stamp_text:
                img = _draw_stamp(img, stamp_text)
            jpeg = _to_jpeg_bytes(img, exif_bytes=exif_bytes)
            return jpeg, with_jpg_name(), "image/jpeg", metadata
        except Exception:
            # Fallthrough to generic attempt below
            pass

    # Attempt to open with PIL: if it's an image of any kind, convert to JPEG
    try:
        img = Image.open(io.BytesIO(content))
        img = ImageOps.exif_transpose(img)
        exif_bytes, metadata = _extract_exif_payload(img)
        stamp_text = _format_stamp_text(metadata)
        if stamp_text:
            img = _draw_stamp(img, stamp_text)
        jpeg = _to_jpeg_bytes(img, exif_bytes=exif_bytes)
        return jpeg, with_jpg_name(), "image/jpeg", metadata
    except Exception:
        # Not an image or unreadable. Keep original bytes and mark content type if known.
        pass

    # Not an image or unreadable. Keep original bytes and mark content type if known.
    return content, filename, (ct or "application/octet-stream"), metadata

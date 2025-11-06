import uuid
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from CiviCodeAPI.storage import blob_service_client, CONTAINER_NAME
from CiviCodeAPI.models import ActiveStorageBlob
from CiviCodeAPI.image_utils import normalize_image_for_web
from CiviCodeAPI.video_utils import transcode_to_mp4_and_poster


def _derive_new_key(old_key: str, new_filename: str) -> str:
    slash = old_key.rfind("/")
    prefix = old_key[:slash] if slash != -1 else ""
    if prefix:
        return f"{prefix}/{uuid.uuid4()}-{new_filename}"
    return f"{uuid.uuid4()}-{new_filename}"


def ensure_blob_browser_safe(db: Session, blob_row: ActiveStorageBlob) -> ActiveStorageBlob:
    """
    If the blob is a non-browser-friendly image (e.g., HEIC/HEIF), convert it to JPEG,
    upload alongside the original, update DB to point to the new blob, and return the updated row.

    Idempotent: if already browser-safe, returns immediately.
    """
    ct = (blob_row.content_type or "").lower()
    filename = blob_row.filename or ""
    # Images
    if ct in ("image/jpeg", "image/png", "image/webp", "image/gif"):
        return blob_row
    if not (ct in ("image/heic", "image/heif") or filename.lower().endswith((".heic", ".heif"))):
        return blob_row

    # Videos: transcode QuickTime/HEVC MOV to MP4 (H.264/AAC)
    if ct in ("video/quicktime", "video/x-quicktime") or filename.lower().endswith(".mov"):
        src_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=blob_row.key)
        data = src_client.download_blob().readall()
        mp4_bytes, poster_bytes = transcode_to_mp4_and_poster(data)

        # Upload mp4
        mp4_filename = (filename.rsplit('.', 1)[0] if '.' in filename else filename) + ".mp4"
        mp4_key = _derive_new_key(blob_row.key, mp4_filename)
        mp4_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=mp4_key)
        mp4_client.upload_blob(mp4_bytes, overwrite=True, content_type="video/mp4")

        # Update blob row to the mp4
        blob_row.key = mp4_key
        blob_row.filename = mp4_filename
        blob_row.content_type = "video/mp4"
        blob_row.byte_size = len(mp4_bytes)
        db.add(blob_row)
        db.commit()
        db.refresh(blob_row)

        # Optional: upload poster alongside (deterministic key from mp4 key)
        if poster_bytes:
            if mp4_key.lower().endswith(".mp4"):
                base = mp4_key[:-4]
            else:
                base = mp4_key
            poster_key = f"{base}-poster.jpg"
            poster_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=poster_key)
            poster_client.upload_blob(poster_bytes, overwrite=True, content_type="image/jpeg")
            # We do not store poster in DB here to avoid schema changes; caller can derive URL from key if needed.

        return blob_row

    # Download original
    src_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=blob_row.key)
    data = src_client.download_blob().readall()

    # Normalize to web-friendly (JPEG)
    new_bytes, new_filename, new_ct = normalize_image_for_web(data, filename, ct)
    new_key = _derive_new_key(blob_row.key, new_filename)

    # Upload converted blob
    dst_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=new_key)
    dst_client.upload_blob(new_bytes, overwrite=True, content_type=new_ct)

    # Update DB row
    blob_row.key = new_key
    blob_row.filename = new_filename
    blob_row.content_type = new_ct
    blob_row.byte_size = len(new_bytes)
    db.add(blob_row)
    db.commit()
    db.refresh(blob_row)
    return blob_row

import argparse
import os
import sys
import uuid
from typing import Iterable

from azure.storage.blob import BlobClient

# Local imports from project
sys.path.append(os.path.dirname(os.path.dirname(__file__)))  # add FastAPI/CiviCodeAPI to path
from storage import blob_service_client, CONTAINER_NAME  # type: ignore
from database import SessionLocal  # type: ignore
from CiviCodeAPI.models import ActiveStorageBlob  # type: ignore
from image_utils import normalize_image_for_web  # type: ignore


def iter_targets(session, include_octet_stream_ext: bool) -> Iterable[ActiveStorageBlob]:
    q = session.query(ActiveStorageBlob)
    # Primary target: explicit HEIC/HEIF content-types
    targets = q.filter(ActiveStorageBlob.content_type.in_(["image/heic", "image/heif"]))
    for row in targets:
        yield row
    if include_octet_stream_ext:
        # Secondary: unknown content-type but filename suggests HEIC/HEIF
        ext_targets = (
            session.query(ActiveStorageBlob)
            .filter(ActiveStorageBlob.content_type.in_([None, "", "application/octet-stream"]))
            .filter(
                (ActiveStorageBlob.filename.ilike("%.heic")) | (ActiveStorageBlob.filename.ilike("%.heif"))
            )
        )
        for row in ext_targets:
            yield row


def new_key_from_old(old_key: str, new_filename: str) -> str:
    # Preserve the folder structure; place converted file alongside original
    # old_key like: address-comments/{id}/{uuid}-orig.ext
    slash = old_key.rfind("/")
    prefix = old_key[:slash] if slash != -1 else ""
    if prefix:
        return f"{prefix}/{uuid.uuid4()}-{new_filename}"
    return f"{uuid.uuid4()}-{new_filename}"


def main(dry_run: bool, limit: int | None, delete_old: bool, include_octet_stream_ext: bool):
    session = SessionLocal()
    processed = 0
    try:
        for row in iter_targets(session, include_octet_stream_ext):
            if limit is not None and processed >= limit:
                break

            key = row.key
            blob: BlobClient = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=key)
            try:
                content = blob.download_blob().readall()
            except Exception as e:
                print(f"[SKIP] Failed to download {key}: {e}")
                continue

            new_bytes, new_filename, new_ct = normalize_image_for_web(content, row.filename, row.content_type or "")

            # If normalization didn't change type (already web-friendly), skip
            if (row.content_type or "").lower() in ("image/jpeg", "image/png", "image/webp", "image/gif"):
                continue

            new_key = new_key_from_old(key, new_filename)
            if dry_run:
                print(f"[DRY-RUN] Would convert {key} ({row.content_type}) -> {new_key} ({new_ct}), size {len(new_bytes)} bytes")
                processed += 1
                continue

            # Upload converted
            try:
                dst = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=new_key)
                dst.upload_blob(new_bytes, overwrite=True, content_type=new_ct)
            except Exception as e:
                print(f"[ERROR] Upload failed for {new_key}: {e}")
                continue

            # Optionally delete original
            if delete_old:
                try:
                    blob.delete_blob()
                except Exception as e:
                    print(f"[WARN] Failed to delete old blob {key}: {e}")

            # Update DB row to point at the new blob
            row.key = new_key
            row.filename = new_filename
            row.content_type = new_ct
            row.byte_size = len(new_bytes)
            session.add(row)
            session.commit()
            processed += 1
            print(f"[OK] Converted {key} -> {new_key}")
    finally:
        session.close()
    print(f"Done. Processed {processed} record(s).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert stored HEIC/HEIF images to JPEG and update DB/Blob.")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default is dry-run)")
    parser.add_argument("--limit", type=int, default=None, help="Max number of records to process")
    parser.add_argument("--delete-old", action="store_true", help="Delete original blob after successful conversion")
    parser.add_argument(
        "--include-octet-stream-ext",
        action="store_true",
        help="Include blobs with unknown content_type but .heic/.heif filename",
    )
    args = parser.parse_args()

    main(
        dry_run=not args.apply,
        limit=args.limit,
        delete_old=args.delete_old,
        include_octet_stream_ext=args.include_octet_stream_ext,
    )

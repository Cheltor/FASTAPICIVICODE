import os
import subprocess
import tempfile
from typing import Tuple, Optional


def _run_ffmpeg(args: list[str]) -> None:
    proc = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", *args], capture_output=True)
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="ignore")
        raise RuntimeError(f"ffmpeg failed: {stderr}")


def transcode_to_mp4_and_poster(data: bytes) -> Tuple[bytes, Optional[bytes]]:
    """
    Transcode source video bytes (e.g., MOV/HEVC) to H.264/AAC MP4 and extract a poster JPEG.

    Requires ffmpeg available on PATH.

    Args:
        data (bytes): The source video bytes.

    Returns:
        tuple[bytes, bytes | None]: A tuple containing the MP4 bytes and optional poster bytes.

    Raises:
        RuntimeError: If ffmpeg fails.
    """
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "in.mov")
        dst = os.path.join(td, "out.mp4")
        poster = os.path.join(td, "poster.jpg")
        with open(src, "wb") as f:
            f.write(data)

        # Transcode to broadly compatible H.264 in MP4
        _run_ffmpeg([
            "-y",
            "-i", src,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-profile:v", "high",
            "-level", "4.1",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-c:a", "aac",
            "-b:a", "128k",
            dst,
        ])

        mp4_bytes: bytes
        with open(dst, "rb") as f:
            mp4_bytes = f.read()

        # Best-effort poster from 1s mark
        poster_bytes: Optional[bytes] = None
        try:
            _run_ffmpeg([
                "-y",
                "-ss", "00:00:01.000",
                "-i", src,
                "-vframes", "1",
                poster,
            ])
            with open(poster, "rb") as f:
                poster_bytes = f.read()
        except Exception:
            poster_bytes = None

        return mp4_bytes, poster_bytes

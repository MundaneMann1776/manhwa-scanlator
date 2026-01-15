"""Storage utilities for deterministic file organization and verification."""

import hashlib
from pathlib import Path
from typing import Optional


def get_series_path(root: Path, source_id: str, series_id: str) -> Path:
    """Return deterministic path for a series."""
    return root / "sources" / source_id / series_id


def get_chapter_path(root: Path, source_id: str, series_id: str, chapter_id: str) -> Path:
    """Return deterministic path for a chapter."""
    return get_series_path(root, source_id, series_id) / chapter_id


def get_pages_path(root: Path, source_id: str, series_id: str, chapter_id: str) -> Path:
    """Return deterministic path for chapter pages directory."""
    return get_chapter_path(root, source_id, series_id, chapter_id) / "pages"


def get_page_filename(page_index: int, extension: str = "webp") -> str:
    """Return deterministic filename for a page."""
    return f"{page_index:03d}.{extension}"


def get_page_path(
    root: Path, source_id: str, series_id: str, chapter_id: str, page_index: int, extension: str = "webp"
) -> Path:
    """Return deterministic path for a single page."""
    pages_dir = get_pages_path(root, source_id, series_id, chapter_id)
    return pages_dir / get_page_filename(page_index, extension)


def get_metadata_path(root: Path, source_id: str, series_id: str, chapter_id: str) -> Path:
    """Return path for chapter metadata.json."""
    return get_chapter_path(root, source_id, series_id, chapter_id) / "metadata.json"


def verify_sha256(file_path: Path, expected_sha256: str) -> bool:
    """Verify file SHA256 checksum matches expected value."""
    if not file_path.exists():
        return False

    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)

    return sha256_hash.hexdigest() == expected_sha256


def compute_sha256(file_path: Path) -> Optional[str]:
    """Compute SHA256 checksum of a file."""
    if not file_path.exists():
        return None

    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)

    return sha256_hash.hexdigest()

"""Concurrent chapter downloader with resume support and exponential backoff."""

import json
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from .adapter import ChapterInfo, PageMetadata, SourceAdapter
from .db import AcquisitionDB
from .storage import (
    compute_sha256,
    get_chapter_path,
    get_metadata_path,
    get_page_path,
    get_pages_path,
)


class DownloadResult:
    """Result of downloading a chapter."""

    def __init__(self, success: bool, pages_downloaded: int, pages_failed: int, errors: list[str]):
        """Initialize download result."""
        self.success = success
        self.pages_downloaded = pages_downloaded
        self.pages_failed = pages_failed
        self.errors = errors


def _download_page_with_retry(
    adapter: SourceAdapter,
    chapter_info: ChapterInfo,
    page_index: int,
    output_path: Path,
    max_retries: int = 5,
) -> tuple[int, bool, Optional[PageMetadata], Optional[str]]:
    """Download a single page with exponential backoff retry."""
    part_file = output_path.with_suffix(output_path.suffix + ".part")

    for attempt in range(max_retries):
        try:
            # Download to .part file first
            result = adapter.download_page(chapter_info, page_index, part_file)

            if result.success and result.metadata:
                # Rename .part to final name on success
                part_file.rename(output_path)
                return (page_index, True, result.metadata, None)
            else:
                error = result.error or "Unknown error"
                if attempt < max_retries - 1:
                    # Exponential backoff with jitter
                    backoff = (2**attempt) + random.uniform(0, 1)
                    time.sleep(backoff)
                else:
                    return (page_index, False, None, error)

        except Exception as e:
            error = str(e)
            if attempt < max_retries - 1:
                backoff = (2**attempt) + random.uniform(0, 1)
                time.sleep(backoff)
            else:
                return (page_index, False, None, error)

    return (page_index, False, None, "Max retries exceeded")


def _write_page_manifest(
    output_dir: Path, page_index: int, metadata: PageMetadata, success: bool, error: Optional[str] = None
) -> None:
    """Write per-page manifest JSON."""
    manifest = {
        "page_index": page_index,
        "success": success,
        "error": error,
        "metadata": asdict(metadata) if metadata else None,
        "timestamp": datetime.utcnow().isoformat(),
    }

    manifest_path = output_dir / f"page_{page_index:03d}.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)


def download_chapter(
    adapter: SourceAdapter,
    chapter_info: ChapterInfo,
    root_path: Path,
    db: AcquisitionDB,
    max_workers: int = 4,
    resume: bool = True,
) -> DownloadResult:
    """Download all pages of a chapter with concurrency and resume support."""
    # Register chapter in database
    db.register_chapter(
        chapter_info.source_id, chapter_info.series_id, chapter_info.chapter_id, chapter_info.chapter_title,
        chapter_info.page_count
    )

    # Prepare output directory
    pages_dir = get_pages_path(root_path, chapter_info.source_id, chapter_info.series_id, chapter_info.chapter_id)
    pages_dir.mkdir(parents=True, exist_ok=True)

    # Determine pages to download
    total_pages = chapter_info.page_count or 100  # Default to 100 if unknown
    pages_to_download = []

    for page_idx in range(total_pages):
        output_path = get_page_path(
            root_path, chapter_info.source_id, chapter_info.series_id, chapter_info.chapter_id, page_idx, "png"
        )

        # Check if page already exists and is valid (resume support)
        if resume and output_path.exists():
            manifest_path = pages_dir / f"page_{page_idx:03d}.json"
            if manifest_path.exists():
                try:
                    with open(manifest_path) as f:
                        manifest = json.load(f)
                        if manifest.get("success"):
                            continue  # Skip already downloaded page
                except Exception:
                    pass  # Re-download if manifest is corrupt

        pages_to_download.append((page_idx, output_path))

    if not pages_to_download:
        return DownloadResult(success=True, pages_downloaded=0, pages_failed=0, errors=[])

    # Download pages concurrently
    pages_downloaded = 0
    pages_failed = 0
    errors = []
    page_metadata_list = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_download_page_with_retry, adapter, chapter_info, page_idx, output_path): page_idx
            for page_idx, output_path in pages_to_download
        }

        for future in as_completed(futures):
            page_idx, success, metadata, error = future.result()

            if success and metadata:
                pages_downloaded += 1
                page_metadata_list.append(metadata)
                _write_page_manifest(pages_dir, page_idx, metadata, True)
                db.mark_page_downloaded(
                    chapter_info.source_id,
                    chapter_info.series_id,
                    chapter_info.chapter_id,
                    page_idx,
                    metadata.filename,
                )
            else:
                pages_failed += 1
                if error:
                    errors.append(f"Page {page_idx}: {error}")
                _write_page_manifest(pages_dir, page_idx, None, False, error)
                db.mark_page_failed(chapter_info.source_id, chapter_info.series_id, chapter_info.chapter_id, page_idx, error or "Unknown error")

    # Write chapter metadata
    chapter_metadata = {
        "source_id": chapter_info.source_id,
        "series_id": chapter_info.series_id,
        "chapter_id": chapter_info.chapter_id,
        "chapter_title": chapter_info.chapter_title,
        "page_count": total_pages,
        "acquired_at": datetime.utcnow().isoformat(),
        "source_url": chapter_info.chapter_url,
        "status": "complete" if pages_failed == 0 else "partial" if pages_downloaded > 0 else "failed",
        "pages": [asdict(m) for m in sorted(page_metadata_list, key=lambda x: x.index)],
    }

    metadata_path = get_metadata_path(
        root_path, chapter_info.source_id, chapter_info.series_id, chapter_info.chapter_id
    )
    with open(metadata_path, "w") as f:
        json.dump(chapter_metadata, f, indent=2)

    return DownloadResult(
        success=(pages_failed == 0), pages_downloaded=pages_downloaded, pages_failed=pages_failed, errors=errors
    )

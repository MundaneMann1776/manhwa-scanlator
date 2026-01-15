"""Filesystem-based source adapter for testing and local chapter libraries."""

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional
from PIL import Image

from .adapter import (
    ChapterInfo,
    ChapterMetadata,
    PageDownloadResult,
    PageMetadata,
    SeriesInfo,
)


class FilesystemAdapter:
    """Adapter that reads manhwa chapters from local filesystem."""

    def __init__(self, source_id: str, root_path: Path):
        """Initialize filesystem adapter with source ID and root directory."""
        self.source_id = source_id
        self.root_path = Path(root_path)

    def discover_series(self, query: str) -> list[SeriesInfo]:
        """Search for series by matching directory names."""
        results = []
        if not self.root_path.exists():
            return results

        for series_dir in self.root_path.iterdir():
            if series_dir.is_dir() and query.lower() in series_dir.name.lower():
                results.append(
                    SeriesInfo(
                        source_id=self.source_id,
                        series_id=series_dir.name,
                        title=series_dir.name,
                        description=None,
                        author=None,
                        cover_url=None,
                    )
                )
        return results

    def list_chapters(self, series_id: str) -> list[ChapterInfo]:
        """List all chapters in a series directory."""
        series_path = self.root_path / series_id
        chapters = []

        if not series_path.exists():
            return chapters

        for chapter_dir in sorted(series_path.iterdir()):
            if chapter_dir.is_dir():
                page_count = len(list(chapter_dir.glob("*.png")))
                chapters.append(
                    ChapterInfo(
                        source_id=self.source_id,
                        series_id=series_id,
                        chapter_id=chapter_dir.name,
                        chapter_title=chapter_dir.name,
                        chapter_url=str(chapter_dir),
                        page_count=page_count,
                    )
                )
        return chapters

    def download_page(
        self, chapter_info: ChapterInfo, page_index: int, output_path: Path
    ) -> PageDownloadResult:
        """Copy a page from filesystem to output path."""
        try:
            chapter_path = Path(chapter_info.chapter_url)
            page_files = sorted(chapter_path.glob("*.png"))

            if page_index >= len(page_files):
                return PageDownloadResult(
                    index=page_index,
                    success=False,
                    local_path=None,
                    error=f"Page index {page_index} out of range",
                    metadata=None,
                )

            source_file = page_files[page_index]
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Copy file
            import shutil

            shutil.copy2(source_file, output_path)

            # Generate metadata
            with Image.open(output_path) as img:
                width, height = img.size

            file_size = output_path.stat().st_size

            with open(output_path, "rb") as f:
                sha256 = hashlib.sha256(f.read()).hexdigest()

            metadata = PageMetadata(
                index=page_index,
                filename=output_path.name,
                width=width,
                height=height,
                size_bytes=file_size,
                sha256=sha256,
            )

            return PageDownloadResult(
                index=page_index,
                success=True,
                local_path=output_path,
                error=None,
                metadata=metadata,
            )

        except Exception as e:
            return PageDownloadResult(
                index=page_index,
                success=False,
                local_path=None,
                error=str(e),
                metadata=None,
            )

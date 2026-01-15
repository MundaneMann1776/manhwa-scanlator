"""Source adapter protocol and data structures for manhwa acquisition."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol, Optional


@dataclass
class PageMetadata:
    """Metadata for a single page in a chapter."""
    index: int
    filename: str
    width: int
    height: int
    size_bytes: int
    sha256: str


@dataclass
class ChapterMetadata:
    """Metadata for a complete chapter."""
    source_id: str
    series_id: str
    chapter_id: str
    chapter_title: str
    page_count: int
    acquired_at: datetime
    source_url: str
    status: str  # "complete" | "partial" | "failed"
    pages: list[PageMetadata]


@dataclass
class SeriesInfo:
    """Information about a series from a source."""
    source_id: str
    series_id: str
    title: str
    description: Optional[str]
    author: Optional[str]
    cover_url: Optional[str]


@dataclass
class ChapterInfo:
    """Basic information about a chapter before acquisition."""
    source_id: str
    series_id: str
    chapter_id: str
    chapter_title: str
    chapter_url: str
    page_count: Optional[int]


@dataclass
class PageDownloadResult:
    """Result of downloading a single page."""
    index: int
    success: bool
    local_path: Optional[Path]
    error: Optional[str]
    metadata: Optional[PageMetadata]


class SourceAdapter(Protocol):
    """Protocol for implementing manhwa source adapters."""

    @property
    def source_id(self) -> str:
        """Return unique identifier for this source."""
        ...

    def discover_series(self, query: str) -> list[SeriesInfo]:
        """Search for series by query string."""
        ...

    def list_chapters(self, series_id: str) -> list[ChapterInfo]:
        """List all available chapters for a series."""
        ...

    def download_page(self, chapter_info: ChapterInfo, page_index: int, output_path: Path) -> PageDownloadResult:
        """Download a single page to the specified path."""
        ...

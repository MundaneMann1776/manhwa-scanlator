"""Processing job datastructures."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


JobStatus = Literal["PENDING", "DONE", "FAILED"]


@dataclass
class PageJob:
    """Job for processing a single page."""

    # Identifiers
    source_id: str
    series_id: str
    chapter_id: str
    page_index: int

    # Input paths
    input_image_path: Path
    input_manifest_path: Path

    # Output paths
    output_image_path: Path
    output_manifest_path: Path

    # Status
    status: JobStatus
    error: str | None = None

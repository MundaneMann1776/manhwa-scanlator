"""Tests for filesystem adapter."""

import tempfile
from pathlib import Path
import pytest
from PIL import Image

from src.acquisition.filesystem_adapter import FilesystemAdapter
from src.acquisition.adapter import ChapterInfo


@pytest.fixture
def temp_source_dir():
    """Create temporary source directory with test data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create test series
        series_path = tmpdir_path / "test-series"
        series_path.mkdir()

        # Create test chapter
        chapter_path = series_path / "ch001"
        chapter_path.mkdir()

        # Create test pages
        for i in range(3):
            img = Image.new("RGB", (100, 200), color=(255, 0, 0))
            img.save(chapter_path / f"page_{i:03d}.png")

        yield tmpdir_path


def test_discover_series(temp_source_dir):
    """Test discovering series from filesystem."""
    adapter = FilesystemAdapter("filesystem", temp_source_dir)
    series_list = adapter.discover_series("test")

    assert len(series_list) == 1
    assert series_list[0].series_id == "test-series"
    assert series_list[0].title == "test-series"


def test_discover_series_no_match(temp_source_dir):
    """Test discovering series with no matches."""
    adapter = FilesystemAdapter("filesystem", temp_source_dir)
    series_list = adapter.discover_series("nonexistent")

    assert len(series_list) == 0


def test_list_chapters(temp_source_dir):
    """Test listing chapters for a series."""
    adapter = FilesystemAdapter("filesystem", temp_source_dir)
    chapters = adapter.list_chapters("test-series")

    assert len(chapters) == 1
    assert chapters[0].chapter_id == "ch001"
    assert chapters[0].page_count == 3


def test_list_chapters_nonexistent_series(temp_source_dir):
    """Test listing chapters for nonexistent series."""
    adapter = FilesystemAdapter("filesystem", temp_source_dir)
    chapters = adapter.list_chapters("nonexistent")

    assert len(chapters) == 0


def test_download_page(temp_source_dir):
    """Test downloading a page."""
    adapter = FilesystemAdapter("filesystem", temp_source_dir)
    chapters = adapter.list_chapters("test-series")

    with tempfile.TemporaryDirectory() as output_dir:
        output_path = Path(output_dir) / "output.png"
        result = adapter.download_page(chapters[0], 0, output_path)

        assert result.success is True
        assert result.local_path == output_path
        assert output_path.exists()
        assert result.metadata is not None
        assert result.metadata.index == 0
        assert result.metadata.width == 100
        assert result.metadata.height == 200


def test_download_page_out_of_range(temp_source_dir):
    """Test downloading page with invalid index."""
    adapter = FilesystemAdapter("filesystem", temp_source_dir)
    chapters = adapter.list_chapters("test-series")

    with tempfile.TemporaryDirectory() as output_dir:
        output_path = Path(output_dir) / "output.png"
        result = adapter.download_page(chapters[0], 999, output_path)

        assert result.success is False
        assert result.error is not None
        assert "out of range" in result.error

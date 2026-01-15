"""Tests for downloader resume functionality."""

import json
import tempfile
from pathlib import Path

import pytest
from PIL import Image

from src.acquisition.adapter import ChapterInfo
from src.acquisition.db import AcquisitionDB
from src.acquisition.downloader import download_chapter
from src.acquisition.filesystem_adapter import FilesystemAdapter
from src.acquisition.storage import get_pages_path


@pytest.fixture
def test_chapter_source():
    """Create temporary source with test chapter."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create test series and chapter
        series_path = tmpdir_path / "test-series"
        chapter_path = series_path / "ch001"
        chapter_path.mkdir(parents=True)

        # Create 5 test pages
        for i in range(5):
            img = Image.new("RGB", (100, 200), color=(i * 50, 0, 0))
            img.save(chapter_path / f"page_{i:03d}.png")

        yield tmpdir_path


@pytest.fixture
def output_dir():
    """Create temporary output directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_download_chapter_fresh(test_chapter_source, output_dir):
    """Test downloading a chapter from scratch."""
    adapter = FilesystemAdapter("filesystem", test_chapter_source)
    chapters = adapter.list_chapters("test-series")
    assert len(chapters) == 1

    db_path = output_dir / "test.db"
    db = AcquisitionDB(db_path)

    result = download_chapter(adapter, chapters[0], output_dir, db, max_workers=2)

    assert result.success is True
    assert result.pages_downloaded == 5
    assert result.pages_failed == 0

    # Verify files exist
    pages_dir = get_pages_path(output_dir, "filesystem", "test-series", "ch001")
    assert (pages_dir / "000.png").exists()
    assert (pages_dir / "004.png").exists()

    # Verify manifests exist
    assert (pages_dir / "page_000.json").exists()
    with open(pages_dir / "page_000.json") as f:
        manifest = json.load(f)
        assert manifest["success"] is True
        assert manifest["metadata"] is not None

    db.close()


def test_download_chapter_resume_partial(test_chapter_source, output_dir):
    """Test resuming a partially downloaded chapter."""
    adapter = FilesystemAdapter("filesystem", test_chapter_source)
    chapters = adapter.list_chapters("test-series")

    db_path = output_dir / "test.db"
    db = AcquisitionDB(db_path)

    # Pre-create first 2 pages as "already downloaded"
    pages_dir = get_pages_path(output_dir, "filesystem", "test-series", "ch001")
    pages_dir.mkdir(parents=True, exist_ok=True)

    for i in range(2):
        img = Image.new("RGB", (100, 200), color=(0, 255, 0))
        page_path = pages_dir / f"{i:03d}.png"
        img.save(page_path)

        # Create manifest
        manifest = {
            "page_index": i,
            "success": True,
            "error": None,
            "metadata": {"index": i, "filename": page_path.name},
        }
        with open(pages_dir / f"page_{i:03d}.json", "w") as f:
            json.dump(manifest, f)

    # Download with resume enabled (default)
    result = download_chapter(adapter, chapters[0], output_dir, db, max_workers=2, resume=True)

    # Should only download remaining 3 pages (indexes 2, 3, 4)
    assert result.success is True
    # Note: pages_downloaded counts only NEW downloads, not resumed ones
    assert result.pages_downloaded == 3
    assert result.pages_failed == 0

    # Verify all 5 pages exist
    assert (pages_dir / "000.png").exists()
    assert (pages_dir / "001.png").exists()
    assert (pages_dir / "002.png").exists()
    assert (pages_dir / "003.png").exists()
    assert (pages_dir / "004.png").exists()

    db.close()


def test_download_chapter_no_resume(test_chapter_source, output_dir):
    """Test downloading without resume re-downloads all pages."""
    adapter = FilesystemAdapter("filesystem", test_chapter_source)
    chapters = adapter.list_chapters("test-series")

    db_path = output_dir / "test.db"
    db = AcquisitionDB(db_path)

    # Pre-create a page
    pages_dir = get_pages_path(output_dir, "filesystem", "test-series", "ch001")
    pages_dir.mkdir(parents=True, exist_ok=True)

    img = Image.new("RGB", (100, 200), color=(0, 255, 0))
    img.save(pages_dir / "000.png")

    # Download with resume disabled
    result = download_chapter(adapter, chapters[0], output_dir, db, max_workers=2, resume=False)

    # Should download all 5 pages including page 0 again
    assert result.success is True
    assert result.pages_downloaded == 5

    db.close()


def test_download_chapter_corrupted_manifest_redownloads(test_chapter_source, output_dir):
    """Test that corrupted manifest causes re-download."""
    adapter = FilesystemAdapter("filesystem", test_chapter_source)
    chapters = adapter.list_chapters("test-series")

    db_path = output_dir / "test.db"
    db = AcquisitionDB(db_path)

    # Pre-create page with corrupted manifest
    pages_dir = get_pages_path(output_dir, "filesystem", "test-series", "ch001")
    pages_dir.mkdir(parents=True, exist_ok=True)

    img = Image.new("RGB", (100, 200), color=(0, 255, 0))
    page_path = pages_dir / "000.png"
    img.save(page_path)

    # Write corrupted manifest
    with open(pages_dir / "page_000.json", "w") as f:
        f.write("{invalid json")

    # Download with resume enabled
    result = download_chapter(adapter, chapters[0], output_dir, db, max_workers=2, resume=True)

    # Should re-download page 0 due to corrupt manifest
    assert result.success is True
    assert result.pages_downloaded == 5

    # Verify manifest is now valid
    with open(pages_dir / "page_000.json") as f:
        manifest = json.load(f)
        assert manifest["success"] is True

    db.close()

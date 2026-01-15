"""Tests for processing runner."""

import json
import tempfile
from pathlib import Path

import pytest
from PIL import Image

from src.processing.job import PageJob
from src.processing.runner import run_page


@pytest.fixture
def temp_dirs():
    """Create temporary input and output directories."""
    with tempfile.TemporaryDirectory() as input_dir, tempfile.TemporaryDirectory() as output_dir:
        input_path = Path(input_dir)
        output_path = Path(output_dir)

        # Create input structure: data/sources/{source}/{series}/{chapter}/pages/
        pages_dir = input_path / "data" / "sources" / "test-source" / "test-series" / "ch001" / "pages"
        pages_dir.mkdir(parents=True)

        # Create test image
        img = Image.new("RGB", (100, 200), color=(255, 0, 0))
        input_image = pages_dir / "000.png"
        img.save(input_image)

        # Create test manifest
        manifest = {
            "page_index": 0,
            "success": True,
            "metadata": {
                "index": 0,
                "filename": "000.png",
                "width": 100,
                "height": 200,
            },
        }
        input_manifest = pages_dir / "page_000.json"
        with open(input_manifest, "w") as f:
            json.dump(manifest, f)

        yield {
            "input_dir": input_path,
            "output_dir": output_path,
            "input_image": input_image,
            "input_manifest": input_manifest,
        }


def test_run_page_success(temp_dirs):
    """Test successful page processing."""
    output_dir = temp_dirs["output_dir"] / "output" / "test-source" / "test-series" / "ch001" / "pages"
    output_image = output_dir / "000_processed.png"
    output_manifest = output_dir / "page_000.out.json"

    job = PageJob(
        source_id="test-source",
        series_id="test-series",
        chapter_id="ch001",
        page_index=0,
        input_image_path=temp_dirs["input_image"],
        input_manifest_path=temp_dirs["input_manifest"],
        output_image_path=output_image,
        output_manifest_path=output_manifest,
        status="PENDING",
    )

    result = run_page(job)

    # Check job status
    assert result.status == "DONE"
    assert result.error is None

    # Check output files exist
    assert output_image.exists()
    assert output_manifest.exists()

    # Verify output image is a valid image
    with Image.open(output_image) as img:
        assert img.size == (100, 200)

    # Verify output manifest
    with open(output_manifest) as f:
        manifest = json.load(f)
        assert manifest["status"] == "DONE"
        assert manifest["source_id"] == "test-source"
        assert manifest["series_id"] == "test-series"
        assert manifest["chapter_id"] == "ch001"
        assert manifest["page_index"] == 0
        assert "processed_at" in manifest


def test_run_page_missing_input_image(temp_dirs):
    """Test handling of missing input image."""
    output_dir = temp_dirs["output_dir"] / "output" / "test-source" / "test-series" / "ch001" / "pages"
    nonexistent_image = temp_dirs["input_dir"] / "nonexistent.png"

    job = PageJob(
        source_id="test-source",
        series_id="test-series",
        chapter_id="ch001",
        page_index=0,
        input_image_path=nonexistent_image,
        input_manifest_path=temp_dirs["input_manifest"],
        output_image_path=output_dir / "000_processed.png",
        output_manifest_path=output_dir / "page_000.out.json",
        status="PENDING",
    )

    result = run_page(job)

    # Check job failed
    assert result.status == "FAILED"
    assert result.error is not None
    assert "not found" in result.error


def test_run_page_missing_input_manifest(temp_dirs):
    """Test handling of missing input manifest."""
    output_dir = temp_dirs["output_dir"] / "output" / "test-source" / "test-series" / "ch001" / "pages"
    nonexistent_manifest = temp_dirs["input_dir"] / "nonexistent.json"

    job = PageJob(
        source_id="test-source",
        series_id="test-series",
        chapter_id="ch001",
        page_index=0,
        input_image_path=temp_dirs["input_image"],
        input_manifest_path=nonexistent_manifest,
        output_image_path=output_dir / "000_processed.png",
        output_manifest_path=output_dir / "page_000.out.json",
        status="PENDING",
    )

    result = run_page(job)

    # Check job failed
    assert result.status == "FAILED"
    assert result.error is not None
    assert "not found" in result.error

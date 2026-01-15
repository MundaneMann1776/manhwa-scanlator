"""Tests for OCR functionality."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from src.processing.job import PageJob
from src.processing.runner import run_page


@pytest.fixture
def temp_dirs_with_image():
    """Create temporary directories with test image and manifest."""
    with tempfile.TemporaryDirectory() as input_dir, tempfile.TemporaryDirectory() as output_dir:
        input_path = Path(input_dir)
        output_path = Path(output_dir)

        # Create input structure
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
            "metadata": {"index": 0, "filename": "000.png"},
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


def test_run_page_without_ocr(temp_dirs_with_image):
    """Test that OCR file is not created when with_ocr=False."""
    output_dir = (
        temp_dirs_with_image["output_dir"] / "output" / "test-source" / "test-series" / "ch001" / "pages"
    )
    output_image = output_dir / "000_processed.png"
    output_manifest = output_dir / "page_000.out.json"
    ocr_output = output_dir / "page_000.ocr.json"

    job = PageJob(
        source_id="test-source",
        series_id="test-series",
        chapter_id="ch001",
        page_index=0,
        input_image_path=temp_dirs_with_image["input_image"],
        input_manifest_path=temp_dirs_with_image["input_manifest"],
        output_image_path=output_image,
        output_manifest_path=output_manifest,
        status="PENDING",
    )

    result = run_page(job, with_ocr=False)

    # Check success
    assert result.status == "DONE"
    assert output_image.exists()
    assert output_manifest.exists()

    # Check OCR file does NOT exist
    assert not ocr_output.exists()


def test_run_page_with_ocr_mocked(temp_dirs_with_image):
    """Test that OCR file is created when with_ocr=True (with mocked PaddleOCR)."""
    # Mock PaddleOCR result
    mock_ocr_instance = MagicMock()
    mock_ocr_instance.ocr.return_value = [
        [
            # Detection 1: bbox and (text, confidence)
            [[[10, 10], [90, 10], [90, 30], [10, 30]], ("안녕하세요", 0.98)],
            # Detection 2
            [[[10, 40], [90, 40], [90, 60], [10, 60]], ("테스트", 0.95)],
        ]
    ]

    mock_paddle_class = MagicMock(return_value=mock_ocr_instance)

    output_dir = (
        temp_dirs_with_image["output_dir"] / "output" / "test-source" / "test-series" / "ch001" / "pages"
    )
    output_image = output_dir / "000_processed.png"
    output_manifest = output_dir / "page_000.out.json"
    ocr_output = output_dir / "page_000.ocr.json"

    job = PageJob(
        source_id="test-source",
        series_id="test-series",
        chapter_id="ch001",
        page_index=0,
        input_image_path=temp_dirs_with_image["input_image"],
        input_manifest_path=temp_dirs_with_image["input_manifest"],
        output_image_path=output_image,
        output_manifest_path=output_manifest,
        status="PENDING",
    )

    # Patch the PaddleOCR import inside run_ocr
    with patch.dict("sys.modules", {"paddleocr": MagicMock(PaddleOCR=mock_paddle_class)}):
        result = run_page(job, with_ocr=True)

    # Check success
    assert result.status == "DONE"
    assert output_image.exists()
    assert output_manifest.exists()

    # Check OCR file exists
    assert ocr_output.exists()

    # Verify OCR file content
    with open(ocr_output, encoding="utf-8") as f:
        ocr_data = json.load(f)

    assert ocr_data["engine"] == "paddleocr"
    assert ocr_data["language"] == "ko"
    assert len(ocr_data["lines"]) == 2

    # Check first line
    assert ocr_data["lines"][0]["text"] == "안녕하세요"
    assert ocr_data["lines"][0]["confidence"] == 0.98
    assert ocr_data["lines"][0]["bbox"] == [[10, 10], [90, 10], [90, 30], [10, 30]]

    # Check second line
    assert ocr_data["lines"][1]["text"] == "테스트"
    assert ocr_data["lines"][1]["confidence"] == 0.95

    # Check metadata fields
    assert "source_image" in ocr_data
    assert "created_at" in ocr_data


def test_run_page_with_ocr_empty_result(temp_dirs_with_image):
    """Test OCR with empty result (no text detected)."""
    # Mock empty OCR result
    mock_ocr_instance = MagicMock()
    mock_ocr_instance.ocr.return_value = None
    mock_paddle_class = MagicMock(return_value=mock_ocr_instance)

    output_dir = (
        temp_dirs_with_image["output_dir"] / "output" / "test-source" / "test-series" / "ch001" / "pages"
    )
    output_image = output_dir / "000_processed.png"
    output_manifest = output_dir / "page_000.out.json"
    ocr_output = output_dir / "page_000.ocr.json"

    job = PageJob(
        source_id="test-source",
        series_id="test-series",
        chapter_id="ch001",
        page_index=0,
        input_image_path=temp_dirs_with_image["input_image"],
        input_manifest_path=temp_dirs_with_image["input_manifest"],
        output_image_path=output_image,
        output_manifest_path=output_manifest,
        status="PENDING",
    )

    # Patch the PaddleOCR import inside run_ocr
    with patch.dict("sys.modules", {"paddleocr": MagicMock(PaddleOCR=mock_paddle_class)}):
        result = run_page(job, with_ocr=True)

    # Check success
    assert result.status == "DONE"

    # Check OCR file exists with empty lines
    assert ocr_output.exists()

    with open(ocr_output, encoding="utf-8") as f:
        ocr_data = json.load(f)

    assert ocr_data["lines"] == []
    assert ocr_data["engine"] == "paddleocr"

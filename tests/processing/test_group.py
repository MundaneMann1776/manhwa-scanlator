"""Tests for OCR line grouping functionality."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.processing.group import (
    bbox_to_rect,
    compute_distance,
    compute_vertical_distance,
    group_lines,
    union_bbox,
)
from src.processing.job import PageJob
from src.processing.runner import run_page


def test_bbox_to_rect():
    """Test bounding box to rectangle conversion."""
    bbox = [[10, 20], [90, 20], [90, 40], [10, 40]]
    rect = bbox_to_rect(bbox)
    assert rect == (10, 20, 90, 40)


def test_compute_distance_overlapping():
    """Test distance between overlapping rectangles."""
    rect1 = (10, 10, 50, 30)
    rect2 = (40, 20, 80, 40)
    dist = compute_distance(rect1, rect2)
    assert dist == 0.0


def test_compute_distance_separated():
    """Test distance between separated rectangles."""
    rect1 = (10, 10, 30, 30)
    rect2 = (40, 10, 60, 30)
    dist = compute_distance(rect1, rect2)
    assert dist == 10.0  # Horizontal distance only


def test_compute_vertical_distance():
    """Test vertical distance computation."""
    rect1 = (10, 10, 50, 30)
    rect2 = (10, 50, 50, 70)
    vert_dist = compute_vertical_distance(rect1, rect2)
    assert vert_dist == 20.0


def test_union_bbox():
    """Test union of multiple bounding boxes."""
    bboxes = [
        [[10, 10], [30, 10], [30, 20], [10, 20]],
        [[20, 25], [50, 25], [50, 35], [20, 35]],
    ]
    union = union_bbox(bboxes)
    # Should contain both boxes
    assert union == [[10, 10], [50, 10], [50, 35], [10, 35]]


def test_group_lines_empty():
    """Test grouping with no OCR lines."""
    ocr_result = {"lines": [], "source_image": "test.png"}
    result = group_lines(ocr_result)

    assert result["engine"] == "heuristic"
    assert result["groups"] == []
    assert "created_at" in result


def test_group_lines_single_line():
    """Test grouping with single OCR line."""
    ocr_result = {
        "lines": [{"text": "Hello", "confidence": 0.95, "bbox": [[10, 10], [50, 10], [50, 30], [10, 30]]}],
        "source_image": "test.png",
    }
    result = group_lines(ocr_result)

    assert result["engine"] == "heuristic"
    assert len(result["groups"]) == 1
    assert result["groups"][0]["group_id"] == 1
    assert result["groups"][0]["lines"] == [0]
    assert result["groups"][0]["bbox"] == [[10, 10], [50, 10], [50, 30], [10, 30]]


def test_group_lines_close_vertical():
    """Test grouping lines that are close vertically."""
    ocr_result = {
        "lines": [
            # Two lines close together (should be grouped)
            {"text": "Line 1", "confidence": 0.95, "bbox": [[10, 10], [50, 10], [50, 30], [10, 30]]},
            {"text": "Line 2", "confidence": 0.95, "bbox": [[10, 35], [50, 35], [50, 55], [10, 55]]},
        ],
        "source_image": "test.png",
    }
    result = group_lines(ocr_result)

    assert len(result["groups"]) == 1  # Should be grouped together
    assert result["groups"][0]["lines"] == [0, 1]


def test_group_lines_far_vertical():
    """Test grouping lines that are far apart vertically."""
    ocr_result = {
        "lines": [
            # Two lines far apart (should NOT be grouped)
            {"text": "Line 1", "confidence": 0.95, "bbox": [[10, 10], [50, 10], [50, 30], [10, 30]]},
            {"text": "Line 2", "confidence": 0.95, "bbox": [[10, 100], [50, 100], [50, 120], [10, 120]]},
        ],
        "source_image": "test.png",
    }
    result = group_lines(ocr_result)

    assert len(result["groups"]) == 2  # Should be separate groups
    assert result["groups"][0]["lines"] == [0]
    assert result["groups"][1]["lines"] == [1]


def test_group_lines_multiple_groups():
    """Test grouping with multiple distinct regions."""
    ocr_result = {
        "lines": [
            # Group 1: two close lines at top
            {"text": "A1", "confidence": 0.95, "bbox": [[10, 10], [50, 10], [50, 25], [10, 25]]},
            {"text": "A2", "confidence": 0.95, "bbox": [[10, 28], [50, 28], [50, 43], [10, 43]]},
            # Group 2: two close lines at bottom
            {"text": "B1", "confidence": 0.95, "bbox": [[10, 100], [50, 100], [50, 115], [10, 115]]},
            {"text": "B2", "confidence": 0.95, "bbox": [[10, 118], [50, 118], [50, 133], [10, 133]]},
        ],
        "source_image": "test.png",
    }
    result = group_lines(ocr_result)

    assert len(result["groups"]) == 2
    # Groups should be sorted by vertical position
    assert result["groups"][0]["lines"] == [0, 1]  # Top group
    assert result["groups"][1]["lines"] == [2, 3]  # Bottom group


def test_group_lines_preserves_line_order():
    """Test that lines within groups maintain vertical order."""
    ocr_result = {
        "lines": [
            {"text": "Line 2", "confidence": 0.95, "bbox": [[10, 40], [50, 40], [50, 55], [10, 55]]},
            {"text": "Line 1", "confidence": 0.95, "bbox": [[10, 10], [50, 10], [50, 25], [10, 25]]},
            {"text": "Line 3", "confidence": 0.95, "bbox": [[10, 60], [50, 60], [50, 75], [10, 75]]},
        ],
        "source_image": "test.png",
    }
    result = group_lines(ocr_result)

    assert len(result["groups"]) == 1
    # Lines should be sorted by vertical position within group
    assert result["groups"][0]["lines"] == [1, 0, 2]  # Sorted top to bottom


def test_group_lines_bbox_union():
    """Test that group bounding box is union of member boxes."""
    ocr_result = {
        "lines": [
            {"text": "Short", "confidence": 0.95, "bbox": [[10, 10], [40, 10], [40, 25], [10, 25]]},
            {"text": "Much longer line", "confidence": 0.95, "bbox": [[10, 28], [80, 28], [80, 43], [10, 43]]},
        ],
        "source_image": "test.png",
    }
    result = group_lines(ocr_result)

    assert len(result["groups"]) == 1
    # Union should cover both lines
    bbox = result["groups"][0]["bbox"]
    rect = bbox_to_rect(bbox)
    assert rect == (10, 10, 80, 43)


@pytest.fixture
def temp_dirs_with_ocr():
    """Create temporary directories with OCR output for testing."""
    with tempfile.TemporaryDirectory() as input_tmpdir, tempfile.TemporaryDirectory() as output_tmpdir:
        input_dir = Path(input_tmpdir)
        output_dir = Path(output_tmpdir)

        # Create input structure
        input_path = input_dir / "sources" / "test-source" / "test-series" / "ch001" / "pages"
        input_path.mkdir(parents=True, exist_ok=True)

        # Create dummy image
        from PIL import Image

        img = Image.new("RGB", (100, 100), color="white")
        img.save(input_path / "000.png")

        # Create input manifest
        input_manifest = {
            "page_index": 0,
            "source_url": "test://example.com/000.png",
            "chapter_id": "ch001",
        }
        input_manifest_path = input_path / "page_000.json"
        with open(input_manifest_path, "w") as f:
            json.dump(input_manifest, f, indent=2)

        # Create OCR output
        ocr_output_dir = output_dir / "output" / "test-source" / "test-series" / "ch001" / "pages"
        ocr_output_dir.mkdir(parents=True, exist_ok=True)

        ocr_result = {
            "engine": "paddleocr",
            "language": "ko",
            "lines": [
                {"text": "안녕", "confidence": 0.98, "bbox": [[10, 10], [40, 10], [40, 25], [10, 25]]},
                {"text": "하세요", "confidence": 0.95, "bbox": [[10, 28], [50, 28], [50, 43], [10, 43]]},
                {"text": "테스트", "confidence": 0.97, "bbox": [[10, 80], [50, 80], [50, 95], [10, 95]]},
            ],
            "source_image": str(input_path / "000.png"),
            "created_at": "2024-01-01T00:00:00",
        }
        ocr_output_path = ocr_output_dir / "page_000.ocr.json"
        with open(ocr_output_path, "w", encoding="utf-8") as f:
            json.dump(ocr_result, f, indent=2, ensure_ascii=False)

        yield {
            "input_dir": input_dir,
            "output_dir": output_dir,
            "input_image": input_path / "000.png",
            "input_manifest": input_manifest_path,
            "ocr_output": ocr_output_path,
        }


def test_run_page_with_grouping(temp_dirs_with_ocr):
    """Test run_page with grouping enabled (OCR already exists)."""
    output_dir = (
        temp_dirs_with_ocr["output_dir"] / "output" / "test-source" / "test-series" / "ch001" / "pages"
    )
    output_image = output_dir / "000_processed.png"
    output_manifest = output_dir / "page_000.out.json"
    grouping_output = output_dir / "page_000.groups.json"

    job = PageJob(
        source_id="test-source",
        series_id="test-series",
        chapter_id="ch001",
        page_index=0,
        input_image_path=temp_dirs_with_ocr["input_image"],
        input_manifest_path=temp_dirs_with_ocr["input_manifest"],
        output_image_path=output_image,
        output_manifest_path=output_manifest,
        status="PENDING",
    )

    # Run with grouping (OCR file already exists)
    result = run_page(job, with_grouping=True)

    # Check success
    assert result.status == "DONE"
    assert result.error is None

    # Check grouping file created
    assert grouping_output.exists()

    # Read and verify grouping result
    with open(grouping_output, "r", encoding="utf-8") as f:
        grouping_data = json.load(f)

    assert grouping_data["engine"] == "heuristic"
    assert len(grouping_data["groups"]) == 2  # Two groups (first two close, third far)
    assert grouping_data["groups"][0]["lines"] == [0, 1]  # First group
    assert grouping_data["groups"][1]["lines"] == [2]  # Second group (far away)
    assert "created_at" in grouping_data


def test_run_page_with_grouping_no_ocr(temp_dirs_with_ocr):
    """Test run_page with grouping when OCR file missing."""
    output_dir = (
        temp_dirs_with_ocr["output_dir"] / "output" / "test-source" / "test-series" / "ch002" / "pages"
    )
    output_image = output_dir / "000_processed.png"
    output_manifest = output_dir / "page_000.out.json"

    job = PageJob(
        source_id="test-source",
        series_id="test-series",
        chapter_id="ch002",  # Different chapter, no OCR
        page_index=0,
        input_image_path=temp_dirs_with_ocr["input_image"],
        input_manifest_path=temp_dirs_with_ocr["input_manifest"],
        output_image_path=output_image,
        output_manifest_path=output_manifest,
        status="PENDING",
    )

    # Run with grouping but no OCR file
    result = run_page(job, with_grouping=True)

    # Check failure
    assert result.status == "FAILED"
    assert "OCR file not found for grouping" in result.error


def test_run_page_with_ocr_and_grouping(temp_dirs_with_ocr):
    """Test run_page with both OCR and grouping enabled."""
    # Mock PaddleOCR
    mock_ocr_instance = MagicMock()
    mock_ocr_instance.ocr.return_value = [
        [
            [[[10, 10], [40, 10], [40, 25], [10, 25]], ("라인1", 0.98)],
            [[[10, 28], [50, 28], [50, 43], [10, 43]], ("라인2", 0.95)],
        ]
    ]
    mock_paddle_class = MagicMock(return_value=mock_ocr_instance)

    output_dir = (
        temp_dirs_with_ocr["output_dir"] / "output" / "test-source" / "test-series" / "ch003" / "pages"
    )
    output_image = output_dir / "000_processed.png"
    output_manifest = output_dir / "page_000.out.json"
    grouping_output = output_dir / "page_000.groups.json"

    job = PageJob(
        source_id="test-source",
        series_id="test-series",
        chapter_id="ch003",
        page_index=0,
        input_image_path=temp_dirs_with_ocr["input_image"],
        input_manifest_path=temp_dirs_with_ocr["input_manifest"],
        output_image_path=output_image,
        output_manifest_path=output_manifest,
        status="PENDING",
    )

    # Run with both OCR and grouping
    with patch.dict("sys.modules", {"paddleocr": MagicMock(PaddleOCR=mock_paddle_class)}):
        result = run_page(job, with_ocr=True, with_grouping=True)

    # Check success
    assert result.status == "DONE"
    assert result.error is None

    # Check both OCR and grouping files created
    ocr_output = output_dir / "page_000.ocr.json"
    assert ocr_output.exists()
    assert grouping_output.exists()

    # Verify grouping result
    with open(grouping_output, "r", encoding="utf-8") as f:
        grouping_data = json.load(f)

    assert grouping_data["engine"] == "heuristic"
    assert len(grouping_data["groups"]) == 1  # Close lines grouped together
    assert grouping_data["groups"][0]["lines"] == [0, 1]

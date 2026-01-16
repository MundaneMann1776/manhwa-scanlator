"""Tests for text inpainting functionality."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

from src.processing.inpaint import (
    bbox_to_rect,
    create_mask_from_groups,
    expand_rect,
    run_inpaint,
)
from src.processing.job import PageJob
from src.processing.runner import run_page


def test_bbox_to_rect():
    """Test bounding box to integer rectangle conversion."""
    bbox = [[10.5, 20.3], [90.7, 20.3], [90.7, 40.9], [10.5, 40.9]]
    rect = bbox_to_rect(bbox)
    assert rect == (10, 20, 90, 40)


def test_expand_rect():
    """Test rectangle expansion with padding."""
    rect = (10, 10, 50, 50)
    expanded = expand_rect(rect, padding=5, width=100, height=100)
    assert expanded == (5, 5, 55, 55)


def test_expand_rect_clipped():
    """Test rectangle expansion clipped to image bounds."""
    rect = (5, 5, 50, 50)
    expanded = expand_rect(rect, padding=10, width=100, height=100)
    # Should clip to (0, 0) on the left/top
    assert expanded == (0, 0, 60, 60)

    rect = (50, 50, 95, 95)
    expanded = expand_rect(rect, padding=10, width=100, height=100)
    # Should clip to (100, 100) on the right/bottom
    assert expanded == (40, 40, 100, 100)


def test_create_mask_single_group():
    """Test mask creation with single group."""
    groups = {
        "groups": [
            {
                "group_id": 1,
                "lines": [0],
                "bbox": [[10, 10], [50, 10], [50, 30], [10, 30]],
            }
        ]
    }

    mask = create_mask_from_groups(groups, width=100, height=100, padding=0)

    # Check mask shape
    assert mask.shape == (100, 100)

    # Check that region is marked for inpainting
    assert (mask[10:30, 10:50] == 255).all()

    # Check that outside region is preserved
    assert (mask[0:10, :] == 0).all()
    assert (mask[30:, :] == 0).all()


def test_create_mask_multiple_groups():
    """Test mask creation with multiple groups."""
    groups = {
        "groups": [
            {"group_id": 1, "lines": [0], "bbox": [[10, 10], [50, 10], [50, 30], [10, 30]]},
            {"group_id": 2, "lines": [1], "bbox": [[10, 50], [50, 50], [50, 70], [10, 70]]},
        ]
    }

    mask = create_mask_from_groups(groups, width=100, height=100, padding=0)

    # Check both regions are marked
    assert (mask[10:30, 10:50] == 255).all()
    assert (mask[50:70, 10:50] == 255).all()

    # Check gap between regions is preserved
    assert (mask[30:50, 10:50] == 0).all()


def test_create_mask_with_padding():
    """Test mask creation with padding expansion."""
    groups = {
        "groups": [
            {"group_id": 1, "lines": [0], "bbox": [[10, 10], [50, 10], [50, 30], [10, 30]]},
        ]
    }

    mask = create_mask_from_groups(groups, width=100, height=100, padding=5)

    # With padding=5, region should be expanded to [5:35, 5:55]
    assert (mask[5:35, 5:55] == 255).all()

    # Original region without padding should definitely be masked
    assert (mask[10:30, 10:50] == 255).all()


def test_create_mask_empty_groups():
    """Test mask creation with no groups."""
    groups = {"groups": []}

    mask = create_mask_from_groups(groups, width=100, height=100, padding=5)

    # Entire mask should be preserved (all zeros)
    assert (mask == 0).all()


@pytest.fixture
def temp_dirs_with_grouping():
    """Create temporary directories with grouping output for testing."""
    with tempfile.TemporaryDirectory() as input_tmpdir, tempfile.TemporaryDirectory() as output_tmpdir:
        input_dir = Path(input_tmpdir)
        output_dir = Path(output_tmpdir)

        # Create input structure
        input_path = input_dir / "sources" / "test-source" / "test-series" / "ch001" / "pages"
        input_path.mkdir(parents=True, exist_ok=True)

        # Create test image (simple pattern for verification)
        img = Image.new("RGB", (100, 100), color="white")
        # Draw some colored rectangles where text would be
        pixels = img.load()
        for y in range(10, 30):
            for x in range(10, 50):
                pixels[x, y] = (255, 0, 0)  # Red region (text area 1)
        for y in range(50, 70):
            for x in range(10, 50):
                pixels[x, y] = (0, 0, 255)  # Blue region (text area 2)

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

        # Create output structure with grouping
        output_path = output_dir / "output" / "test-source" / "test-series" / "ch001" / "pages"
        output_path.mkdir(parents=True, exist_ok=True)

        # Copy image to output (simulating processing)
        img.save(output_path / "000_processed.png")

        # Create grouping result
        grouping_result = {
            "engine": "heuristic",
            "groups": [
                {"group_id": 1, "lines": [0], "bbox": [[10, 10], [50, 10], [50, 30], [10, 30]]},
                {"group_id": 2, "lines": [1], "bbox": [[10, 50], [50, 50], [50, 70], [10, 70]]},
            ],
            "source_ocr": str(input_path / "000.png"),
            "created_at": "2024-01-01T00:00:00",
        }
        grouping_output_path = output_path / "page_000.groups.json"
        with open(grouping_output_path, "w", encoding="utf-8") as f:
            json.dump(grouping_result, f, indent=2, ensure_ascii=False)

        yield {
            "input_dir": input_dir,
            "output_dir": output_dir,
            "input_image": input_path / "000.png",
            "input_manifest": input_manifest_path,
            "output_image": output_path / "000_processed.png",
            "grouping_output": grouping_output_path,
        }


def test_run_inpaint_creates_cleaned_image(temp_dirs_with_grouping):
    """Test that run_inpaint creates a cleaned output image."""
    # Load grouping result
    with open(temp_dirs_with_grouping["grouping_output"], "r", encoding="utf-8") as f:
        grouping_result = json.load(f)

    # Mock cv2.inpaint to return a modified image
    with patch("src.processing.inpaint.cv2.imread") as mock_imread, \
         patch("src.processing.inpaint.cv2.inpaint") as mock_inpaint, \
         patch("src.processing.inpaint.cv2.imwrite") as mock_imwrite:

        # Mock imread to return a numpy array
        mock_image = np.ones((100, 100, 3), dtype=np.uint8) * 255
        mock_imread.return_value = mock_image

        # Mock inpaint to return a modified image
        mock_inpainted = np.ones((100, 100, 3), dtype=np.uint8) * 128
        mock_inpaint.return_value = mock_inpainted

        # Mock imwrite to succeed
        mock_imwrite.return_value = True

        # Run inpainting
        cleaned_path = run_inpaint(temp_dirs_with_grouping["output_image"], grouping_result)

        # Check that imread was called with correct path
        mock_imread.assert_called_once_with(str(temp_dirs_with_grouping["output_image"]))

        # Check that inpaint was called
        assert mock_inpaint.called
        call_args = mock_inpaint.call_args
        image_arg = call_args[0][0]
        mask_arg = call_args[0][1]

        # Verify image shape
        assert image_arg.shape == (100, 100, 3)

        # Verify mask shape and that it has masked regions
        assert mask_arg.shape == (100, 100)
        assert mask_arg.max() == 255  # Should have some masked regions

        # Check that imwrite was called with correct path
        expected_cleaned_path = temp_dirs_with_grouping["output_image"].parent / "000_processed.cleaned.png"
        mock_imwrite.assert_called_once()
        assert Path(mock_imwrite.call_args[0][0]) == expected_cleaned_path

        # Check returned path
        assert cleaned_path == expected_cleaned_path


def test_run_inpaint_invalid_image():
    """Test run_inpaint with invalid image path."""
    grouping_result = {"groups": []}

    with patch("src.processing.inpaint.cv2.imread") as mock_imread:
        mock_imread.return_value = None

        with pytest.raises(ValueError, match="Failed to load image"):
            run_inpaint(Path("/nonexistent/image.png"), grouping_result)


def test_run_page_with_inpaint(temp_dirs_with_grouping):
    """Test run_page with inpainting enabled (grouping already exists)."""
    output_dir = temp_dirs_with_grouping["output_dir"] / "output" / "test-source" / "test-series" / "ch001" / "pages"
    output_image = output_dir / "000_processed.png"
    output_manifest = output_dir / "page_000.out.json"
    cleaned_output = output_dir / "000_processed.cleaned.png"

    job = PageJob(
        source_id="test-source",
        series_id="test-series",
        chapter_id="ch001",
        page_index=0,
        input_image_path=temp_dirs_with_grouping["input_image"],
        input_manifest_path=temp_dirs_with_grouping["input_manifest"],
        output_image_path=output_image,
        output_manifest_path=output_manifest,
        status="PENDING",
    )

    # Mock cv2 operations
    with patch("src.processing.inpaint.cv2.imread") as mock_imread, \
         patch("src.processing.inpaint.cv2.inpaint") as mock_inpaint, \
         patch("src.processing.inpaint.cv2.imwrite") as mock_imwrite:

        mock_image = np.ones((100, 100, 3), dtype=np.uint8) * 255
        mock_imread.return_value = mock_image
        mock_inpaint.return_value = mock_image
        mock_imwrite.return_value = True

        # Run with inpainting (grouping file already exists)
        result = run_page(job, with_inpaint=True)

        # Check success
        assert result.status == "DONE"
        assert result.error is None

        # Verify cv2 operations were called
        assert mock_imread.called
        assert mock_inpaint.called
        assert mock_imwrite.called


def test_run_page_with_inpaint_no_grouping(temp_dirs_with_grouping):
    """Test run_page with inpainting when grouping file missing."""
    output_dir = temp_dirs_with_grouping["output_dir"] / "output" / "test-source" / "test-series" / "ch002" / "pages"
    output_image = output_dir / "000_processed.png"
    output_manifest = output_dir / "page_000.out.json"

    job = PageJob(
        source_id="test-source",
        series_id="test-series",
        chapter_id="ch002",  # Different chapter, no grouping
        page_index=0,
        input_image_path=temp_dirs_with_grouping["input_image"],
        input_manifest_path=temp_dirs_with_grouping["input_manifest"],
        output_image_path=output_image,
        output_manifest_path=output_manifest,
        status="PENDING",
    )

    # Run with inpainting but no grouping file
    result = run_page(job, with_inpaint=True)

    # Check failure
    assert result.status == "FAILED"
    assert "Grouping file not found for inpainting" in result.error


def test_run_page_full_pipeline(temp_dirs_with_grouping):
    """Test run_page with OCR, grouping, and inpainting all enabled."""
    # Mock PaddleOCR
    mock_ocr_instance = MagicMock()
    mock_ocr_instance.ocr.return_value = [
        [
            [[[10, 10], [50, 10], [50, 30], [10, 30]], ("텍스트1", 0.98)],
            [[[10, 50], [50, 50], [50, 70], [10, 70]], ("텍스트2", 0.95)],
        ]
    ]
    mock_paddle_class = MagicMock(return_value=mock_ocr_instance)

    output_dir = temp_dirs_with_grouping["output_dir"] / "output" / "test-source" / "test-series" / "ch003" / "pages"
    output_image = output_dir / "000_processed.png"
    output_manifest = output_dir / "page_000.out.json"
    cleaned_output = output_dir / "000_processed.cleaned.png"

    job = PageJob(
        source_id="test-source",
        series_id="test-series",
        chapter_id="ch003",
        page_index=0,
        input_image_path=temp_dirs_with_grouping["input_image"],
        input_manifest_path=temp_dirs_with_grouping["input_manifest"],
        output_image_path=output_image,
        output_manifest_path=output_manifest,
        status="PENDING",
    )

    # Mock both PaddleOCR and cv2
    with patch.dict("sys.modules", {"paddleocr": MagicMock(PaddleOCR=mock_paddle_class)}), \
         patch("src.processing.inpaint.cv2.imread") as mock_imread, \
         patch("src.processing.inpaint.cv2.inpaint") as mock_inpaint, \
         patch("src.processing.inpaint.cv2.imwrite") as mock_imwrite:

        mock_image = np.ones((100, 100, 3), dtype=np.uint8) * 255
        mock_imread.return_value = mock_image
        mock_inpaint.return_value = mock_image
        mock_imwrite.return_value = True

        # Run with OCR, grouping, and inpainting
        result = run_page(job, with_ocr=True, with_grouping=True, with_inpaint=True)

        # Check success
        assert result.status == "DONE"
        assert result.error is None

        # Verify all files were created
        ocr_output = output_dir / "page_000.ocr.json"
        grouping_output = output_dir / "page_000.groups.json"

        assert ocr_output.exists()
        assert grouping_output.exists()

        # Verify inpainting was called
        assert mock_inpaint.called

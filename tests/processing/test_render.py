"""Tests for text rendering functionality."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from src.processing.job import PageJob
from src.processing.render import (
    bbox_to_rect,
    calculate_font_size,
    render_page,
    wrap_text,
)
from src.processing.runner import run_page


def test_bbox_to_rect():
    """Test bounding box to integer rectangle conversion."""
    bbox = [[10.5, 20.3], [90.7, 20.3], [90.7, 40.9], [10.5, 40.9]]
    rect = bbox_to_rect(bbox)
    assert rect == (10, 20, 90, 40)


def test_calculate_font_size_small_bbox():
    """Test font size calculation for small bounding box."""
    size = calculate_font_size(bbox_width=50, bbox_height=30, text_length=10)
    assert 10 <= size <= 24


def test_calculate_font_size_large_bbox():
    """Test font size calculation for large bounding box."""
    size = calculate_font_size(bbox_width=200, bbox_height=100, text_length=10)
    assert 10 <= size <= 24


def test_calculate_font_size_long_text():
    """Test font size scales down for long text."""
    size_short = calculate_font_size(bbox_width=100, bbox_height=50, text_length=10)
    size_long = calculate_font_size(bbox_width=100, bbox_height=50, text_length=100)
    assert size_long <= size_short


def test_wrap_text():
    """Test text wrapping functionality."""
    mock_font = MagicMock()
    # Mock getbbox to return width based on text length
    mock_font.getbbox.side_effect = lambda text: (0, 0, len(text) * 10, 20)

    text = "This is a long text that should wrap"
    lines = wrap_text(text, mock_font, max_width=100)

    # Should wrap into multiple lines
    assert len(lines) > 1
    # Each line should be within bounds when measured
    for line in lines:
        bbox = mock_font.getbbox(line)
        width = bbox[2] - bbox[0]
        assert width <= 100 or line == lines[-1]  # Last line might be slightly over


def test_wrap_text_single_word():
    """Test text wrapping with single long word."""
    mock_font = MagicMock()
    mock_font.getbbox.side_effect = lambda text: (0, 0, len(text) * 10, 20)

    text = "Supercalifragilisticexpialidocious"
    lines = wrap_text(text, mock_font, max_width=50)

    # Should still add the word even if it's too long
    assert len(lines) == 1
    assert lines[0] == text


@pytest.fixture
def temp_dirs_with_full_pipeline():
    """Create temporary directories with all pipeline outputs for testing."""
    with tempfile.TemporaryDirectory() as input_tmpdir, tempfile.TemporaryDirectory() as output_tmpdir:
        input_dir = Path(input_tmpdir)
        output_dir = Path(output_tmpdir)

        # Create input structure
        input_path = input_dir / "sources" / "test-source" / "test-series" / "ch001" / "pages"
        input_path.mkdir(parents=True, exist_ok=True)

        # Create test image
        img = Image.new("RGB", (200, 200), color="white")
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

        # Create output structure
        output_path = output_dir / "output" / "test-source" / "test-series" / "ch001" / "pages"
        output_path.mkdir(parents=True, exist_ok=True)

        # Create cleaned image
        img.save(output_path / "000_processed.cleaned.png")

        # Create grouping result
        grouping_result = {
            "engine": "heuristic",
            "groups": [
                {"group_id": 1, "lines": [0, 1], "bbox": [[10, 10], [100, 10], [100, 50], [10, 50]]},
                {"group_id": 2, "lines": [2], "bbox": [[10, 100], [100, 100], [100, 130], [10, 130]]},
            ],
            "source_ocr": str(input_path / "000.png"),
            "created_at": "2024-01-01T00:00:00",
        }
        grouping_output_path = output_path / "page_000.groups.json"
        with open(grouping_output_path, "w", encoding="utf-8") as f:
            json.dump(grouping_result, f, indent=2, ensure_ascii=False)

        # Create translation result
        translation_result = {
            "engine": "papago",
            "source_language": "ko",
            "target_language": "en",
            "lines": [
                {"source_text": "안녕", "translated_text": "Hello", "confidence": 0.98},
                {"source_text": "하세요", "translated_text": "there", "confidence": 0.95},
                {"source_text": "테스트", "translated_text": "Test", "confidence": 0.97},
            ],
            "source_ocr": str(output_path / "page_000.ocr.json"),
            "created_at": "2024-01-01T00:00:00",
        }
        translation_output_path = output_path / "page_000.translated.json"
        with open(translation_output_path, "w", encoding="utf-8") as f:
            json.dump(translation_result, f, indent=2, ensure_ascii=False)

        yield {
            "input_dir": input_dir,
            "output_dir": output_dir,
            "input_image": input_path / "000.png",
            "input_manifest": input_manifest_path,
            "cleaned_image": output_path / "000_processed.cleaned.png",
            "grouping_output": grouping_output_path,
            "translation_output": translation_output_path,
        }


def test_render_page_creates_output(temp_dirs_with_full_pipeline):
    """Test that render_page creates a rendered output image."""
    # Load grouping and translation results
    with open(temp_dirs_with_full_pipeline["grouping_output"], "r", encoding="utf-8") as f:
        grouping_result = json.load(f)

    with open(temp_dirs_with_full_pipeline["translation_output"], "r", encoding="utf-8") as f:
        translation_result = json.load(f)

    # Mock PIL operations
    with patch("src.processing.render.ImageDraw.Draw") as mock_draw_class, \
         patch("src.processing.render.load_font") as mock_load_font:

        mock_draw = MagicMock()
        mock_draw_class.return_value = mock_draw

        mock_font = MagicMock()
        mock_font.getbbox.return_value = (0, 0, 50, 20)
        mock_load_font.return_value = mock_font

        # Run rendering
        rendered_path = render_page(
            temp_dirs_with_full_pipeline["cleaned_image"],
            grouping_result,
            translation_result
        )

        # Check that output path is correct
        expected_path = temp_dirs_with_full_pipeline["cleaned_image"].parent / "000_processed.rendered.png"
        assert rendered_path == expected_path

        # Check that image was saved
        assert rendered_path.exists()

        # Check that text was drawn (at least once for each group)
        assert mock_draw.text.call_count >= 2


def test_render_page_handles_empty_groups(temp_dirs_with_full_pipeline):
    """Test render_page with empty groups."""
    grouping_result = {"groups": []}
    translation_result = {"lines": []}

    with patch("src.processing.render.ImageDraw.Draw") as mock_draw_class, \
         patch("src.processing.render.load_font") as mock_load_font:

        mock_draw = MagicMock()
        mock_draw_class.return_value = mock_draw

        mock_font = MagicMock()
        mock_load_font.return_value = mock_font

        rendered_path = render_page(
            temp_dirs_with_full_pipeline["cleaned_image"],
            grouping_result,
            translation_result
        )

        # Should still create output
        assert rendered_path.exists()

        # No text should be drawn
        mock_draw.text.assert_not_called()


def test_render_page_handles_missing_translations(temp_dirs_with_full_pipeline):
    """Test render_page when some translations are missing."""
    with open(temp_dirs_with_full_pipeline["grouping_output"], "r", encoding="utf-8") as f:
        grouping_result = json.load(f)

    # Translation with fewer lines than groups
    translation_result = {
        "lines": [
            {"source_text": "안녕", "translated_text": "Hello", "confidence": 0.98},
        ]
    }

    with patch("src.processing.render.ImageDraw.Draw") as mock_draw_class, \
         patch("src.processing.render.load_font") as mock_load_font:

        mock_draw = MagicMock()
        mock_draw_class.return_value = mock_draw

        mock_font = MagicMock()
        mock_font.getbbox.return_value = (0, 0, 50, 20)
        mock_load_font.return_value = mock_font

        rendered_path = render_page(
            temp_dirs_with_full_pipeline["cleaned_image"],
            grouping_result,
            translation_result
        )

        # Should create output without crashing
        assert rendered_path.exists()


def test_run_page_with_render(temp_dirs_with_full_pipeline):
    """Test run_page with rendering enabled (all dependencies exist)."""
    output_dir = temp_dirs_with_full_pipeline["output_dir"] / "output" / "test-source" / "test-series" / "ch001" / "pages"
    output_image = output_dir / "000_processed.png"
    output_manifest = output_dir / "page_000.out.json"
    rendered_output = output_dir / "000_processed.rendered.png"

    job = PageJob(
        source_id="test-source",
        series_id="test-series",
        chapter_id="ch001",
        page_index=0,
        input_image_path=temp_dirs_with_full_pipeline["input_image"],
        input_manifest_path=temp_dirs_with_full_pipeline["input_manifest"],
        output_image_path=output_image,
        output_manifest_path=output_manifest,
        status="PENDING",
    )

    # Mock PIL operations
    with patch("src.processing.render.ImageDraw.Draw") as mock_draw_class, \
         patch("src.processing.render.load_font") as mock_load_font:

        mock_draw = MagicMock()
        mock_draw_class.return_value = mock_draw

        mock_font = MagicMock()
        mock_font.getbbox.return_value = (0, 0, 50, 20)
        mock_load_font.return_value = mock_font

        # Run with rendering (all files already exist)
        result = run_page(job, with_render=True)

        # Check success
        assert result.status == "DONE"
        assert result.error is None

        # Check that rendered image was created
        assert rendered_output.exists()


def test_run_page_with_render_missing_cleaned_image(temp_dirs_with_full_pipeline):
    """Test run_page with rendering when cleaned image missing."""
    output_dir = temp_dirs_with_full_pipeline["output_dir"] / "output" / "test-source" / "test-series" / "ch002" / "pages"
    output_image = output_dir / "000_processed.png"
    output_manifest = output_dir / "page_000.out.json"

    job = PageJob(
        source_id="test-source",
        series_id="test-series",
        chapter_id="ch002",  # Different chapter, no cleaned image
        page_index=0,
        input_image_path=temp_dirs_with_full_pipeline["input_image"],
        input_manifest_path=temp_dirs_with_full_pipeline["input_manifest"],
        output_image_path=output_image,
        output_manifest_path=output_manifest,
        status="PENDING",
    )

    # Run with rendering but no cleaned image
    result = run_page(job, with_render=True)

    # Check failure
    assert result.status == "FAILED"
    assert "Cleaned image not found for rendering" in result.error


def test_run_page_with_render_missing_translation(temp_dirs_with_full_pipeline):
    """Test run_page with rendering when translation file missing."""
    # Remove translation file
    temp_dirs_with_full_pipeline["translation_output"].unlink()

    output_dir = temp_dirs_with_full_pipeline["output_dir"] / "output" / "test-source" / "test-series" / "ch001" / "pages"
    output_image = output_dir / "000_processed.png"
    output_manifest = output_dir / "page_000.out.json"

    job = PageJob(
        source_id="test-source",
        series_id="test-series",
        chapter_id="ch001",
        page_index=0,
        input_image_path=temp_dirs_with_full_pipeline["input_image"],
        input_manifest_path=temp_dirs_with_full_pipeline["input_manifest"],
        output_image_path=output_image,
        output_manifest_path=output_manifest,
        status="PENDING",
    )

    # Run with rendering but no translation file
    result = run_page(job, with_render=True)

    # Check failure
    assert result.status == "FAILED"
    assert "Translation file not found for rendering" in result.error


def test_run_page_full_pipeline_with_render(temp_dirs_with_full_pipeline):
    """Test run_page with full pipeline including rendering."""
    # Mock PaddleOCR
    mock_ocr_instance = MagicMock()
    mock_ocr_instance.ocr.return_value = [
        [
            [[[10, 10], [100, 10], [100, 30], [10, 30]], ("안녕하세요", 0.98)],
        ]
    ]
    mock_paddle_class = MagicMock(return_value=mock_ocr_instance)

    # Mock Papago translation
    mock_translation_response = MagicMock()
    mock_translation_response.status_code = 200
    mock_translation_response.json.return_value = {
        "message": {"result": {"translatedText": "Hello"}}
    }

    output_dir = temp_dirs_with_full_pipeline["output_dir"] / "output" / "test-source" / "test-series" / "ch003" / "pages"
    output_image = output_dir / "000_processed.png"
    output_manifest = output_dir / "page_000.out.json"
    rendered_output = output_dir / "000_processed.rendered.png"

    job = PageJob(
        source_id="test-source",
        series_id="test-series",
        chapter_id="ch003",
        page_index=0,
        input_image_path=temp_dirs_with_full_pipeline["input_image"],
        input_manifest_path=temp_dirs_with_full_pipeline["input_manifest"],
        output_image_path=output_image,
        output_manifest_path=output_manifest,
        status="PENDING",
    )

    # Mock all external dependencies
    with patch.dict("sys.modules", {"paddleocr": MagicMock(PaddleOCR=mock_paddle_class)}), \
         patch("src.processing.translate.requests.post", return_value=mock_translation_response), \
         patch("src.processing.inpaint.cv2.imread") as mock_imread, \
         patch("src.processing.inpaint.cv2.inpaint") as mock_inpaint, \
         patch("src.processing.inpaint.cv2.imwrite") as mock_imwrite, \
         patch("src.processing.render.Image.open") as mock_image_open, \
         patch("src.processing.render.ImageDraw.Draw") as mock_draw_class, \
         patch("src.processing.render.load_font") as mock_load_font:

        # Mock cv2 for inpainting
        import numpy as np
        mock_cv_image = np.ones((200, 200, 3), dtype=np.uint8) * 255
        mock_imread.return_value = mock_cv_image
        mock_inpaint.return_value = mock_cv_image
        mock_imwrite.return_value = True

        # Mock PIL Image for rendering
        mock_pil_image = MagicMock()
        mock_pil_image.save = MagicMock()
        mock_image_open.return_value = mock_pil_image

        # Mock PIL Draw for rendering
        mock_draw = MagicMock()
        mock_draw_class.return_value = mock_draw

        mock_font = MagicMock()
        mock_font.getbbox.return_value = (0, 0, 50, 20)
        mock_load_font.return_value = mock_font

        # Run full pipeline: OCR → Translation → Grouping → Inpainting → Rendering
        result = run_page(job, with_ocr=True, with_translate=True, with_grouping=True, with_inpaint=True, with_render=True)

        # Check success
        assert result.status == "DONE"
        assert result.error is None

        # Check all JSON files created (images are mocked)
        ocr_output = output_dir / "page_000.ocr.json"
        translation_output = output_dir / "page_000.translated.json"
        grouping_output = output_dir / "page_000.groups.json"

        assert ocr_output.exists()
        assert translation_output.exists()
        assert grouping_output.exists()

        # Verify PIL operations were called
        assert mock_image_open.called
        assert mock_pil_image.save.called

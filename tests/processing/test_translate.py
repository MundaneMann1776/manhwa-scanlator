"""Tests for translation functionality."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from src.processing.job import PageJob
from src.processing.runner import run_page


@pytest.fixture
def temp_dirs_with_ocr():
    """Create temporary directories with test image, manifest, and OCR file."""
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

        # Create output directory structure for OCR file
        output_pages_dir = output_path / "output" / "test-source" / "test-series" / "ch001" / "pages"
        output_pages_dir.mkdir(parents=True)

        # Create OCR file in output directory
        ocr_data = {
            "engine": "paddleocr",
            "language": "ko",
            "lines": [
                {"text": "안녕하세요", "confidence": 0.98, "bbox": [[10, 10], [90, 10], [90, 30], [10, 30]]},
                {"text": "테스트입니다", "confidence": 0.95, "bbox": [[10, 40], [90, 40], [90, 60], [10, 60]]},
                {"text": "번역 테스트", "confidence": 0.92, "bbox": [[10, 70], [90, 70], [90, 90], [10, 90]]},
            ],
            "source_image": str(input_image),
            "created_at": "2024-01-01T00:00:00",
        }
        ocr_file = output_pages_dir / "page_000.ocr.json"
        with open(ocr_file, "w", encoding="utf-8") as f:
            json.dump(ocr_data, f, ensure_ascii=False)

        yield {
            "input_dir": input_path,
            "output_dir": output_path,
            "input_image": input_image,
            "input_manifest": input_manifest,
            "output_pages_dir": output_pages_dir,
            "ocr_file": ocr_file,
            "ocr_data": ocr_data,
        }


def mock_papago_translate(text: str, version: str) -> str:
    """Mock Papago translation - returns a fake English translation."""
    translations = {
        "안녕하세요": "Hello",
        "테스트입니다": "This is a test",
        "번역 테스트": "Translation test",
    }
    return translations.get(text, f"[Translated: {text}]")


def test_run_translation_success(temp_dirs_with_ocr):
    """Test that run_translation produces correct output with mocked Papago."""
    from src.processing.translate import run_translation

    with patch("src.processing.translate._get_papago_version") as mock_version, patch(
        "src.processing.translate._translate_text_papago"
    ) as mock_translate:
        mock_version.return_value = "v1.0.0"
        mock_translate.side_effect = mock_papago_translate

        result = run_translation(temp_dirs_with_ocr["ocr_data"], str(temp_dirs_with_ocr["ocr_file"]))

    # Verify structure
    assert result["engine"] == "papago"
    assert result["source_language"] == "ko"
    assert result["target_language"] == "en"
    assert result["source_ocr"] == str(temp_dirs_with_ocr["ocr_file"])
    assert "created_at" in result
    assert "lines" in result

    # Verify lines
    assert len(result["lines"]) == 3
    assert result["lines"][0]["source_text"] == "안녕하세요"
    assert result["lines"][0]["translated_text"] == "Hello"
    assert result["lines"][0]["confidence"] is None

    assert result["lines"][1]["source_text"] == "테스트입니다"
    assert result["lines"][1]["translated_text"] == "This is a test"

    assert result["lines"][2]["source_text"] == "번역 테스트"
    assert result["lines"][2]["translated_text"] == "Translation test"


def test_line_count_matches_ocr(temp_dirs_with_ocr):
    """Test that output line count exactly matches OCR input."""
    from src.processing.translate import run_translation

    with patch("src.processing.translate._get_papago_version") as mock_version, patch(
        "src.processing.translate._translate_text_papago"
    ) as mock_translate:
        mock_version.return_value = "v1.0.0"
        mock_translate.side_effect = mock_papago_translate

        result = run_translation(temp_dirs_with_ocr["ocr_data"])

    assert len(result["lines"]) == len(temp_dirs_with_ocr["ocr_data"]["lines"])


def test_source_text_preserved(temp_dirs_with_ocr):
    """Test that Korean source text is preserved in translation output."""
    from src.processing.translate import run_translation

    with patch("src.processing.translate._get_papago_version") as mock_version, patch(
        "src.processing.translate._translate_text_papago"
    ) as mock_translate:
        mock_version.return_value = "v1.0.0"
        mock_translate.side_effect = mock_papago_translate

        result = run_translation(temp_dirs_with_ocr["ocr_data"])

    # Verify all Korean source texts are preserved
    ocr_texts = [line["text"] for line in temp_dirs_with_ocr["ocr_data"]["lines"]]
    result_source_texts = [line["source_text"] for line in result["lines"]]
    assert ocr_texts == result_source_texts


def test_run_page_with_translate_success(temp_dirs_with_ocr):
    """Test end-to-end page processing with translation (mocked Papago)."""
    output_dir = temp_dirs_with_ocr["output_pages_dir"]
    output_image = output_dir / "000_processed.png"
    output_manifest = output_dir / "page_000.out.json"
    translation_output = output_dir / "page_000.translated.json"

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

    with patch("src.processing.translate._get_papago_version") as mock_version, patch(
        "src.processing.translate._translate_text_papago"
    ) as mock_translate:
        mock_version.return_value = "v1.0.0"
        mock_translate.side_effect = mock_papago_translate

        result = run_page(job, with_ocr=False, with_translate=True)

    # Check success
    assert result.status == "DONE"
    assert result.error is None

    # Check translation file exists
    assert translation_output.exists()

    # Verify translation content
    with open(translation_output, encoding="utf-8") as f:
        translation_data = json.load(f)

    assert translation_data["engine"] == "papago"
    assert translation_data["source_language"] == "ko"
    assert translation_data["target_language"] == "en"
    assert len(translation_data["lines"]) == 3
    assert translation_data["lines"][0]["source_text"] == "안녕하세요"
    assert translation_data["lines"][0]["translated_text"] == "Hello"


def test_translate_without_ocr_fails(temp_dirs_with_ocr):
    """Test that translation fails gracefully when OCR file is missing."""
    output_dir = temp_dirs_with_ocr["output_pages_dir"]
    output_image = output_dir / "001_processed.png"  # Different page index
    output_manifest = output_dir / "page_001.out.json"

    job = PageJob(
        source_id="test-source",
        series_id="test-series",
        chapter_id="ch001",
        page_index=1,  # No OCR file for page 1
        input_image_path=temp_dirs_with_ocr["input_image"],
        input_manifest_path=temp_dirs_with_ocr["input_manifest"],
        output_image_path=output_image,
        output_manifest_path=output_manifest,
        status="PENDING",
    )

    result = run_page(job, with_ocr=False, with_translate=True)

    # Check failure
    assert result.status == "FAILED"
    assert result.error is not None
    assert "OCR file not found" in result.error


def test_translate_empty_ocr(temp_dirs_with_ocr):
    """Test translation handles OCR with zero lines."""
    from src.processing.translate import run_translation

    empty_ocr = {
        "engine": "paddleocr",
        "language": "ko",
        "lines": [],
        "source_image": "test.png",
        "created_at": "2024-01-01T00:00:00",
    }

    with patch("src.processing.translate._get_papago_version") as mock_version, patch(
        "src.processing.translate._translate_text_papago"
    ) as mock_translate:
        mock_version.return_value = "v1.0.0"
        mock_translate.side_effect = mock_papago_translate

        result = run_translation(empty_ocr)

    assert result["engine"] == "papago"
    assert result["lines"] == []
    assert len(result["lines"]) == 0


def test_write_translation_result(temp_dirs_with_ocr):
    """Test that write_translation_result creates proper JSON file."""
    from src.processing.translate import write_translation_result

    translation_result = {
        "engine": "papago",
        "source_language": "ko",
        "target_language": "en",
        "lines": [
            {"source_text": "안녕", "translated_text": "Hi", "confidence": None}
        ],
        "source_ocr": "/path/to/ocr.json",
        "created_at": "2024-01-01T00:00:00",
    }

    output_path = temp_dirs_with_ocr["output_pages_dir"] / "test_translation.json"
    write_translation_result(translation_result, output_path)

    assert output_path.exists()

    with open(output_path, encoding="utf-8") as f:
        loaded = json.load(f)

    assert loaded == translation_result
    # Verify Korean characters are preserved (not escaped)
    with open(output_path, "r", encoding="utf-8") as f:
        raw_content = f.read()
    assert "안녕" in raw_content  # Should be actual Korean, not \\uXXXX

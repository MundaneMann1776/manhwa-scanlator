"""OCR functionality for processing pipeline."""

import json
from datetime import datetime
from pathlib import Path

from .job import PageJob


def run_ocr(job: PageJob) -> dict:
    """Run whole-page OCR on input image using PaddleOCR."""
    from paddleocr import PaddleOCR

    # Initialize PaddleOCR for Korean
    ocr_engine = PaddleOCR(lang="korean", use_angle_cls=False, show_log=False)

    # Run OCR on input image
    result = ocr_engine.ocr(str(job.input_image_path), cls=False)

    # Parse results into structured format
    lines = []
    if result and result[0]:
        for detection in result[0]:
            bbox = detection[0]  # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
            text_info = detection[1]  # (text, confidence)
            text = text_info[0]
            confidence = float(text_info[1])

            lines.append({"text": text, "confidence": confidence, "bbox": bbox})

    # Construct OCR result
    ocr_result = {
        "engine": "paddleocr",
        "language": "ko",
        "lines": lines,
        "source_image": str(job.input_image_path),
        "created_at": datetime.utcnow().isoformat(),
    }

    return ocr_result


def write_ocr_result(ocr_result: dict, output_path: Path) -> None:
    """Write OCR result to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(ocr_result, f, indent=2, ensure_ascii=False)

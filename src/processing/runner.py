"""Processing runner for executing page jobs."""

import json
import shutil
from datetime import datetime
from pathlib import Path

from .job import PageJob


def run_page(job: PageJob, with_ocr: bool = False, with_translate: bool = False, with_grouping: bool = False, with_inpaint: bool = False) -> PageJob:
    """Execute a single page processing job.

    Args:
        job: PageJob to execute
        with_ocr: If True, run OCR on the page and write page.ocr.json
        with_translate: If True, translate OCR text and write page.translated.json
                        Requires OCR file to exist (either from with_ocr or previous run)
        with_grouping: If True, group OCR lines into regions and write page.groups.json
                       Requires OCR file to exist (either from with_ocr or previous run)
        with_inpaint: If True, inpaint text regions and write page.cleaned.png
                      Requires grouping file to exist (either from with_grouping or previous run)
    """
    try:
        # Validate input files exist
        if not job.input_image_path.exists():
            job.status = "FAILED"
            job.error = f"Input image not found: {job.input_image_path}"
            return job

        if not job.input_manifest_path.exists():
            job.status = "FAILED"
            job.error = f"Input manifest not found: {job.input_manifest_path}"
            return job

        # Create output directory
        job.output_image_path.parent.mkdir(parents=True, exist_ok=True)
        job.output_manifest_path.parent.mkdir(parents=True, exist_ok=True)

        # Copy input image to output
        shutil.copy2(job.input_image_path, job.output_image_path)

        # Read input manifest
        with open(job.input_manifest_path, "r") as f:
            input_manifest = json.load(f)

        # Write output manifest
        output_manifest = {
            "input_manifest": str(job.input_manifest_path),
            "input_image": str(job.input_image_path),
            "output_image": str(job.output_image_path),
            "status": "DONE",
            "processed_at": datetime.utcnow().isoformat(),
            "source_id": job.source_id,
            "series_id": job.series_id,
            "chapter_id": job.chapter_id,
            "page_index": job.page_index,
        }

        with open(job.output_manifest_path, "w") as f:
            json.dump(output_manifest, f, indent=2)

        # Run OCR if requested
        ocr_output_path = job.output_manifest_path.parent / f"page_{job.page_index:03d}.ocr.json"
        if with_ocr:
            from .ocr import run_ocr, write_ocr_result

            ocr_result = run_ocr(job)

            # Write OCR result to separate file
            write_ocr_result(ocr_result, ocr_output_path)

        # Run translation if requested
        if with_translate:
            from .translate import run_translation, write_translation_result

            # Check if OCR file exists
            if not ocr_output_path.exists():
                job.status = "FAILED"
                job.error = f"OCR file not found for translation: {ocr_output_path}"
                return job

            # Read OCR result
            with open(ocr_output_path, "r", encoding="utf-8") as f:
                ocr_result = json.load(f)

            # Run translation
            translation_result = run_translation(ocr_result, str(ocr_output_path))

            # Write translation result
            translation_output_path = job.output_manifest_path.parent / f"page_{job.page_index:03d}.translated.json"
            write_translation_result(translation_result, translation_output_path)

        # Run grouping if requested
        grouping_output_path = job.output_manifest_path.parent / f"page_{job.page_index:03d}.groups.json"
        if with_grouping:
            from .group import group_lines, write_grouping_result

            # Check if OCR file exists
            if not ocr_output_path.exists():
                job.status = "FAILED"
                job.error = f"OCR file not found for grouping: {ocr_output_path}"
                return job

            # Read OCR result
            with open(ocr_output_path, "r", encoding="utf-8") as f:
                ocr_result = json.load(f)

            # Run grouping
            grouping_result = group_lines(ocr_result)

            # Write grouping result
            write_grouping_result(grouping_result, grouping_output_path)

        # Run inpainting if requested
        if with_inpaint:
            from .inpaint import run_inpaint

            # Check if grouping file exists
            if not grouping_output_path.exists():
                job.status = "FAILED"
                job.error = f"Grouping file not found for inpainting: {grouping_output_path}"
                return job

            # Read grouping result
            with open(grouping_output_path, "r", encoding="utf-8") as f:
                grouping_result = json.load(f)

            # Run inpainting on the output image (which is a copy of input)
            cleaned_image_path = run_inpaint(job.output_image_path, grouping_result)

        # Update job status
        job.status = "DONE"
        job.error = None

    except Exception as e:
        job.status = "FAILED"
        job.error = str(e)

    return job

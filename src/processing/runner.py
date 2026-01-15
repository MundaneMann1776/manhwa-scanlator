"""Processing runner for executing page jobs."""

import json
import shutil
from datetime import datetime
from pathlib import Path

from .job import PageJob


def run_page(job: PageJob) -> PageJob:
    """Execute a single page processing job."""
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

        # Update job status
        job.status = "DONE"
        job.error = None

    except Exception as e:
        job.status = "FAILED"
        job.error = str(e)

    return job

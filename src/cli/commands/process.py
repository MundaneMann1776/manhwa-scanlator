"""Processing CLI commands."""

import json
from pathlib import Path

from src.processing.job import PageJob
from src.processing.runner import run_page


def cmd_process_page(args):
    """Process a single page from its manifest."""
    manifest_path = Path(args.manifest)

    if not manifest_path.exists():
        print(f"Manifest not found: {manifest_path}")
        return 1

    # Read input manifest
    try:
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
    except Exception as e:
        print(f"Failed to read manifest: {e}")
        return 1

    # Extract metadata from manifest path
    # Expected path: data/sources/{source}/{series}/{chapter}/pages/page_XXX.json
    parts = manifest_path.parts
    try:
        sources_idx = parts.index("sources")
        source_id = parts[sources_idx + 1]
        series_id = parts[sources_idx + 2]
        chapter_id = parts[sources_idx + 3]
        page_index = manifest.get("page_index", 0)
    except (ValueError, IndexError):
        print(f"Cannot parse source/series/chapter from path: {manifest_path}")
        return 1

    # Construct input paths
    input_image_path = manifest_path.parent / f"{page_index:03d}.png"
    input_manifest_path = manifest_path

    # Construct output paths
    output_root = Path(args.output_dir)
    output_dir = output_root / "output" / source_id / series_id / chapter_id / "pages"
    output_image_path = output_dir / f"{page_index:03d}_processed.png"
    output_manifest_path = output_dir / f"page_{page_index:03d}.out.json"

    # Create job
    job = PageJob(
        source_id=source_id,
        series_id=series_id,
        chapter_id=chapter_id,
        page_index=page_index,
        input_image_path=input_image_path,
        input_manifest_path=input_manifest_path,
        output_image_path=output_image_path,
        output_manifest_path=output_manifest_path,
        status="PENDING",
    )

    # Run job
    print(f"Processing page {page_index} from {chapter_id}...")
    if args.with_ocr:
        print("  Running OCR (Korean)...")
    if args.with_translate:
        print("  Running translation (Korean → English via Papago)...")
    if args.with_grouping:
        print("  Grouping OCR lines into regions...")
    if args.with_inpaint:
        print("  Inpainting text regions...")
    if args.with_render:
        print("  Rendering translated text...")
    result = run_page(job, with_ocr=args.with_ocr, with_translate=args.with_translate, with_grouping=args.with_grouping, with_inpaint=args.with_inpaint, with_render=args.with_render)

    if result.status == "DONE":
        print(f"✓ Success")
        print(f"  Output image: {result.output_image_path}")
        print(f"  Output manifest: {result.output_manifest_path}")
        if args.with_ocr:
            ocr_path = output_dir / f"page_{page_index:03d}.ocr.json"
            print(f"  OCR result: {ocr_path}")
        if args.with_translate:
            translate_path = output_dir / f"page_{page_index:03d}.translated.json"
            print(f"  Translation result: {translate_path}")
        if args.with_grouping:
            grouping_path = output_dir / f"page_{page_index:03d}.groups.json"
            print(f"  Grouping result: {grouping_path}")
        if args.with_inpaint:
            cleaned_path = output_dir / f"{page_index:03d}_processed.cleaned.png"
            print(f"  Cleaned image: {cleaned_path}")
        if args.with_render:
            rendered_path = output_dir / f"{page_index:03d}_processed.rendered.png"
            print(f"  Rendered image: {rendered_path}")
        return 0
    else:
        print(f"✗ Failed: {result.error}")
        return 1


def setup_process_commands(subparsers):
    """Setup processing subcommands."""
    process_page_parser = subparsers.add_parser("process-page", help="Process a single page")
    process_page_parser.add_argument("--manifest", required=True, help="Path to page manifest JSON")
    process_page_parser.add_argument("--output-dir", default="data", help="Output directory root")
    process_page_parser.add_argument("--with-ocr", action="store_true", help="Run OCR on the page (Korean)")
    process_page_parser.add_argument("--with-translate", action="store_true", help="Translate OCR text (Korean → English via Papago)")
    process_page_parser.add_argument("--with-grouping", action="store_true", help="Group OCR lines into regions (requires OCR)")
    process_page_parser.add_argument("--with-inpaint", action="store_true", help="Inpaint text regions (requires grouping)")
    process_page_parser.add_argument("--with-render", action="store_true", help="Render translated text (requires translation, grouping, and inpainting)")
    process_page_parser.set_defaults(func=cmd_process_page)

"""Acquisition CLI commands."""

import argparse
import json
from pathlib import Path

from src.acquisition.db import AcquisitionDB
from src.acquisition.downloader import download_chapter
from src.acquisition.filesystem_adapter import FilesystemAdapter


# Global registry of adapters
_ADAPTERS = {}


def register_adapter(source_id: str, adapter):
    """Register a source adapter."""
    _ADAPTERS[source_id] = adapter


def get_adapter(source_id: str):
    """Get registered adapter by source ID."""
    return _ADAPTERS.get(source_id)


def cmd_add_source(args):
    """Add a new source adapter."""
    if args.type == "filesystem":
        adapter = FilesystemAdapter(args.source_id, Path(args.path))
        register_adapter(args.source_id, adapter)
        print(f"Added filesystem source: {args.source_id} at {args.path}")
    else:
        print(f"Unknown source type: {args.type}")
        return 1

    return 0


def cmd_list_sources(args):
    """List all registered sources."""
    if not _ADAPTERS:
        print("No sources registered")
        return 0

    print("Registered sources:")
    for source_id in _ADAPTERS:
        print(f"  - {source_id}")

    return 0


def cmd_sync(args):
    """Sync a series from a source."""
    adapter = get_adapter(args.source_id)
    if not adapter:
        print(f"Source not found: {args.source_id}")
        return 1

    # List chapters
    chapters = adapter.list_chapters(args.series_id)
    if not chapters:
        print(f"No chapters found for series: {args.series_id}")
        return 1

    print(f"Found {len(chapters)} chapters for {args.series_id}")

    # Setup database and root path
    root_path = Path(args.data_dir)
    db_path = root_path / "acquisition.db"
    db = AcquisitionDB(db_path)

    # Register series
    db.register_series(args.source_id, args.series_id, args.series_id)

    # Download chapters
    for chapter in chapters:
        print(f"Downloading {chapter.chapter_id}...")
        result = download_chapter(adapter, chapter, root_path, db, max_workers=args.workers)

        if result.success:
            print(f"  ✓ Downloaded {result.pages_downloaded} pages")
        else:
            print(f"  ✗ Failed: {result.pages_failed} pages failed")
            for error in result.errors[:3]:  # Show first 3 errors
                print(f"    - {error}")

    db.close()
    return 0


def setup_acquire_commands(subparsers):
    """Setup acquisition subcommands."""
    # add-source command
    add_source_parser = subparsers.add_parser("add-source", help="Add a new source adapter")
    add_source_parser.add_argument("source_id", help="Unique identifier for the source")
    add_source_parser.add_argument("--type", required=True, choices=["filesystem"], help="Source adapter type")
    add_source_parser.add_argument("--path", required=True, help="Path for filesystem source")
    add_source_parser.set_defaults(func=cmd_add_source)

    # list-sources command
    list_sources_parser = subparsers.add_parser("list-sources", help="List registered sources")
    list_sources_parser.set_defaults(func=cmd_list_sources)

    # sync command
    sync_parser = subparsers.add_parser("sync", help="Sync a series from a source")
    sync_parser.add_argument("source_id", help="Source identifier")
    sync_parser.add_argument("--series-id", required=True, help="Series identifier")
    sync_parser.add_argument("--data-dir", default="data", help="Data directory")
    sync_parser.add_argument("--workers", type=int, default=4, help="Number of concurrent workers")
    sync_parser.set_defaults(func=cmd_sync)

"""Acquisition CLI commands."""

import argparse
import json
from pathlib import Path

from src.acquisition.db import AcquisitionDB
from src.acquisition.downloader import download_chapter
from src.acquisition.filesystem_adapter import FilesystemAdapter
from src.acquisition.adapters.manhwaraw import ManhwaRawAdapter
from src.acquisition import registry


def get_adapter(source_id: str):
    """Get adapter instance for a registered source.

    Args:
        source_id: Source identifier

    Returns:
        Instantiated adapter or None if source not found
    """
    source_config = registry.get_source(source_id)
    if not source_config:
        return None

    source_type = source_config.get("type")

    if source_type == "filesystem":
        path = source_config.get("path")
        if not path:
            print(f"Error: Filesystem source {source_id} missing path")
            return None
        return FilesystemAdapter(source_id, Path(path))
    elif source_type == "manhwaraw":
        return ManhwaRawAdapter()
    else:
        print(f"Error: Unknown source type: {source_type}")
        return None


def cmd_add_source(args):
    """Add a new source adapter."""
    if args.type == "filesystem":
        if not args.path:
            print("Error: --path is required for filesystem sources")
            return 1
        registry.add_source(args.source_id, args.type, path=args.path)
        print(f"Added filesystem source: {args.source_id} at {args.path}")
    elif args.type == "manhwaraw":
        registry.add_source(args.source_id, args.type)
        print(f"Added manhwaraw source: {args.source_id}")
    else:
        print(f"Unknown source type: {args.type}")
        return 1

    return 0


def cmd_list_sources(args):
    """List all registered sources."""
    sources = registry.list_sources()

    if not sources:
        print("No sources registered")
        return 0

    print("Registered sources:")
    for source_id, config in sources.items():
        source_type = config.get("type", "unknown")
        if source_type == "filesystem":
            path = config.get("path", "?")
            print(f"  - {source_id} ({source_type}: {path})")
        else:
            print(f"  - {source_id} ({source_type})")

    return 0


def cmd_search(args):
    """Search for series in a source."""
    adapter = get_adapter(args.source_id)
    if not adapter:
        print(f"Source not found: {args.source_id}")
        return 1

    try:
        results = adapter.discover_series(args.query)

        if not results:
            print(f"No results found for: {args.query}")
            return 0

        print(f"Found {len(results)} results for '{args.query}':\n")

        for idx, series in enumerate(results, 1):
            print(f"{idx}. {series.title}")
            print(f"   ID: {series.series_id}")
            print(f"   URL: {series.url}")
            if series.thumbnail_url:
                print(f"   Thumbnail: {series.thumbnail_url}")
            print()

        return 0

    except Exception as e:
        print(f"Search failed: {e}")
        return 1


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
    add_source_parser.add_argument("--type", required=True, choices=["filesystem", "manhwaraw"], help="Source adapter type")
    add_source_parser.add_argument("--path", help="Path for filesystem source (required if type=filesystem)")
    add_source_parser.set_defaults(func=cmd_add_source)

    # list-sources command
    list_sources_parser = subparsers.add_parser("list-sources", help="List registered sources")
    list_sources_parser.set_defaults(func=cmd_list_sources)

    # search command
    search_parser = subparsers.add_parser("search", help="Search for series in a source")
    search_parser.add_argument("source_id", help="Source identifier")
    search_parser.add_argument("query", help="Search query (series title)")
    search_parser.set_defaults(func=cmd_search)

    # sync command
    sync_parser = subparsers.add_parser("sync", help="Sync a series from a source")
    sync_parser.add_argument("source_id", help="Source identifier")
    sync_parser.add_argument("--series-id", required=True, help="Series identifier")
    sync_parser.add_argument("--data-dir", default="data", help="Data directory")
    sync_parser.add_argument("--workers", type=int, default=4, help="Number of concurrent workers")
    sync_parser.set_defaults(func=cmd_sync)

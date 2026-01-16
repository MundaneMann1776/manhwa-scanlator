"""Source registry with JSON persistence."""

import json
from pathlib import Path
from typing import Dict, Optional


REGISTRY_PATH = Path("data") / "sources.json"


def load_sources() -> Dict[str, dict]:
    """Load source registry from disk.

    Returns:
        Dict mapping source_id to source config
    """
    if not REGISTRY_PATH.exists():
        return {}

    try:
        with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"Warning: Failed to load source registry: {e}")
        return {}


def save_sources(sources: Dict[str, dict]) -> None:
    """Save source registry to disk.

    Args:
        sources: Dict mapping source_id to source config
    """
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
            json.dump(sources, f, indent=2, ensure_ascii=False)
    except OSError as e:
        print(f"Error: Failed to save source registry: {e}")
        raise


def add_source(source_id: str, source_type: str, **kwargs) -> None:
    """Add or update a source in the registry.

    Args:
        source_id: Unique identifier for the source
        source_type: Type of source adapter (filesystem, manhwaraw, etc.)
        **kwargs: Additional source-specific configuration
    """
    sources = load_sources()

    sources[source_id] = {
        "type": source_type,
        **kwargs
    }

    save_sources(sources)


def remove_source(source_id: str) -> bool:
    """Remove a source from the registry.

    Args:
        source_id: Source to remove

    Returns:
        True if source was removed, False if not found
    """
    sources = load_sources()

    if source_id in sources:
        del sources[source_id]
        save_sources(sources)
        return True

    return False


def get_source(source_id: str) -> Optional[dict]:
    """Get configuration for a specific source.

    Args:
        source_id: Source identifier

    Returns:
        Source config dict or None if not found
    """
    sources = load_sources()
    return sources.get(source_id)


def list_sources() -> Dict[str, dict]:
    """List all registered sources.

    Returns:
        Dict mapping source_id to source config
    """
    return load_sources()

# Source Adapter Development Guide

This guide explains how to implement a new source adapter for downloading manhwa chapters from web sources.

## Overview

A source adapter implements the `SourceAdapter` protocol defined in `src/acquisition/adapter.py`. The adapter is responsible for:

1. **Discovery**: Searching for series on the source
2. **Chapter Listing**: Enumerating available chapters for a series
3. **Page Download**: Downloading individual pages to local storage

## Implementing SourceAdapter

### Required Methods

```python
from src.acquisition.adapter import (
    SourceAdapter,
    SeriesInfo,
    ChapterInfo,
    PageDownloadResult,
)

class MySourceAdapter:
    @property
    def source_id(self) -> str:
        """Return unique identifier for this source (e.g., 'webtoon_kr')."""
        return "my_source"

    def discover_series(self, query: str) -> list[SeriesInfo]:
        """Search for series matching the query string."""
        # Implementation here
        pass

    def list_chapters(self, series_id: str) -> list[ChapterInfo]:
        """List all available chapters for a series."""
        # Implementation here
        pass

    def download_page(
        self,
        chapter_info: ChapterInfo,
        page_index: int,
        output_path: Path
    ) -> PageDownloadResult:
        """Download a single page to the specified output path."""
        # Implementation here
        pass
```

## Best Practices

### 1. Rate Limiting

Respect the source's server by implementing rate limiting:

```python
import time
from datetime import datetime, timedelta

class RateLimitedAdapter:
    def __init__(self):
        self._last_request = datetime.now()
        self._min_interval = timedelta(milliseconds=500)  # 2 requests/second max

    def _wait_for_rate_limit(self):
        """Enforce minimum time between requests."""
        elapsed = datetime.now() - self._last_request
        if elapsed < self._min_interval:
            time.sleep((self._min_interval - elapsed).total_seconds())
        self._last_request = datetime.now()

    def download_page(self, chapter_info, page_index, output_path):
        self._wait_for_rate_limit()
        # ... download logic
```

### 2. Authentication

If the source requires authentication, handle it in the adapter constructor:

```python
import requests

class AuthenticatedAdapter:
    def __init__(self, username: str, password: str):
        self.source_id = "authenticated_source"
        self.session = requests.Session()
        self._authenticate(username, password)

    def _authenticate(self, username: str, password: str):
        """Authenticate and store session cookies."""
        response = self.session.post(
            "https://example.com/login",
            data={"username": username, "password": password}
        )
        response.raise_for_status()
```

### 3. Error Handling

Always return explicit results, never raise exceptions from `download_page`:

```python
def download_page(self, chapter_info, page_index, output_path):
    try:
        # Download logic here
        response = self.session.get(page_url, timeout=30)
        response.raise_for_status()

        output_path.write_bytes(response.content)

        # Generate metadata
        metadata = PageMetadata(
            index=page_index,
            filename=output_path.name,
            width=width,
            height=height,
            size_bytes=len(response.content),
            sha256=hashlib.sha256(response.content).hexdigest(),
        )

        return PageDownloadResult(
            index=page_index,
            success=True,
            local_path=output_path,
            error=None,
            metadata=metadata,
        )

    except Exception as e:
        return PageDownloadResult(
            index=page_index,
            success=False,
            local_path=None,
            error=f"Download failed: {str(e)}",
            metadata=None,
        )
```

### 4. Politeness

Be a good citizen of the web:

- **User-Agent**: Set a descriptive User-Agent header
- **Caching**: Cache series/chapter metadata to reduce requests
- **Concurrent Limits**: Don't open too many connections simultaneously
- **Retry Backoff**: Use exponential backoff for retries (handled by downloader)

```python
class PoliteAdapter:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'ManhwaScanlator/1.0 (Educational; +https://github.com/...)'
        })
```

### 5. Dynamic Page Discovery

If page count is unknown upfront, set `page_count=None` and handle gracefully:

```python
def list_chapters(self, series_id: str) -> list[ChapterInfo]:
    chapters = []
    # ... fetch chapter list

    for ch in raw_chapters:
        chapters.append(ChapterInfo(
            source_id=self.source_id,
            series_id=series_id,
            chapter_id=ch["id"],
            chapter_title=ch["title"],
            chapter_url=ch["url"],
            page_count=None,  # Unknown until download starts
        ))

    return chapters
```

The downloader will attempt to download up to 100 pages by default when `page_count=None`.

## Legal and Ethical Considerations

### ⚠️ IMPORTANT LEGAL NOTE ⚠️

**This software is for educational and research purposes only.**

When implementing a source adapter, you must:

1. **Respect Copyright**: Ensure you have the legal right to download content from the source
2. **Check Terms of Service**: Review the source's ToS - automated scraping may be prohibited
3. **Honor robots.txt**: Respect the site's `robots.txt` directives
4. **Private Use Only**: Do not redistribute downloaded content
5. **Support Creators**: Consider purchasing official translations when available

### Ethical Guidelines

- **Don't harm the source**: Excessive requests can overload servers
- **Don't bypass paywalls**: If content is paid, respect that
- **Credit the source**: Maintain attribution to original creators
- **Use responsibly**: This tool is for personal archival and language learning

### Geographic Restrictions

Some sources may have geographic licensing restrictions. Respect these by:

- Not implementing adapters for region-locked content
- Using official APIs when available
- Considering VPN usage implications in your jurisdiction

## Testing Your Adapter

Use the filesystem adapter as a reference implementation:

```bash
# Run adapter tests
pytest tests/acquisition/test_filesystem_adapter.py -v

# Test your adapter
pytest tests/acquisition/test_your_adapter.py -v
```

## Example: Simple HTTP Adapter

```python
import hashlib
import requests
from pathlib import Path
from PIL import Image
from io import BytesIO

from src.acquisition.adapter import *

class SimpleHTTPAdapter:
    """Adapter for sites with predictable URL patterns."""

    def __init__(self, source_id: str, base_url: str):
        self.source_id = source_id
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "ManhwaScanlator/1.0"

    def discover_series(self, query: str) -> list[SeriesInfo]:
        # Implementation depends on site's search API
        return []

    def list_chapters(self, series_id: str) -> list[ChapterInfo]:
        # Fetch chapter list from API or parse HTML
        url = f"{self.base_url}/series/{series_id}/chapters"
        response = self.session.get(url)
        chapters_data = response.json()

        return [
            ChapterInfo(
                source_id=self.source_id,
                series_id=series_id,
                chapter_id=ch["id"],
                chapter_title=ch["title"],
                chapter_url=ch["url"],
                page_count=ch.get("page_count"),
            )
            for ch in chapters_data
        ]

    def download_page(
        self, chapter_info: ChapterInfo, page_index: int, output_path: Path
    ) -> PageDownloadResult:
        try:
            # Construct page URL (pattern depends on site)
            page_url = f"{chapter_info.chapter_url}/page/{page_index}"

            response = self.session.get(page_url, timeout=30)
            response.raise_for_status()

            # Save to output path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(response.content)

            # Extract image dimensions
            img = Image.open(BytesIO(response.content))
            width, height = img.size

            # Compute metadata
            sha256 = hashlib.sha256(response.content).hexdigest()

            metadata = PageMetadata(
                index=page_index,
                filename=output_path.name,
                width=width,
                height=height,
                size_bytes=len(response.content),
                sha256=sha256,
            )

            return PageDownloadResult(
                index=page_index,
                success=True,
                local_path=output_path,
                error=None,
                metadata=metadata,
            )

        except Exception as e:
            return PageDownloadResult(
                index=page_index,
                success=False,
                local_path=None,
                error=str(e),
                metadata=None,
            )
```

## Registration

Register your adapter in the CLI or programmatically:

```python
from src.cli.commands.acquire import register_adapter
from my_adapters import MySourceAdapter

# Register the adapter
adapter = MySourceAdapter()
register_adapter(adapter.source_id, adapter)
```

## Additional Resources

- **Protocol Definition**: `src/acquisition/adapter.py`
- **Reference Implementation**: `src/acquisition/filesystem_adapter.py`
- **Downloader Logic**: `src/acquisition/downloader.py`
- **Storage Utilities**: `src/acquisition/storage.py`

## Support

For questions or issues with adapter development, please open an issue on the project repository.

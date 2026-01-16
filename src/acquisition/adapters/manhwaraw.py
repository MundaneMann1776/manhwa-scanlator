"""ManhwaRaw source adapter for Korean manhwa.

Site: https://manhwaraw.com
Type: Madara WordPress theme
Auth: None required
"""

import re
from typing import List
from urllib.parse import urljoin, quote

import requests
from bs4 import BeautifulSoup

from ..adapter import (
    SourceAdapter,
    SeriesInfo,
    ChapterInfo,
    PageMetadata,
)


class ManhwaRawAdapter(SourceAdapter):
    """Adapter for manhwaraw.com (Madara-based site)."""

    def __init__(self):
        self.base_url = "https://manhwaraw.com"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/120.0.0.0 Safari/537.36"
        })

    def discover_series(self, query: str) -> List[SeriesInfo]:
        """Search for series by title.

        Args:
            query: Search term (series title)

        Returns:
            List of matching series
        """
        # Madara search: ?s=query&post_type=wp-manga
        search_url = f"{self.base_url}/?s={quote(query)}&post_type=wp-manga"

        try:
            response = self.session.get(search_url, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            raise RuntimeError(f"Failed to search series: {e}")

        soup = BeautifulSoup(response.text, "html.parser")

        series_list = []

        # Try multiple selectors (site structure varies)
        # Option 1: .block-wrapper (current site structure as of Jan 2026)
        for link_elem in soup.select("a.block-wrapper"):
            url = link_elem.get("href", "")
            if not url or "/manhwa-raw/" not in url:
                continue

            # Get title from .movie-title-1 span
            title_elem = link_elem.select_one(".movie-title-1")
            if not title_elem:
                continue

            title = title_elem.get_text(strip=True)

            # Extract series ID from URL
            # Expected: https://manhwaraw.com/manhwa-raw/series-name/
            match = re.search(r"/manhwa-raw/([^/]+)/?$", url)
            if match:
                series_id = match.group(1)
            else:
                # Fallback: use last path segment
                series_id = url.rstrip("/").split("/")[-1]

            # Get thumbnail/cover image if available
            img_elem = link_elem.select_one("img")
            cover_url = img_elem.get("data-src") or img_elem.get("src") if img_elem else None

            series_list.append(SeriesInfo(
                source_id="manhwaraw",  # Fixed source identifier
                series_id=series_id,
                title=title,
                description=None,  # Not available in search results
                author=None,  # Not available in search results
                cover_url=cover_url
            ))

        # Option 2: .c-tabs-item__content (older Madara structure)
        if not series_list:
            for item in soup.select(".c-tabs-item__content"):
                title_elem = item.select_one(".post-title h3 a, .post-title a, h3 a")
                if not title_elem:
                    continue

                title = title_elem.get_text(strip=True)
                url = title_elem.get("href", "")

                if not url:
                    continue

                match = re.search(r"/manhwa-raw/([^/]+)/?$", url)
                if match:
                    series_id = match.group(1)
                else:
                    series_id = url.rstrip("/").split("/")[-1]

                img_elem = item.select_one("img")
                cover_url = img_elem.get("data-src") or img_elem.get("src") if img_elem else None

                series_list.append(SeriesInfo(
                    source_id="manhwaraw",
                    series_id=series_id,
                    title=title,
                    description=None,
                    author=None,
                    cover_url=cover_url
                ))

        # Option 3: .post-title (fallback structure)
        if not series_list:
            for item in soup.select(".post-title"):
                link_elem = item.select_one("a")
                if not link_elem:
                    continue

                title = link_elem.get_text(strip=True)
                url = link_elem.get("href", "")

                if not url:
                    continue

                match = re.search(r"/manhwa-raw/([^/]+)/?$", url)
                if match:
                    series_id = match.group(1)
                else:
                    series_id = url.rstrip("/").split("/")[-1]

                series_list.append(SeriesInfo(
                    source_id="manhwaraw",
                    series_id=series_id,
                    title=title,
                    description=None,
                    author=None,
                    cover_url=None
                ))

        return series_list

    def list_chapters(self, series_id: str) -> List[ChapterInfo]:
        """Get all chapters for a series.

        Args:
            series_id: Series identifier (e.g., "solo-leveling")

        Returns:
            List of chapters in reading order (oldest first)
        """
        series_url = f"{self.base_url}/manhwa-raw/{series_id}/"

        try:
            response = self.session.get(series_url, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            raise RuntimeError(f"Failed to fetch chapters for {series_id}: {e}")

        soup = BeautifulSoup(response.text, "html.parser")

        chapters = []

        # Madara chapter list: .wp-manga-chapter or .version-chap li a
        chapter_elements = soup.select(".wp-manga-chapter a, .version-chap li a, .listing-chapters_wrap li a")

        for elem in chapter_elements:
            chapter_url = elem.get("href", "")
            if not chapter_url:
                continue

            # Extract chapter title
            chapter_title = elem.get_text(strip=True)

            # Extract chapter ID from URL
            # Expected: https://manhwaraw.com/manhwa-raw/series/chapter-123/
            match = re.search(r"/manhwa-raw/[^/]+/([^/]+)/?$", chapter_url)
            if match:
                chapter_id = match.group(1)
            else:
                chapter_id = chapter_url.rstrip("/").split("/")[-1]

            # Extract chapter number if present
            # Try patterns: "Chapter 123", "Ch. 123", "123화"
            chapter_number = None
            number_match = re.search(r"(?:chapter|ch\.?|화)\s*(\d+)", chapter_title, re.IGNORECASE)
            if number_match:
                chapter_number = int(number_match.group(1))
            else:
                # Try plain number
                number_match = re.search(r"(\d+)", chapter_id)
                if number_match:
                    chapter_number = int(number_match.group(1))

            chapters.append(ChapterInfo(
                chapter_id=chapter_id,
                title=chapter_title,
                url=chapter_url,
                chapter_number=chapter_number
            ))

        # Madara lists newest first, reverse for reading order
        chapters.reverse()

        return chapters

    def download_page(self, series_id: str, chapter_id: str, page_index: int) -> PageMetadata:
        """Download a specific page from a chapter.

        Args:
            series_id: Series identifier
            chapter_id: Chapter identifier
            page_index: 0-based page index

        Returns:
            Page metadata with image URL
        """
        # First, get all pages for the chapter
        pages = self._get_all_pages(series_id, chapter_id)

        if page_index >= len(pages):
            raise ValueError(f"Page index {page_index} out of range (chapter has {len(pages)} pages)")

        return pages[page_index]

    def _get_all_pages(self, series_id: str, chapter_id: str) -> List[PageMetadata]:
        """Get all pages for a chapter (internal helper).

        Args:
            series_id: Series identifier
            chapter_id: Chapter identifier

        Returns:
            List of page metadata
        """
        # Madara: use ?style=list to get all images in one page load
        chapter_url = f"{self.base_url}/manhwa-raw/{series_id}/{chapter_id}/?style=list"

        try:
            response = self.session.get(chapter_url, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            raise RuntimeError(f"Failed to fetch pages for {series_id}/{chapter_id}: {e}")

        soup = BeautifulSoup(response.text, "html.parser")

        pages = []

        # Madara page images: .wp-manga-chapter-img or .reading-content img
        img_elements = soup.select(".wp-manga-chapter-img, .reading-content img, .page-break img")

        for idx, img in enumerate(img_elements):
            # Try data-src first (lazy loading), then src
            image_url = img.get("data-src") or img.get("src")

            if not image_url:
                continue

            # Make absolute URL
            image_url = urljoin(chapter_url, image_url)

            # Skip placeholder images
            if "loading" in image_url.lower() or "placeholder" in image_url.lower():
                continue

            pages.append(PageMetadata(
                page_index=idx,
                image_url=image_url,
                width=None,  # Unknown until downloaded
                height=None
            ))

        if not pages:
            raise ValueError(f"No pages found for {series_id}/{chapter_id}")

        return pages

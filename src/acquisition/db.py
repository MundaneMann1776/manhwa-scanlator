"""SQLite database for tracking acquisition state."""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional


class AcquisitionDB:
    """Database for tracking series, chapters, and page download state."""

    def __init__(self, db_path: Path):
        """Initialize database connection and create schema if needed."""
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self._create_schema()

    def _create_schema(self):
        """Create database schema if it doesn't exist."""
        cursor = self.conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS series (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL,
                series_id TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(source_id, series_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chapters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL,
                series_id TEXT NOT NULL,
                chapter_id TEXT NOT NULL,
                chapter_title TEXT NOT NULL,
                page_count INTEGER,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                UNIQUE(source_id, series_id, chapter_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL,
                series_id TEXT NOT NULL,
                chapter_id TEXT NOT NULL,
                page_index INTEGER NOT NULL,
                filename TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                error TEXT,
                downloaded_at TEXT,
                UNIQUE(source_id, series_id, chapter_id, page_index)
            )
        """)

        self.conn.commit()

    def register_series(self, source_id: str, series_id: str, title: str) -> int:
        """Register a series in the database."""
        cursor = self.conn.cursor()
        created_at = datetime.utcnow().isoformat()

        cursor.execute(
            """
            INSERT OR IGNORE INTO series (source_id, series_id, title, created_at)
            VALUES (?, ?, ?, ?)
        """,
            (source_id, series_id, title, created_at),
        )

        self.conn.commit()

        cursor.execute(
            """
            SELECT id FROM series WHERE source_id = ? AND series_id = ?
        """,
            (source_id, series_id),
        )

        result = cursor.fetchone()
        return result[0] if result else -1

    def register_chapter(
        self, source_id: str, series_id: str, chapter_id: str, chapter_title: str, page_count: Optional[int] = None
    ) -> int:
        """Register a chapter in the database."""
        cursor = self.conn.cursor()
        created_at = datetime.utcnow().isoformat()

        cursor.execute(
            """
            INSERT OR IGNORE INTO chapters
            (source_id, series_id, chapter_id, chapter_title, page_count, created_at, status)
            VALUES (?, ?, ?, ?, ?, ?, 'pending')
        """,
            (source_id, series_id, chapter_id, chapter_title, page_count, created_at),
        )

        self.conn.commit()

        cursor.execute(
            """
            SELECT id FROM chapters
            WHERE source_id = ? AND series_id = ? AND chapter_id = ?
        """,
            (source_id, series_id, chapter_id),
        )

        result = cursor.fetchone()
        return result[0] if result else -1

    def mark_page_downloaded(
        self, source_id: str, series_id: str, chapter_id: str, page_index: int, filename: str
    ) -> None:
        """Mark a page as successfully downloaded."""
        cursor = self.conn.cursor()
        downloaded_at = datetime.utcnow().isoformat()

        cursor.execute(
            """
            INSERT OR REPLACE INTO pages
            (source_id, series_id, chapter_id, page_index, filename, status, downloaded_at)
            VALUES (?, ?, ?, ?, ?, 'downloaded', ?)
        """,
            (source_id, series_id, chapter_id, page_index, filename, downloaded_at),
        )

        self.conn.commit()

    def mark_page_failed(
        self, source_id: str, series_id: str, chapter_id: str, page_index: int, error: str
    ) -> None:
        """Mark a page download as failed."""
        cursor = self.conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO pages
            (source_id, series_id, chapter_id, page_index, status, error)
            VALUES (?, ?, ?, ?, 'failed', ?)
        """,
            (source_id, series_id, chapter_id, page_index, error),
        )

        self.conn.commit()

    def get_chapter_status(self, source_id: str, series_id: str, chapter_id: str) -> Optional[dict]:
        """Get status of a chapter."""
        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT * FROM chapters
            WHERE source_id = ? AND series_id = ? AND chapter_id = ?
        """,
            (source_id, series_id, chapter_id),
        )

        result = cursor.fetchone()
        return dict(result) if result else None

    def close(self):
        """Close database connection."""
        self.conn.close()

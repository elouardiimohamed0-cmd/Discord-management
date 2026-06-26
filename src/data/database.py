from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from src.core.logging import get_logger

logger = get_logger(__name__)


class Database:
    def __init__(self, path: Path, schema_path: Path | None = None):
        self.path = path
        self.schema_path = schema_path or Path(__file__).with_name("schema.sql")
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        schema = self.schema_path.read_text(encoding="utf-8")
        with self.connect() as conn:
            conn.executescript(schema)
        logger.info("SQLite database initialized at %s", self.path)

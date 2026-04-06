from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .models import RemoteFile


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True, slots=True)
class StoredFile:
    id: int
    order_key: str
    bundle_name: str
    source_id: str
    item_machine_name: str
    item_name: str
    platform: str
    label: str
    filename: str
    md5: str | None
    relative_path: str
    status: str
    last_error: str | None


class StateStore:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(db_path)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._create_schema()

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "StateStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _create_schema(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS orders (
                order_key TEXT PRIMARY KEY,
                bundle_name TEXT NOT NULL,
                synced_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_key TEXT NOT NULL,
                bundle_name TEXT NOT NULL,
                source_id TEXT NOT NULL UNIQUE,
                item_machine_name TEXT NOT NULL,
                item_name TEXT NOT NULL,
                platform TEXT NOT NULL,
                label TEXT NOT NULL,
                filename TEXT NOT NULL,
                md5 TEXT,
                relative_path TEXT NOT NULL,
                status TEXT NOT NULL,
                last_error TEXT,
                synced_at TEXT NOT NULL,
                completed_at TEXT,
                FOREIGN KEY (order_key) REFERENCES orders(order_key) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_files_status ON files(status);
            CREATE INDEX IF NOT EXISTS idx_files_order_key ON files(order_key);
            """
        )
        self._connection.commit()

    def upsert_order_files(
        self, order_key: str, bundle_name: str, files: list[RemoteFile]
    ) -> tuple[int, int]:
        synced_at = _utc_now()
        cursor = self._connection.cursor()
        cursor.execute(
            """
            INSERT INTO orders(order_key, bundle_name, synced_at)
            VALUES(?, ?, ?)
            ON CONFLICT(order_key) DO UPDATE SET
                bundle_name = excluded.bundle_name,
                synced_at = excluded.synced_at
            """,
            (order_key, bundle_name, synced_at),
        )

        inserted = 0
        updated = 0
        active_source_ids = {remote_file.source_id for remote_file in files}
        for remote_file in files:
            row = cursor.execute(
                (
                    "SELECT id, md5, relative_path, filename, status "
                    "FROM files WHERE source_id = ?"
                ),
                (remote_file.source_id,),
            ).fetchone()

            if row is None:
                cursor.execute(
                    """
                    INSERT INTO files(
                        order_key, bundle_name, source_id, item_machine_name, item_name,
                        platform, label, filename, md5, relative_path, status,
                        last_error, synced_at, completed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', NULL, ?, NULL)
                    """,
                    (
                        order_key,
                        bundle_name,
                        remote_file.source_id,
                        remote_file.item_machine_name,
                        remote_file.item_name,
                        remote_file.platform,
                        remote_file.label,
                        remote_file.filename,
                        remote_file.md5,
                        remote_file.relative_path,
                        synced_at,
                    ),
                )
                inserted += 1
                continue

            metadata_changed = (
                row["md5"] != remote_file.md5
                or row["relative_path"] != remote_file.relative_path
                or row["filename"] != remote_file.filename
            )
            next_status = "pending" if metadata_changed else row["status"]
            next_completed_at = (
                None
                if metadata_changed
                else cursor.execute(
                    "SELECT completed_at FROM files WHERE id = ?",
                    (row["id"],),
                ).fetchone()[0]
            )

            cursor.execute(
                """
                UPDATE files
                SET order_key = ?,
                    bundle_name = ?,
                    item_machine_name = ?,
                    item_name = ?,
                    platform = ?,
                    label = ?,
                    filename = ?,
                    md5 = ?,
                    relative_path = ?,
                    status = ?,
                    last_error = CASE WHEN ? THEN NULL ELSE last_error END,
                    synced_at = ?,
                    completed_at = ?
                WHERE id = ?
                """,
                (
                    order_key,
                    bundle_name,
                    remote_file.item_machine_name,
                    remote_file.item_name,
                    remote_file.platform,
                    remote_file.label,
                    remote_file.filename,
                    remote_file.md5,
                    remote_file.relative_path,
                    next_status,
                    1 if metadata_changed else 0,
                    synced_at,
                    next_completed_at,
                    row["id"],
                ),
            )
            updated += 1

        placeholders = ", ".join("?" for _ in active_source_ids)
        if active_source_ids:
            cursor.execute(
                (
                    "DELETE FROM files WHERE order_key = ? "
                    f"AND source_id NOT IN ({placeholders})"
                ),
                [order_key, *active_source_ids],
            )
        else:
            cursor.execute("DELETE FROM files WHERE order_key = ?", (order_key,))

        self._connection.commit()
        return inserted, updated

    def reset_incomplete_downloads(self) -> int:
        cursor = self._connection.execute(
            (
                "UPDATE files SET status = 'pending', "
                "last_error = 'Download interrupted before completion.' "
                "WHERE status = 'downloading'"
            )
        )
        self._connection.commit()
        return cursor.rowcount

    def list_files(
        self, *, statuses: tuple[str, ...] | None = None
    ) -> list[StoredFile]:
        query = """
            SELECT id, order_key, bundle_name, source_id, item_machine_name, item_name,
                   platform, label, filename, md5, relative_path, status, last_error
            FROM files
        """
        params: list[str] = []
        if statuses:
            placeholders = ", ".join("?" for _ in statuses)
            query += f" WHERE status IN ({placeholders})"
            params.extend(statuses)
        query += " ORDER BY bundle_name, item_name, filename"
        rows = self._connection.execute(query, params).fetchall()
        return [
            StoredFile(
                id=row["id"],
                order_key=row["order_key"],
                bundle_name=row["bundle_name"],
                source_id=row["source_id"],
                item_machine_name=row["item_machine_name"],
                item_name=row["item_name"],
                platform=row["platform"],
                label=row["label"],
                filename=row["filename"],
                md5=row["md5"],
                relative_path=row["relative_path"],
                status=row["status"],
                last_error=row["last_error"],
            )
            for row in rows
        ]

    def mark_downloading(self, file_id: int) -> None:
        self._connection.execute(
            "UPDATE files SET status = 'downloading', last_error = NULL WHERE id = ?",
            (file_id,),
        )
        self._connection.commit()

    def mark_complete(self, file_id: int) -> None:
        self._connection.execute(
            (
                "UPDATE files SET status = 'complete', last_error = NULL, "
                "completed_at = ? WHERE id = ?"
            ),
            (_utc_now(), file_id),
        )
        self._connection.commit()

    def mark_failed(self, file_id: int, message: str) -> None:
        self._connection.execute(
            (
                "UPDATE files SET status = 'failed', last_error = ?, "
                "completed_at = NULL WHERE id = ?"
            ),
            (message, file_id),
        )
        self._connection.commit()

    def mark_pending(self, file_id: int, message: str | None = None) -> None:
        self._connection.execute(
            (
                "UPDATE files SET status = 'pending', last_error = ?, "
                "completed_at = NULL WHERE id = ?"
            ),
            (message, file_id),
        )
        self._connection.commit()

    def retry_failed(self) -> int:
        cursor = self._connection.execute(
            (
                "UPDATE files SET status = 'pending', last_error = NULL "
                "WHERE status = 'failed'"
            )
        )
        self._connection.commit()
        return cursor.rowcount

    def status_counts(self) -> dict[str, int]:
        rows = self._connection.execute(
            "SELECT status, COUNT(*) AS count FROM files GROUP BY status"
        ).fetchall()
        return {row["status"]: int(row["count"]) for row in rows}

    def order_count(self) -> int:
        row = self._connection.execute(
            "SELECT COUNT(*) AS count FROM orders"
        ).fetchone()
        return int(row["count"])

    def failed_files(self, *, limit: int = 10) -> list[StoredFile]:
        rows = self._connection.execute(
            """
            SELECT id, order_key, bundle_name, source_id, item_machine_name, item_name,
                   platform, label, filename, md5, relative_path, status, last_error
            FROM files
            WHERE status = 'failed'
            ORDER BY bundle_name, item_name, filename
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [
            StoredFile(
                id=row["id"],
                order_key=row["order_key"],
                bundle_name=row["bundle_name"],
                source_id=row["source_id"],
                item_machine_name=row["item_machine_name"],
                item_name=row["item_name"],
                platform=row["platform"],
                label=row["label"],
                filename=row["filename"],
                md5=row["md5"],
                relative_path=row["relative_path"],
                status=row["status"],
                last_error=row["last_error"],
            )
            for row in rows
        ]

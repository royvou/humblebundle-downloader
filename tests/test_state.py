from __future__ import annotations

from pathlib import Path

from humblebundle_downloader.models import RemoteFile
from humblebundle_downloader.state import StateStore


def test_upsert_preserves_complete_status_for_unchanged_file(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "hb.sqlite3")
    remote_file = RemoteFile(
        order_key="KEY123",
        bundle_name="Bundle",
        item_machine_name="machine",
        item_name="Item",
        platform="ebook",
        label="pdf",
        filename="file.pdf",
        md5="abc",
        url="https://example.test/file.pdf",
        source_id="KEY123|machine|ebook|pdf|file.pdf",
        relative_path="Bundle/Item/file.pdf",
    )

    inserted, updated = store.upsert_order_files("KEY123", "Bundle", [remote_file])
    assert inserted == 1
    assert updated == 0

    stored_file = store.list_files()[0]
    store.mark_complete(stored_file.id)

    inserted, updated = store.upsert_order_files("KEY123", "Bundle", [remote_file])
    assert inserted == 0
    assert updated == 1
    assert store.list_files()[0].status == "complete"

    store.close()


def test_upsert_removes_stale_files_for_order(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "hb.sqlite3")
    original = RemoteFile(
        order_key="KEY123",
        bundle_name="Bundle",
        item_machine_name="machine",
        item_name="Item",
        platform="ebook",
        label="pdf",
        filename="old.pdf",
        md5="abc",
        url="https://example.test/old.pdf",
        source_id="KEY123|machine|ebook|pdf|old.pdf",
        relative_path="Bundle/Item/old.pdf",
    )
    replacement = RemoteFile(
        order_key="KEY123",
        bundle_name="Bundle",
        item_machine_name="machine",
        item_name="Item",
        platform="ebook",
        label="epub",
        filename="new.epub",
        md5="def",
        url="https://example.test/new.epub",
        source_id="KEY123|machine|ebook|epub|new.epub",
        relative_path="Bundle/Item/new.epub",
    )

    store.upsert_order_files("KEY123", "Bundle", [original])
    store.upsert_order_files("KEY123", "Bundle", [replacement])

    files = store.list_files()
    assert len(files) == 1
    assert files[0].filename == "new.epub"

    store.close()


def test_reset_incomplete_downloads_returns_to_pending(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "hb.sqlite3")
    remote_file = RemoteFile(
        order_key="KEY123",
        bundle_name="Bundle",
        item_machine_name="machine",
        item_name="Item",
        platform="ebook",
        label="pdf",
        filename="file.pdf",
        md5="abc",
        url="https://example.test/file.pdf",
        source_id="KEY123|machine|ebook|pdf|file.pdf",
        relative_path="Bundle/Item/file.pdf",
    )

    store.upsert_order_files("KEY123", "Bundle", [remote_file])
    stored = store.list_files()[0]
    store.mark_downloading(stored.id)

    reset = store.reset_incomplete_downloads()

    assert reset == 1
    refreshed = store.list_files()[0]
    assert refreshed.status == "pending"
    assert refreshed.last_error == "Download interrupted before completion."

    store.close()

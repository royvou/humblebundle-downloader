from __future__ import annotations

from pathlib import Path

from humblebundle_downloader.downloader import apply_path_migrations
from humblebundle_downloader.models import RemoteFile
from humblebundle_downloader.state import PathMigration, StateStore


def test_apply_path_migrations_moves_file_and_restores_complete(tmp_path: Path) -> None:
    output_dir = tmp_path / "downloads"
    output_dir.mkdir()
    store = StateStore(tmp_path / "hb.sqlite3")
    remote_file = RemoteFile(
        order_key="KEY123",
        bundle_name="Bundle (2024)",
        item_machine_name="machine",
        item_name="Item",
        platform="ebook",
        label="pdf",
        filename="file.pdf",
        md5="abc",
        url="https://example.test/file.pdf",
        source_id="KEY123|machine|ebook|pdf|file.pdf",
        relative_path="Bundle (2024)/Item/file.pdf",
    )

    store.upsert_order_files(
        "KEY123",
        "Bundle",
        [
            RemoteFile(
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
        ],
    )
    stored = store.list_files()[0]
    store.mark_complete(stored.id)
    _, _, migrations = store.upsert_order_files(
        "KEY123", "Bundle (2024)", [remote_file]
    )

    old_path = output_dir / "Bundle/Item/file.pdf"
    old_path.parent.mkdir(parents=True, exist_ok=True)
    old_path.write_text("contents", encoding="utf-8")

    moved, skipped = apply_path_migrations(
        store=store,
        output_dir=output_dir,
        migrations=migrations,
    )

    assert moved == 1
    assert skipped == 0
    assert not old_path.exists()
    assert (output_dir / "Bundle (2024)/Item/file.pdf").exists()
    assert store.list_files()[0].status == "complete"

    store.close()


def test_apply_path_migrations_skips_existing_destination(tmp_path: Path) -> None:
    output_dir = tmp_path / "downloads"
    output_dir.mkdir()
    store = StateStore(tmp_path / "hb.sqlite3")

    source = output_dir / "Bundle/Item/file.pdf"
    destination = output_dir / "Bundle (2024)/Item/file.pdf"
    source.parent.mkdir(parents=True, exist_ok=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("source", encoding="utf-8")
    destination.write_text("destination", encoding="utf-8")

    moved, skipped = apply_path_migrations(
        store=store,
        output_dir=output_dir,
        migrations=[
            PathMigration(
                file_id=1,
                old_relative_path="Bundle/Item/file.pdf",
                new_relative_path="Bundle (2024)/Item/file.pdf",
                restore_complete=False,
            )
        ],
    )

    assert moved == 0
    assert skipped == 1
    assert source.read_text(encoding="utf-8") == "source"
    assert destination.read_text(encoding="utf-8") == "destination"

    store.close()

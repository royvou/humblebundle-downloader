from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from .humble_api import HumbleApiClient
from .models import RemoteFile, matches_filters, parse_order_payload
from .state import PathMigration, StateStore, StoredFile


def md5_for_file(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


async def sync_orders(
    *,
    client: HumbleApiClient,
    store: StateStore,
    order_keys: list[str],
    output_dir: Path,
) -> tuple[int, int, int, int, dict[str, str]]:
    payloads, errors = await client.fetch_orders(order_keys, concurrency=2)
    inserted = 0
    updated = 0
    migrated = 0
    skipped = 0
    for order_key, payload in payloads.items():
        bundle_name, remote_files = parse_order_payload(order_key, payload)
        order_inserted, order_updated, migrations = store.upsert_order_files(
            order_key, bundle_name, remote_files
        )
        inserted += order_inserted
        updated += order_updated
        order_migrated, order_skipped = apply_path_migrations(
            store=store,
            output_dir=output_dir,
            migrations=migrations,
        )
        migrated += order_migrated
        skipped += order_skipped
    return inserted, updated, migrated, skipped, errors


def apply_path_migrations(
    *,
    store: StateStore,
    output_dir: Path,
    migrations: list[PathMigration],
) -> tuple[int, int]:
    moved = 0
    skipped = 0
    for migration in migrations:
        source = output_dir / migration.old_relative_path
        destination = output_dir / migration.new_relative_path

        if not source.exists():
            continue
        if destination.exists():
            skipped += 1
            continue

        destination.parent.mkdir(parents=True, exist_ok=True)
        source.replace(destination)
        _remove_empty_parents(source.parent, output_dir)
        moved += 1

        if migration.restore_complete:
            store.mark_complete(migration.file_id)

    return moved, skipped


def _remove_empty_parents(path: Path, stop_at: Path) -> None:
    current = path
    stop_at = stop_at.resolve()
    while True:
        try:
            current_resolved = current.resolve()
        except OSError:
            break

        if current_resolved == stop_at:
            break

        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


async def _refresh_remote_files(
    client: HumbleApiClient, order_keys: list[str]
) -> dict[str, RemoteFile]:
    payloads, errors = await client.fetch_orders(order_keys, concurrency=2)
    if errors:
        sample = "; ".join(
            f"{key}: {message}" for key, message in sorted(errors.items())
        )
        raise RuntimeError(sample)

    remote_by_source: dict[str, RemoteFile] = {}
    for order_key, payload in payloads.items():
        _, remote_files = parse_order_payload(order_key, payload)
        for remote_file in remote_files:
            remote_by_source[remote_file.source_id] = remote_file
    return remote_by_source


async def download_pending(
    *,
    client: HumbleApiClient,
    store: StateStore,
    output_dir: Path,
    formats: tuple[str, ...],
    platforms: tuple[str, ...],
    concurrency: int,
) -> tuple[int, int]:
    output_dir.mkdir(parents=True, exist_ok=True)
    store.reset_incomplete_downloads()

    candidates = [
        file
        for file in store.list_files(statuses=("pending",))
        if matches_filters(
            filename=file.filename,
            platform=file.platform,
            formats=formats,
            platforms=platforms,
        )
    ]

    if not candidates:
        return 0, 0

    remote_by_source = await _refresh_remote_files(
        client, sorted({file.order_key for file in candidates})
    )

    semaphore = asyncio.Semaphore(concurrency)
    progress = Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        transient=False,
    )
    completed = 0
    failed = 0

    with progress:
        task_id = progress.add_task("Overall", total=len(candidates))

        async def download_one(file: StoredFile) -> None:
            nonlocal completed, failed
            remote_file = remote_by_source.get(file.source_id)
            if remote_file is None:
                store.mark_failed(
                    file.id, "File is no longer present in the synced order metadata."
                )
                failed += 1
                progress.advance(task_id)
                return

            destination = output_dir / file.relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)

            if destination.exists():
                if file.md5:
                    if await asyncio.to_thread(md5_for_file, destination) == file.md5:
                        store.mark_complete(file.id)
                        completed += 1
                        progress.advance(task_id)
                        return
                else:
                    store.mark_complete(file.id)
                    completed += 1
                    progress.advance(task_id)
                    return

            async with semaphore:
                store.mark_downloading(file.id)
                file_task_id = progress.add_task(file.filename, total=None)
                try:
                    await _download_to_path(
                        client, remote_file, destination, progress, file_task_id
                    )
                except Exception as exc:  # noqa: BLE001
                    store.mark_failed(file.id, str(exc))
                    failed += 1
                else:
                    store.mark_complete(file.id)
                    completed += 1
                finally:
                    progress.update(file_task_id, visible=False)
                    progress.advance(task_id)

        await asyncio.gather(*(download_one(file) for file in candidates))

    return completed, failed


async def _download_to_path(
    client: HumbleApiClient,
    remote_file: RemoteFile,
    destination: Path,
    progress: Progress,
    task_id: int,
) -> None:
    part_path = destination.with_name(f"{destination.name}.part")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if part_path.exists():
        part_path.unlink()

    async def attempt() -> None:
        async with client._client.stream("GET", remote_file.url) as response:  # noqa: SLF001
            if response.status_code != 200:
                raise RuntimeError(
                    f"Download failed with status {response.status_code}."
                )
            total = response.headers.get("content-length")
            progress.update(
                task_id, total=int(total) if total and total.isdigit() else None
            )
            with part_path.open("wb") as handle:
                async for chunk in response.aiter_bytes(1024 * 64):
                    handle.write(chunk)
                    progress.advance(task_id, len(chunk))

        if remote_file.md5:
            digest = await asyncio.to_thread(md5_for_file, part_path)
            if digest != remote_file.md5:
                raise RuntimeError("Downloaded file failed MD5 verification.")
        part_path.replace(destination)

    last_error: Exception | None = None
    for delay in (0, 1, 2):
        if delay:
            await asyncio.sleep(delay)
        try:
            progress.update(task_id, completed=0)
            await attempt()
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if part_path.exists():
                part_path.unlink()
    raise RuntimeError(str(last_error))


def verify_files(
    *,
    store: StateStore,
    output_dir: Path,
    formats: tuple[str, ...],
    platforms: tuple[str, ...],
) -> tuple[int, int]:
    checked = 0
    repaired = 0
    for file in store.list_files():
        if not matches_filters(
            filename=file.filename,
            platform=file.platform,
            formats=formats,
            platforms=platforms,
        ):
            continue

        checked += 1
        destination = output_dir / file.relative_path
        if not destination.exists():
            store.mark_pending(file.id, "Local file is missing.")
            repaired += 1
            continue

        if file.md5:
            digest = md5_for_file(destination)
            if digest != file.md5:
                store.mark_pending(file.id, "Local file failed MD5 verification.")
                repaired += 1
                continue

        store.mark_complete(file.id)

    return checked, repaired

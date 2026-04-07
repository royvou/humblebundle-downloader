from __future__ import annotations

import asyncio
import threading
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TypeVar

import typer
from rich.console import Console
from rich.table import Table

from .config import (
    DEFAULT_ENV_TEMPLATE,
    DEFAULT_KEYS_TEMPLATE,
    ConfigError,
    Settings,
    load_settings,
)
from .downloader import download_pending, sync_orders, verify_files
from .humble_api import AuthError, HumbleApiClient, HumbleApiError
from .models import extract_order_key, parse_keys_text
from .state import StateStore

app = typer.Typer(help="Download DRM-free Humble Bundle files from known order keys.")
auth_app = typer.Typer(help="Authentication checks.")
app.add_typer(auth_app, name="auth")

console = Console()
T = TypeVar("T")


def main() -> None:
    app()


def _run_async(
    async_fn: Callable[[], Awaitable[T]],
) -> T:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(async_fn())  # type: ignore[arg-type]

    result: T | None = None
    error: BaseException | None = None

    def runner() -> None:
        nonlocal result, error
        try:
            result = asyncio.run(async_fn())  # type: ignore[arg-type]
        except BaseException as exc:  # noqa: BLE001
            error = exc

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join()

    if error is not None:
        raise error
    return result  # type: ignore[return-value]


def _settings(*, require_session: bool) -> Settings:
    try:
        return load_settings(require_session=require_session)
    except ConfigError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _collect_order_keys(keys: list[str] | None, keys_file: Path | None) -> list[str]:
    resolved: list[str] = []
    for key in keys or []:
        extracted = extract_order_key(key)
        if not extracted:
            raise typer.BadParameter(f"Unsupported key value: {key}")
        resolved.append(extracted)

    if keys_file:
        if not keys_file.exists():
            raise typer.BadParameter(f"Keys file does not exist: {keys_file}")
        parsed_keys = parse_keys_text(keys_file.read_text(encoding="utf-8"))
        if not parsed_keys:
            raise typer.BadParameter(
                f"No valid order keys found in {keys_file}. "
                "Add one order key or downloads URL per line."
            )
        resolved.extend(parsed_keys)

    deduped: list[str] = []
    seen: set[str] = set()
    for key in resolved:
        if key not in seen:
            deduped.append(key)
            seen.add(key)
    return deduped


def _write_text_file(path: Path, contents: str, *, force: bool) -> str:
    if path.exists() and not force:
        return "exists"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")
    return "written"


@app.command()
def init(
    env_file: Path = typer.Option(
        Path(".env"), "--env-file", help="Path to the generated .env file."
    ),
    keys_file: Path = typer.Option(
        Path("keys.txt"), "--keys-file", help="Path to the generated sample keys file."
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite existing files."),
) -> None:
    """Create local starter files for configuration and order keys."""

    env_status = _write_text_file(env_file, DEFAULT_ENV_TEMPLATE, force=force)
    keys_status = _write_text_file(keys_file, DEFAULT_KEYS_TEMPLATE, force=force)

    table = Table(title="Initialized Files")
    table.add_column("File")
    table.add_column("Result")
    table.add_row(str(env_file), env_status)
    table.add_row(str(keys_file), keys_status)
    console.print(table)

    if env_status == "written":
        console.print(
            "Update HB_SESSION in the generated .env file before running auth test."
        )


@auth_app.command("test")
def auth_test() -> None:
    """Validate that HB_SESSION can access the Humble account library."""

    settings = _settings(require_session=True)

    async def run() -> None:
        async with HumbleApiClient(settings.session or "") as client:
            await client.test_auth()

    try:
        _run_async(run)
    except AuthError as exc:
        raise typer.Exit(code=_fail(str(exc))) from exc
    except HumbleApiError as exc:
        raise typer.Exit(code=_fail(str(exc))) from exc

    console.print("HB_SESSION is valid.")


@app.command()
def sync(
    input_path: Path | None = typer.Argument(
        None,
        help="Optional path to a text file containing order keys or downloads URLs.",
    ),
    key: list[str] = typer.Option(
        None, "--key", help="Order key or full downloads URL.", metavar="KEY"
    ),
    keys_file: Path | None = typer.Option(
        None, "--keys-file", help="Text file containing order keys or downloads URLs."
    ),
) -> None:
    """Sync order metadata into the local SQLite database."""

    if input_path and keys_file:
        raise typer.BadParameter(
            "Use either the positional input path or --keys-file, not both."
        )

    resolved_keys_file = keys_file or input_path

    order_keys = _collect_order_keys(key, resolved_keys_file)

    settings = _settings(require_session=True)

    async def run() -> tuple[list[str], int, int, dict[str, str]]:
        async with HumbleApiClient(settings.session or "") as client:
            await client.test_auth()
            resolved_order_keys = order_keys or await client.discover_order_keys()
            if not resolved_order_keys:
                raise HumbleApiError("No order keys were discovered for this account.")
            with StateStore(settings.db_path) as store:
                inserted, updated, migrated, skipped, errors = await sync_orders(
                    client=client,
                    store=store,
                    order_keys=resolved_order_keys,
                    output_dir=settings.output_dir,
                )
                return resolved_order_keys, inserted, updated, migrated, skipped, errors

    try:
        synced_order_keys, inserted, updated, migrated, skipped, errors = _run_async(
            run
        )
    except HumbleApiError as exc:
        raise typer.Exit(code=_fail(str(exc))) from exc

    console.print(f"Synced {len(synced_order_keys) - len(errors)} order(s).")
    console.print(
        f"Inserted {inserted} file record(s); updated {updated} existing record(s)."
    )
    if migrated:
        console.print(
            f"Migrated {migrated} existing file(s) to renamed bundle folders."
        )
    if skipped:
        console.print(
            "[yellow]"
            f"Skipped {skipped} path migration(s) because the destination "
            "already exists."
            "[/yellow]"
        )
    if not order_keys:
        console.print(
            f"Discovered {len(synced_order_keys)} order key(s) from the Humble account."
        )
    if errors:
        for order_key, message in sorted(errors.items()):
            console.print(f"[red]{order_key}[/red]: {message}")


@app.command()
def download(
    concurrency: int | None = typer.Option(
        None, "--concurrency", help="Override HB_CONCURRENCY for this run."
    ),
) -> None:
    """Download all pending files that match the configured filters."""

    settings = _settings(require_session=True)
    effective_concurrency = settings.concurrency if concurrency is None else concurrency
    if effective_concurrency < 1:
        raise typer.BadParameter("--concurrency must be at least 1.")

    async def run() -> tuple[int, int]:
        async with HumbleApiClient(settings.session or "") as client:
            await client.test_auth()
            with StateStore(settings.db_path) as store:
                return await download_pending(
                    client=client,
                    store=store,
                    output_dir=settings.output_dir,
                    formats=settings.formats,
                    platforms=settings.platforms,
                    concurrency=effective_concurrency,
                )

    try:
        completed, failed = _run_async(run)
    except HumbleApiError as exc:
        raise typer.Exit(code=_fail(str(exc))) from exc
    except RuntimeError as exc:
        raise typer.Exit(code=_fail(str(exc))) from exc

    console.print(f"Completed {completed} download(s).")
    if failed:
        console.print(f"[yellow]{failed} download(s) failed.[/yellow]")


@app.command()
def verify() -> None:
    """Verify local files and queue missing or invalid files for redownload."""

    settings = _settings(require_session=False)
    with StateStore(settings.db_path) as store:
        checked, repaired = verify_files(
            store=store,
            output_dir=settings.output_dir,
            formats=settings.formats,
            platforms=settings.platforms,
        )
    console.print(f"Checked {checked} file(s).")
    console.print(f"Queued {repaired} file(s) for redownload.")


@app.command()
def retry_failed() -> None:
    """Move failed downloads back to the pending queue."""

    settings = _settings(require_session=False)
    with StateStore(settings.db_path) as store:
        retried = store.retry_failed()
    console.print(f"Queued {retried} failed download(s) for retry.")


@app.command()
def status() -> None:
    """Show database counts and recent failures."""

    settings = _settings(require_session=False)
    with StateStore(settings.db_path) as store:
        counts = store.status_counts()
        table = Table(title="Humble Bundle Downloader")
        table.add_column("Metric")
        table.add_column("Value", justify="right")
        table.add_row("Orders", str(store.order_count()))
        for status_name in ("pending", "downloading", "complete", "failed"):
            table.add_row(status_name, str(counts.get(status_name, 0)))
        console.print(table)

        failures = store.failed_files(limit=10)
        if failures:
            failure_table = Table(title="Recent Failures")
            failure_table.add_column("File")
            failure_table.add_column("Error")
            for file in failures:
                failure_table.add_row(
                    file.relative_path, file.last_error or "unknown error"
                )
            console.print(failure_table)


def _fail(message: str) -> int:
    console.print(f"[red]{message}[/red]")
    return 1

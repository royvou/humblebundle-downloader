from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from humblebundle_downloader.cli import app


def test_sync_requires_keys(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HB_SESSION", "session")
    monkeypatch.setenv("HB_DB_PATH", str(tmp_path / "hb.sqlite3"))

    runner = CliRunner()
    with (
        patch("humblebundle_downloader.cli.HumbleApiClient.test_auth", new=AsyncMock()),
        patch(
            "humblebundle_downloader.cli.HumbleApiClient.discover_order_keys",
            new=AsyncMock(return_value=["ABC123"]),
        ),
        patch(
            "humblebundle_downloader.cli.sync_orders",
            new=AsyncMock(return_value=(0, 0, 0, 0, {})),
        ),
    ):
        result = runner.invoke(app, ["sync"])

    assert result.exit_code == 0
    assert "Discovered 1 order key(s)" in result.output


def test_sync_rejects_empty_keys_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HB_SESSION", "session")
    monkeypatch.setenv("HB_DB_PATH", str(tmp_path / "hb.sqlite3"))
    keys_file = tmp_path / "keys.txt"
    keys_file.write_text(
        "# Add one order key or full downloads URL per line.\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(app, ["sync", "--keys-file", str(keys_file)])

    assert result.exit_code != 0
    assert "No valid order keys found" in result.output


def test_status_runs_with_empty_database(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HB_DB_PATH", str(tmp_path / "hb.sqlite3"))

    runner = CliRunner()
    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert "Orders" in result.output
    assert "0" in result.output


def test_init_creates_env_and_keys_files(tmp_path: Path) -> None:
    runner = CliRunner()
    env_file = tmp_path / ".env"
    keys_file = tmp_path / "keys.txt"

    result = runner.invoke(
        app,
        [
            "init",
            "--env-file",
            str(env_file),
            "--keys-file",
            str(keys_file),
        ],
    )

    assert result.exit_code == 0
    assert env_file.exists()
    assert keys_file.exists()
    assert "HB_SESSION" in env_file.read_text(encoding="utf-8")
    assert "downloads?key" in keys_file.read_text(encoding="utf-8")


def test_init_does_not_overwrite_without_force(tmp_path: Path) -> None:
    runner = CliRunner()
    env_file = tmp_path / ".env"
    keys_file = tmp_path / "keys.txt"
    env_file.write_text("HB_SESSION=original\n", encoding="utf-8")
    keys_file.write_text("ABC123\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "init",
            "--env-file",
            str(env_file),
            "--keys-file",
            str(keys_file),
        ],
    )

    assert result.exit_code == 0
    assert env_file.read_text(encoding="utf-8") == "HB_SESSION=original\n"
    assert keys_file.read_text(encoding="utf-8") == "ABC123\n"
    assert "exists" in result.output


def test_sync_accepts_positional_keys_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HB_SESSION", "session")
    monkeypatch.setenv("HB_DB_PATH", str(tmp_path / "hb.sqlite3"))
    keys_file = tmp_path / "keys.txt"
    keys_file.write_text("ABC123\n", encoding="utf-8")

    runner = CliRunner()
    with (
        patch("humblebundle_downloader.cli.HumbleApiClient.test_auth", new=AsyncMock()),
        patch(
            "humblebundle_downloader.cli.sync_orders",
            new=AsyncMock(return_value=(0, 0, 0, 0, {})),
        ),
    ):
        result = runner.invoke(app, ["sync", str(keys_file)])

    assert result.exit_code == 0
    assert "Synced 1 order(s)." in result.output


def test_sync_uses_account_discovery_when_keys_are_omitted(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("HB_SESSION", "session")
    monkeypatch.setenv("HB_DB_PATH", str(tmp_path / "hb.sqlite3"))

    runner = CliRunner()
    with (
        patch("humblebundle_downloader.cli.HumbleApiClient.test_auth", new=AsyncMock()),
        patch(
            "humblebundle_downloader.cli.HumbleApiClient.discover_order_keys",
            new=AsyncMock(return_value=["ABC123", "XYZ789"]),
        ),
        patch(
            "humblebundle_downloader.cli.sync_orders",
            new=AsyncMock(return_value=(4, 0, 0, 0, {})),
        ),
    ):
        result = runner.invoke(app, ["sync"])

    assert result.exit_code == 0
    assert "Discovered 2 order key(s)" in result.output
    assert "Inserted 4 file record(s)" in result.output


def test_download_rejects_invalid_concurrency(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HB_SESSION", "session")
    monkeypatch.setenv("HB_DB_PATH", str(tmp_path / "hb.sqlite3"))

    runner = CliRunner()
    result = runner.invoke(app, ["download", "--concurrency", "0"])

    assert result.exit_code != 0
    assert "--concurrency must be at least 1" in result.output

# Development

This document covers the local workflow for working on Humble Bundle Downloader itself.

## Environment setup

Install the project plus the development dependency group:

```bash
uv sync --group dev
```

The project targets Python 3.12 or newer.

## Useful commands

Run the CLI locally:

```bash
uv run hb --help
```

Run the test suite:

```bash
uv run pytest
```

Run lint checks:

```bash
uv run ruff check src tests
```

## Project layout

| Path | Purpose |
| --- | --- |
| `src\humblebundle_downloader\cli.py` | Typer CLI entry point and command wiring |
| `src\humblebundle_downloader\humble_api.py` | Authenticated HTTP client for Humble endpoints |
| `src\humblebundle_downloader\downloader.py` | Sync, verification, download, and file migration logic |
| `src\humblebundle_downloader\state.py` | SQLite-backed state store |
| `src\humblebundle_downloader\models.py` | Payload parsing, filters, and path normalization |
| `tests\` | CLI, API, downloader, model, and state tests |

## Development notes

- Use `uv run ...` for commands so they execute inside the project environment
- The CLI loads configuration from `.env`, which makes local manual testing straightforward
- Tests use temporary paths and mocked network behavior, so they run quickly without touching a real Humble account

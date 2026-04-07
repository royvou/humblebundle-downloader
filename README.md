# Humble Bundle Downloader

Humble Bundle Downloader is a small Python CLI for syncing Humble order metadata and downloading DRM-free files with your Humble account session cookie.

## Highlights

- sync account orders into a local SQLite database
- download pending files with configurable concurrency
- verify existing files and requeue missing or invalid downloads
- retry failures without resyncing everything
- filter downloads by format and platform
- use automatic account discovery or a curated `keys.txt` file

## Requirements

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/)

## Quick start

```bash
uv sync
uv run hb init
uv run hb auth test
uv run hb sync
uv run hb download
```

Before running `auth test`, open `.env` and set `HB_SESSION` to your Humble `_simpleauth_sess` cookie value.

## Common commands

```bash
uv run hb sync
uv run hb sync --keys-file keys.txt
uv run hb download --concurrency 10
uv run hb verify
uv run hb retry-failed
uv run hb status
```

## Documentation

Detailed docs live in [`docs/`](docs/README.md):

- [Getting started](docs/getting-started.md)
- [Configuration](docs/configuration.md)
- [Command reference](docs/commands.md)
- [Working with `keys.txt`](docs/keys.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Development](docs/development.md)

## Contributing

Issues and pull requests are welcome.
# Getting started

This guide walks through the normal first-run workflow for Humble Bundle Downloader.

## What the tool does

The CLI signs in with your Humble account session cookie, syncs order metadata into a local SQLite database, and downloads matching DRM-free files into a local folder.

## Requirements

- Python 3.12 or newer
- [`uv`](https://docs.astral.sh/uv/) for dependency management and command execution

## Install dependencies

From the project root:

```bash
uv sync
```

## Create local starter files

Generate a starter `.env` file and a sample `keys.txt`:

```bash
uv run hb init
```

This creates:

- `.env` for local configuration
- `keys.txt` for optional manual order-key input

## Add your Humble session cookie

Open `.env` and set `HB_SESSION` to the value of your authenticated Humble `_simpleauth_sess` cookie.

```env
HB_SESSION="paste_your_cookie_value_here"
```

Use a fresh cookie from a browser session that can access your Humble library.

## Check authentication

Before syncing anything, confirm the cookie works:

```bash
uv run hb auth test
```

If authentication succeeds, the CLI can read your Humble account library.

## Sync your library metadata

To discover all available order keys from the account automatically:

```bash
uv run hb sync
```

To sync only specific orders instead, use `--key` or a `keys.txt` file:

```bash
uv run hb sync --key ABC123DEF456
uv run hb sync keys.txt
```

The sync step writes order and file metadata into the local SQLite database defined by `HB_DB_PATH`.

## Download pending files

Once sync has populated the database, download every pending file that matches your filters:

```bash
uv run hb download
```

You can temporarily override concurrency for a single run:

```bash
uv run hb download --concurrency 10
```

## Verify local files later

To check the current download folder and queue missing or invalid files for redownload:

```bash
uv run hb verify
uv run hb download
```

## Check progress and failures

```bash
uv run hb status
```

This shows file counts by state and the most recent download failures.

## Where files go

By default, files are stored under:

```text
downloads\<Bundle Name>\<Item Name>\<filename>
```

Bundle and item names are sanitized for the filesystem. When Humble renames a bundle, the next `sync` run can migrate existing files into the new folder name when it is safe to do so.

## Next reading

- [Configuration](configuration.md)
- [Command reference](commands.md)
- [Troubleshooting](troubleshooting.md)

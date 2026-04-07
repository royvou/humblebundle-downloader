# Command reference

This document describes the public CLI commands exposed by the `hb` entry point.

## Command summary

| Command | Purpose |
| --- | --- |
| `hb init` | Create starter `.env` and `keys.txt` files |
| `hb auth test` | Validate the configured Humble session cookie |
| `hb sync` | Sync Humble order metadata into the local database |
| `hb download` | Download pending files that match the current filters |
| `hb verify` | Re-check local files and queue missing or invalid files |
| `hb retry-failed` | Move failed downloads back to `pending` |
| `hb status` | Show counts and recent failures |

## `hb init`

Create starter local files:

```bash
uv run hb init
```

Useful options:

```bash
uv run hb init --env-file .env.local --keys-file my-keys.txt
uv run hb init --force
```

Notes:

- existing files are left untouched unless `--force` is used
- the generated `keys.txt` is optional; it is only needed when you want to sync a curated subset of orders

## `hb auth test`

Validate that `HB_SESSION` can access the Humble account library:

```bash
uv run hb auth test
```

Use this whenever you update your session cookie or suspect it has expired.

## `hb sync`

Sync order metadata into the SQLite database.

### Full-account discovery

If you do not provide any keys, the CLI discovers order keys from the authenticated account:

```bash
uv run hb sync
```

### Sync specific orders

You can pass one or more keys directly:

```bash
uv run hb sync --key ABC123DEF456 --key XYZ789GHI012
```

You can also point to a text file:

```bash
uv run hb sync keys.txt
uv run hb sync --keys-file keys.txt
```

### Important behavior

- `INPUT_PATH` and `--keys-file` are alternatives for the same file input; do not use both together
- `--key` can be repeated and combined with a keys file
- duplicate keys are deduplicated before sync
- sync updates existing file records and removes stale file records for the same order
- if a bundle folder name changes, sync can migrate existing local files to the new path when no conflict exists

## `hb download`

Download all pending files that match your configured filters:

```bash
uv run hb download
```

Override concurrency for one run:

```bash
uv run hb download --concurrency 10
```

Important behavior:

- the command resets interrupted `downloading` records back to `pending` before starting
- existing local files are reused when they already match the expected MD5
- each file is retried automatically before the CLI marks it as failed

## `hb verify`

Check local files and queue missing or invalid matches for redownload:

```bash
uv run hb verify
```

This is the normal recovery flow after moving files, partial cleanup, or suspected corruption:

```bash
uv run hb verify
uv run hb download
```

## `hb retry-failed`

Move failed downloads back into the pending queue:

```bash
uv run hb retry-failed
uv run hb download
```

Use this after a transient network issue or after fixing a temporary account-side problem.

## `hb status`

Show the current database summary:

```bash
uv run hb status
```

The output includes:

- total synced orders
- counts for `pending`, `downloading`, `complete`, and `failed`
- up to ten recent failures with the recorded error message

## Common workflows

### Sync and download your whole library

```bash
uv run hb auth test
uv run hb sync
uv run hb download
```

### Download only selected orders

```bash
uv run hb sync --keys-file keys.txt
uv run hb download
```

### Repair an existing library

```bash
uv run hb verify
uv run hb retry-failed
uv run hb download
```

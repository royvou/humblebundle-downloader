# Configuration

Humble Bundle Downloader reads configuration from environment variables, typically through a local `.env` file created by `hb init`.

## Default `.env`

```env
HB_SESSION="replace_with_your_simpleauth_sess_cookie"
HB_OUTPUT_DIR=downloads
HB_DB_PATH=.data/hb.sqlite3
HB_CONCURRENCY=6
HB_FORMATS=pdf,epub
HB_PLATFORMS=ebook,audio,windows
```

## Settings reference

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `HB_SESSION` | For `auth test`, `sync`, `download` | none | Humble `_simpleauth_sess` cookie value used for authenticated API requests |
| `HB_OUTPUT_DIR` | No | `downloads` | Root folder for downloaded files |
| `HB_DB_PATH` | No | `.data/hb.sqlite3` | SQLite database used to track synced orders and file states |
| `HB_CONCURRENCY` | No | `6` | Default number of concurrent downloads |
| `HB_FORMATS` | No | `pdf,epub` | Comma-separated file extensions to include |
| `HB_PLATFORMS` | No | `ebook,audio,windows` | Comma-separated Humble platform values to include |

## Filter behavior

`HB_FORMATS` and `HB_PLATFORMS` act as inclusive filters:

- Values are normalized to lowercase
- Format values should not include the leading dot
- An empty value means "do not filter on this field"

Examples:

```env
HB_FORMATS=pdf,epub,mobi
HB_PLATFORMS=ebook,audio
```

To disable filtering entirely:

```env
HB_FORMATS=
HB_PLATFORMS=
```

## What the filters affect

Filters are applied when the CLI chooses which files to act on:

- `hb download` only downloads pending files that match the current filters
- `hb verify` only checks files that match the current filters

Sync still records the full order metadata in the database, even for files that do not currently match your filters.

## Download layout

Each file is written under the configured output directory using:

```text
<bundle>\<item>\<filename>
```

The CLI also normalizes path components to keep them filesystem-safe:

- invalid path characters are replaced with `_`
- repeated whitespace is collapsed
- empty names fall back to `untitled`

If the same item exposes multiple downloads with the same filename, the CLI disambiguates them by appending platform and label data, then a numeric suffix if needed.

Example:

```text
downloads\Book Bundle (2025)\Title Name\book [ebook-pdf].pdf
downloads\Book Bundle (2025)\Title Name\book [ebook-epub].pdf
```

## Local state database

The SQLite database stores:

- synced order keys
- discovered downloadable files
- file status (`pending`, `downloading`, `complete`, `failed`)
- recent error messages

This lets you resync metadata, retry failures, and verify local files without losing progress between runs.

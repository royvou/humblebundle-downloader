# Humble Bundle Downloader

HTTP-only CLI for syncing and downloading DRM-free files from Humble Bundle order keys.

## Setup

1. Create a `.env` file:

```env
HB_SESSION="your_simpleauth_sess_value"
HB_OUTPUT_DIR=~/downloads/humblebundle
HB_DB_PATH=.data/hb.sqlite3
HB_CONCURRENCY=6
HB_FORMATS=pdf,epub
HB_PLATFORMS=ebook,audio,windows
```

2. Sync dependencies:

```bash
uv sync
```

3. Generate starter files:

```bash
uv run hb init
```

4. Validate the session:

```bash
uv run hb auth test
```

5. Sync your Humble account orders automatically:

```bash
uv run hb sync
```

Or sync specific orders manually:

```bash
uv run hb sync keys.txt
uv run hb sync --keys-file keys.txt
uv run hb sync --key ABC123 --key DEF456
```

## Usage

Sync all account orders using `HB_SESSION`:

```bash
uv run hb sync
```

Sync one or more specific order keys:

```bash
uv run hb sync --key ABC123 --key DEF456
uv run hb sync keys.txt
uv run hb sync --keys-file keys.txt
```

Download pending files:

```bash
uv run hb download
```

Verify completed files:

```bash
uv run hb verify
```

Inspect stored state:

```bash
uv run hb status
uv run hb retry-failed
```

`keys.txt` can contain bare order keys or `https://www.humblebundle.com/downloads?key=...` URLs.

`uv run hb init --force` will overwrite an existing `.env` or `keys.txt`.

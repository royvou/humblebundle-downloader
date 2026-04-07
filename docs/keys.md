# Working with `keys.txt`

`keys.txt` is an optional plain-text file used by `hb sync` when you want to sync a specific subset of orders instead of discovering everything from the account automatically.

## Supported entries

Each non-comment line can contain either:

1. A raw Humble order key
2. A full Humble downloads URL containing a key parameter

Examples:

```text
ABC123DEF456
https://www.humblebundle.com/downloads?key=ABC123DEF456
https://www.humblebundle.com/downloads?s=XYZ789GHI012
```

## File rules

- one entry per line
- blank lines are ignored
- lines starting with `#` are treated as comments
- duplicate keys are deduplicated before sync
- invalid lines are ignored while parsing; if nothing valid remains, `hb sync` exits with an error

## Example file

```text
# Books to sync this week
ABC123DEF456
https://www.humblebundle.com/downloads?key=XYZ789GHI012

# Another order from a saved URL
https://www.humblebundle.com/downloads?s=LMN345OPQ678
```

## Using the file with `hb sync`

Positional file argument:

```bash
uv run hb sync keys.txt
```

Explicit option:

```bash
uv run hb sync --keys-file keys.txt
```

Combining direct keys with a file:

```bash
uv run hb sync --key ABC123DEF456 --keys-file keys.txt
```

## Choosing between discovery and `keys.txt`

Use account discovery when you want the CLI to work against the full library:

```bash
uv run hb sync
```

Use `keys.txt` when you want tighter control, such as:

- downloading only a subset of purchases
- keeping a reusable list of bundle URLs from email receipts or bookmarks
- avoiding a full-account sync during focused testing

## Tip

`hb init` creates a sample `keys.txt` with commented examples, so you do not have to remember the expected format from scratch.

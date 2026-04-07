# Troubleshooting

This page covers the most common operational problems and what they usually mean.

## `HB_SESSION is invalid or expired`

Your Humble session cookie is missing, stale, or no longer authorized for the account.

What to do:

1. Get a fresh `_simpleauth_sess` cookie value from a logged-in browser session.
2. Update `HB_SESSION` in `.env`.
3. Run `uv run hb auth test`.

## `No order keys were discovered for this account`

`hb sync` only auto-discovers keys when you do not provide any manual keys. This message means the authenticated session did not return any usable Humble order keys.

Typical causes:

- wrong account
- expired session
- the account library is empty

## `No valid order keys found in <file>`

The provided keys file did not contain any usable order keys or download URLs.

Check that:

- each key is on its own line
- the file contains raw keys or Humble download URLs
- lines are not accidentally commented out with `#`

## Downloads are not starting for some files

Check your filters first. `hb download` only processes pending files that match the current `HB_FORMATS` and `HB_PLATFORMS` values.

Common fixes:

- clear the filters temporarily by setting `HB_FORMATS=` and `HB_PLATFORMS=`
- add the missing format or platform to the allowed list
- run `uv run hb status` to see whether files are pending or failed

## `hb verify` queued files for redownload

That is expected when the local file is missing or the MD5 checksum no longer matches the synced metadata.

Recovery flow:

```bash
uv run hb verify
uv run hb download
```

## Bundle folder names changed after sync

The CLI can migrate existing files when Humble changes a bundle name, but it skips a migration if the destination path already exists.

If you see skipped migrations:

- inspect both source and destination folders
- merge or rename the conflicting files manually if needed
- rerun `hb sync` or `hb verify` afterward

## A previous download was interrupted

The next `hb download` run resets any `downloading` records back to `pending` before starting. You do not need to clean those entries manually.

## I need a quick state overview

Use:

```bash
uv run hb status
```

This is the fastest way to see whether the database thinks files are pending, complete, or failed.

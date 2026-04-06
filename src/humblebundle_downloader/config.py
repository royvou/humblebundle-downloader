from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_ENV_TEMPLATE = """
HB_SESSION="replace_with_your_simpleauth_sess_cookie"
HB_OUTPUT_DIR=downloads
HB_DB_PATH=.data/hb.sqlite3
HB_CONCURRENCY=6
HB_FORMATS=pdf,epub
HB_PLATFORMS=ebook,audio,windows
""".lstrip()

DEFAULT_KEYS_TEMPLATE = """# Add one order key or full downloads URL per line.
# Examples:
# ABC123DEF456
# https://www.humblebundle.com/downloads?key=ABC123DEF456
"""


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True, slots=True)
class Settings:
    session: str | None
    output_dir: Path
    db_path: Path
    concurrency: int
    formats: tuple[str, ...]
    platforms: tuple[str, ...]


def _split_csv(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(part.strip().lower() for part in value.split(",") if part.strip())


def load_settings(*, require_session: bool) -> Settings:
    load_dotenv()

    session = os.getenv("HB_SESSION")
    if require_session and not session:
        raise ConfigError("HB_SESSION is required. Add it to your .env file.")

    raw_concurrency = os.getenv("HB_CONCURRENCY", "6")
    try:
        concurrency = int(raw_concurrency)
    except ValueError as exc:
        raise ConfigError("HB_CONCURRENCY must be an integer.") from exc

    if concurrency < 1:
        raise ConfigError("HB_CONCURRENCY must be at least 1.")

    return Settings(
        session=session,
        output_dir=Path(os.getenv("HB_OUTPUT_DIR", "downloads")),
        db_path=Path(os.getenv("HB_DB_PATH", ".data/hb.sqlite3")),
        concurrency=concurrency,
        formats=_split_csv(os.getenv("HB_FORMATS")),
        platforms=_split_csv(os.getenv("HB_PLATFORMS")),
    )

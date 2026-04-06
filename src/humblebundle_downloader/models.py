from __future__ import annotations

import re
from dataclasses import dataclass, replace
from pathlib import PurePosixPath
from urllib.parse import parse_qs, urlparse

_INVALID_PATH_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


@dataclass(frozen=True, slots=True)
class RemoteFile:
    order_key: str
    bundle_name: str
    item_machine_name: str
    item_name: str
    platform: str
    label: str
    filename: str
    md5: str | None
    url: str
    source_id: str
    relative_path: str


def sanitize_component(value: str) -> str:
    cleaned = _INVALID_PATH_CHARS.sub("_", value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().strip(".")
    return cleaned or "untitled"


def file_extension(filename: str) -> str:
    parts = filename.rsplit(".", 1)
    if len(parts) == 1:
        return ""
    return parts[1].lower()


def matches_filters(
    *,
    filename: str,
    platform: str,
    formats: tuple[str, ...],
    platforms: tuple[str, ...],
) -> bool:
    if formats and file_extension(filename) not in formats:
        return False
    if platforms and platform.lower() not in platforms:
        return False
    return True


def extract_order_key(value: str) -> str | None:
    candidate = value.strip()
    if not candidate or candidate.startswith("#"):
        return None

    parsed = urlparse(candidate)
    if parsed.scheme and parsed.netloc:
        query = parse_qs(parsed.query)
        for field in ("key", "s"):
            keys = query.get(field)
            if keys and keys[0].strip():
                return keys[0].strip()
        return None

    if re.fullmatch(r"[A-Za-z0-9_-]+", candidate):
        return candidate

    return None


def parse_keys_text(contents: str) -> list[str]:
    keys: list[str] = []
    for line in contents.splitlines():
        key = extract_order_key(line)
        if key:
            keys.append(key)
    return keys


def _ensure_list(value: object) -> list[object]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _source_id(
    order_key: str, item_machine_name: str, platform: str, label: str, filename: str
) -> str:
    return "|".join(
        [
            order_key,
            item_machine_name or sanitize_component(filename),
            platform.lower(),
            label.lower(),
            filename,
        ]
    )


def _with_unique_paths(files: list[RemoteFile]) -> list[RemoteFile]:
    groups: dict[tuple[str, str, str], list[RemoteFile]] = {}
    for remote_file in files:
        key = (remote_file.bundle_name, remote_file.item_name, remote_file.filename)
        groups.setdefault(key, []).append(remote_file)

    updated: list[RemoteFile] = []
    used_paths: set[str] = set()
    for remote_file in files:
        group = groups[
            (remote_file.bundle_name, remote_file.item_name, remote_file.filename)
        ]
        filename = remote_file.filename
        if len(group) > 1:
            stem, dot, suffix = filename.rpartition(".")
            stem = stem or filename
            label_fragment = sanitize_component(
                f"{remote_file.platform}-{remote_file.label}"
            )
            filename = f"{stem} [{label_fragment}]"
            if dot:
                filename = f"{filename}.{suffix}"

        candidate = str(
            PurePosixPath(
                sanitize_component(remote_file.bundle_name),
                sanitize_component(remote_file.item_name),
                filename,
            )
        )

        if candidate in used_paths:
            stem, dot, suffix = filename.rpartition(".")
            stem = stem or filename
            counter = 2
            while True:
                deduped = f"{stem} ({counter})"
                if dot:
                    deduped = f"{deduped}.{suffix}"
                candidate = str(
                    PurePosixPath(
                        sanitize_component(remote_file.bundle_name),
                        sanitize_component(remote_file.item_name),
                        deduped,
                    )
                )
                if candidate not in used_paths:
                    filename = deduped
                    break
                counter += 1

        used_paths.add(candidate)
        updated.append(replace(remote_file, filename=filename, relative_path=candidate))

    return updated


def parse_order_payload(
    order_key: str, payload: dict[str, object]
) -> tuple[str, list[RemoteFile]]:
    product = payload.get("product") or {}
    bundle_name = sanitize_component(
        str(getattr(product, "get", lambda *_: "")("human_name", "") or order_key)
    )

    files: list[RemoteFile] = []
    for subproduct in _ensure_list(payload.get("subproducts")):
        if not isinstance(subproduct, dict):
            continue

        item_name = sanitize_component(str(subproduct.get("human_name") or "untitled"))
        item_machine_name = str(subproduct.get("machine_name") or item_name)
        downloads = _ensure_list(subproduct.get("downloads"))
        for download in downloads:
            if not isinstance(download, dict):
                continue
            platform = str(download.get("platform") or "unknown").lower()
            structures = _ensure_list(download.get("download_struct"))
            for structure in structures:
                if not isinstance(structure, dict):
                    continue

                url_info = structure.get("url")
                if not isinstance(url_info, dict) or not url_info.get("web"):
                    continue

                url = str(url_info["web"])
                filename = PurePosixPath(urlparse(url).path).name
                if not filename:
                    continue

                label = str(
                    structure.get("name") or file_extension(filename) or "download"
                ).lower()
                md5 = structure.get("md5")
                normalized_md5 = str(md5).lower() if md5 else None
                source_id = _source_id(
                    order_key, item_machine_name, platform, label, filename
                )

                files.append(
                    RemoteFile(
                        order_key=order_key,
                        bundle_name=bundle_name,
                        item_machine_name=item_machine_name,
                        item_name=item_name,
                        platform=platform,
                        label=label,
                        filename=filename,
                        md5=normalized_md5,
                        url=url,
                        source_id=source_id,
                        relative_path="",
                    )
                )

    return bundle_name, _with_unique_paths(files)

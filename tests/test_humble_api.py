from __future__ import annotations

import pytest

from humblebundle_downloader.humble_api import HumbleApiError, _extract_gamekeys


def test_extract_gamekeys_reads_valid_entries() -> None:
    payload = [
        {"gamekey": "ABC123"},
        {"gamekey": "XYZ789"},
        {"ignored": "value"},
    ]

    assert _extract_gamekeys(payload) == ["ABC123", "XYZ789"]


def test_extract_gamekeys_rejects_unexpected_shape() -> None:
    with pytest.raises(HumbleApiError):
        _extract_gamekeys({"gamekey": "ABC123"})


def test_extract_gamekeys_allows_empty_list() -> None:
    assert _extract_gamekeys([]) == []

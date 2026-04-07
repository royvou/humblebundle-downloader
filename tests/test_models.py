from __future__ import annotations

from humblebundle_downloader.models import (
    extract_order_key,
    parse_keys_text,
    parse_order_payload,
    sanitize_component,
)


def test_extract_order_key_supports_urls_and_tokens() -> None:
    assert extract_order_key("ABC123") == "ABC123"
    assert (
        extract_order_key("https://www.humblebundle.com/downloads?key=XYZ789")
        == "XYZ789"
    )
    assert (
        extract_order_key("https://www.humblebundle.com/receipt?s=LMN456") == "LMN456"
    )
    assert extract_order_key("# comment") is None


def test_parse_keys_text_ignores_invalid_lines() -> None:
    keys = parse_keys_text("""
# comment
ABC123
invalid line here
https://www.humblebundle.com/downloads?key=XYZ789
""")

    assert keys == ["ABC123", "XYZ789"]


def test_parse_order_payload_extracts_files_and_dedupes_paths() -> None:
    payload = {
        "orderdate": "2024-07-15T00:00:00Z",
        "product": {"human_name": "Bundle: Name"},
        "subproducts": [
            {
                "human_name": "Book/One",
                "machine_name": "book_one",
                "downloads": [
                    {
                        "platform": "ebook",
                        "download_struct": [
                            {
                                "name": "PDF",
                                "md5": "ABCDEF",
                                "url": {
                                    "web": "https://cdn.example.test/files/book.pdf?sig=1"
                                },
                            },
                            {
                                "name": "EPUB",
                                "md5": "123456",
                                "url": {
                                    "web": "https://cdn.example.test/files/book.pdf?sig=2"
                                },
                            },
                        ],
                    }
                ],
            }
        ],
    }

    bundle_name, files = parse_order_payload("KEY123", payload)

    assert bundle_name == "Bundle_ Name (2024)"
    assert len(files) == 2
    assert files[0].relative_path != files[1].relative_path
    assert files[0].md5 == "abcdef"


def test_parse_order_payload_falls_back_when_no_year_exists() -> None:
    payload = {
        "product": {"human_name": "Bundle Name"},
        "subproducts": [],
    }

    bundle_name, files = parse_order_payload("KEY123", payload)

    assert bundle_name == "Bundle Name"
    assert files == []


def test_sanitize_component_trims_windows_unsafe_characters() -> None:
    assert sanitize_component("  Bad:<Name>?*  ") == "Bad__Name___"

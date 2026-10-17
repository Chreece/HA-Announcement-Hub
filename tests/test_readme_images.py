"""README image links must render outside the GitHub repository page.

HACS embeds this README at a different base URL, so repository-relative image
sources break there even when the assets exist in the repo.
"""

from __future__ import annotations

import re
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
OWN_RAW_ROOT = (
    "https://raw.githubusercontent.com/"
    "Chreece/HA-Announcement-Hub/main/"
)


def _image_sources() -> list[str]:
    html_images = re.findall(
        r'<img\b[^>]*\bsrc=["\']([^"\']+)["\']',
        README,
        flags=re.IGNORECASE,
    )
    markdown_images = re.findall(
        r'!\[[^\]]*\]\(([^\s)]+)',
        README,
    )
    return html_images + markdown_images


def test_all_readme_images_have_absolute_https_sources() -> None:
    images = _image_sources()
    assert len(images) >= 6  # banner, status, HACS and Ko-fi badges
    assert all(src.startswith("https://") for src in images), images
    assert not any(src.startswith(("./", "../", ".github/")) for src in images)


def test_banner_source_is_owned_raw_url_and_svg_exists() -> None:
    banner_url = OWN_RAW_ROOT + ".github/assets/announcement-hub-banner.svg"
    assert banner_url in _image_sources()
    for image_url in _image_sources():
        if not image_url.startswith(OWN_RAW_ROOT):
            continue
        relative_path = image_url.removeprefix(OWN_RAW_ROOT)
        path = ROOT / relative_path
        assert path.is_file(), f"Broken README asset: {image_url}"
        if path.suffix.lower() == ".svg":
            parsed = ElementTree.parse(path)
            assert parsed.getroot().tag.endswith("svg")

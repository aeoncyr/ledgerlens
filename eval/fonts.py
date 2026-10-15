"""Download handwriting-style fonts (all SIL Open Font License) from Google Fonts into a local cache."""

from __future__ import annotations

import re
import urllib.request
from pathlib import Path

CACHE = Path(__file__).parent / ".cache" / "fonts"

FAMILIES = (
    "Caveat",
    "Kalam",
    "Patrick Hand",
    "Gochi Hand",
    "Shadows Into Light Two",
    "Nanum Pen Script",
    "Indie Flower",
    "Just Another Hand",
)

# An old user agent makes the Google Fonts CSS API return plain TrueType URLs.
_UA = {"User-Agent": "Mozilla/4.0"}


def font_paths() -> list[Path]:
    """Return a local path for every family, downloading any that are missing."""
    CACHE.mkdir(parents=True, exist_ok=True)
    paths = []
    for family in FAMILIES:
        path = CACHE / f"{family.replace(' ', '')}.ttf"
        if not path.exists():
            css_url = f"https://fonts.googleapis.com/css2?family={family.replace(' ', '+')}"
            request = urllib.request.Request(css_url, headers=_UA)
            css = urllib.request.urlopen(request, timeout=30).read().decode()
            ttf_url = re.search(r"url\((https://[^)]+\.ttf)\)", css).group(1)
            path.write_bytes(urllib.request.urlopen(ttf_url, timeout=30).read())
        paths.append(path)
    return paths

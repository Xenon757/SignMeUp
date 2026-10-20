"""Find ASL Signbank entries for signed words.

ASL Signbank (https://aslsignbank.com, CC BY-NC-SA 4.0) has a reference video
for thousands of ASL signs. Its glosses are uppercase English words, with
lowercase or digit suffixes marking variants of the same sign: CATf and CATg
are two ways to sign CAT, WALK3 is one way to sign WALK.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import urllib.request
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

GLOSS_FILE = Path(__file__).resolve().parent / "data" / "signbank_glosses.json"
SITE = "https://aslsignbank.com"
USER_AGENT = "SignMeUp (+https://github.com/Xenon757/SignMeUp)"

log = logging.getLogger(__name__)

# Trailing variant marker: "CATf" -> "CAT", "WALK3" -> "WALK".
_VARIANT_SUFFIX = re.compile(r"[a-z0-9]+$")


def gloss_root(gloss: str) -> str:
    """The sign a gloss is a variant of, e.g. 'RUNasym' -> 'RUN'."""
    return _VARIANT_SUFFIX.sub("", gloss) or gloss


class GlossIndex:
    """Maps an English base word to the Signbank entries that sign it."""

    def __init__(self, glosses: Dict[str, int]):
        self._exact: Dict[str, int] = dict(glosses)
        self._by_root: Dict[str, List[Tuple[str, int]]] = {}
        for gloss, entry_id in sorted(glosses.items()):
            self._by_root.setdefault(gloss_root(gloss), []).append((gloss, entry_id))

    @classmethod
    def load(cls, path: Path = GLOSS_FILE) -> "GlossIndex":
        return cls(json.loads(path.read_text(encoding="utf-8"))["glosses"])

    def candidates(self, word: str) -> List[Tuple[str, int]]:
        """Entries for a word, best first: an exact gloss, then its variants.

        Multi-word glosses use hyphens ("ice cream" -> ICE-CREAM). Words with no
        gloss return [] rather than a loosely related sign.
        """
        key = word.strip().upper().replace(" ", "-")
        if not key:
            return []
        found: List[Tuple[str, int]] = []
        if key in self._exact:
            found.append((key, self._exact[key]))
        found.extend(c for c in self._by_root.get(key, []) if c[0] != key)
        return found


def entry_page_url(entry_id: int) -> str:
    return f"{SITE}/dictionary/gloss/{entry_id}.html"


# The entry page's player: <video id='videoplayer' src="/dictionary/protected_media/glossvideo/...mp4">
_VIDEO_SRC = re.compile(r'src="(/dictionary/protected_media/glossvideo/[^"]+\.mp4)"')


def video_url_from_page(html: str) -> Optional[str]:
    """The entry's video URL, or None if the entry has no video yet."""
    match = _VIDEO_SRC.search(html)
    return SITE + match.group(1) if match else None


def _fetch(url: str, timeout: float = 5.0) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


class VideoResolver:
    """Finds the video for a Signbank entry and remembers it.

    Video file names can't be derived from the gloss list (CATf's video is
    CAT-1037.mp4) and some entries have no video, so each entry page is read
    the first time that sign is needed. Results, including "no video", are
    cached in memory and in a JSON file so each page is fetched only once.
    Network errors are not cached, so the entry is retried on a later request.
    """

    def __init__(self, cache_file: Optional[Path] = None, fetch: Callable[[str], str] = _fetch):
        self._cache_file = cache_file
        self._fetch = fetch
        self._lock = threading.Lock()
        self._cache: Dict[str, Optional[str]] = {}
        if cache_file and cache_file.exists():
            try:
                self._cache = json.loads(cache_file.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                log.warning("Ignoring unreadable Signbank cache %s", cache_file)

    def is_cached(self, entry_id: int) -> bool:
        return str(entry_id) in self._cache

    def video_url(self, entry_id: int) -> Optional[str]:
        key = str(entry_id)
        if key in self._cache:
            return self._cache[key]
        try:
            url = video_url_from_page(self._fetch(entry_page_url(entry_id)))
        except Exception as exc:  # network errors, timeouts, HTTP errors
            log.warning("Could not read Signbank entry %s: %s", entry_id, exc)
            return None
        with self._lock:
            self._cache[key] = url
            self._save()
        return url

    def _save(self) -> None:
        if not self._cache_file:
            return
        try:
            self._cache_file.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._cache_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._cache, sort_keys=True), encoding="utf-8")
            tmp.replace(self._cache_file)
        except OSError as exc:
            log.warning("Could not save Signbank cache: %s", exc)

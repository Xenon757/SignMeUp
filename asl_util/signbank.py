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
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Sequence, Tuple

from .translate import Sign

if TYPE_CHECKING:
    from .poses import PoseStore

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


LETTER_IMAGE = "/static/img/fingerspelling/{}.svg"


class SignMedia:
    """Picks what to show for each sign: a Signbank video or a letter image.

    Fingerspelled letters use the bundled public-domain handshape images.
    Other signs use the first Signbank variant that has a video; signs with
    no match get None, and the page shows the gloss as text instead.
    With a PoseStore, video signs also get a 2D pose animation ("pose").
    """

    def __init__(
        self,
        index: GlossIndex,
        resolver: VideoResolver,
        poses: Optional["PoseStore"] = None,
        max_variants: int = 3,
        workers: int = 4,
    ):
        self._index = index
        self._resolver = resolver
        self._poses = poses
        self._max_variants = max_variants
        self._workers = workers

    def for_sign(self, sign: Sign) -> Optional[dict]:
        if sign.kind == "fingerspell":
            letter = sign.gloss.lower()
            if len(letter) == 1 and "a" <= letter <= "z":
                return {"type": "image", "url": LETTER_IMAGE.format(letter), "source": "Wikimedia Commons (public domain)"}
            return None
        return self._video_for(sign.gloss)

    def for_signs(self, signs: Sequence[Sign]) -> List[Optional[dict]]:
        """Media for each sign. Words not seen before are looked up a few at a time."""
        words = {s.gloss for s in signs if s.kind != "fingerspell"}
        with ThreadPoolExecutor(max_workers=self._workers) as pool:
            videos = dict(zip(words, pool.map(self._video_for, words)))
        return [self.for_sign(s) if s.kind == "fingerspell" else videos[s.gloss] for s in signs]

    def _video_for(self, word: str) -> Optional[dict]:
        for gloss, entry_id in self._index.candidates(word)[: self._max_variants]:
            url = self._resolver.video_url(entry_id)
            if url:
                media = {
                    "type": "video",
                    "url": url,
                    "gloss": gloss,
                    "page": entry_page_url(entry_id),
                    "source": "ASL Signbank (CC BY-NC-SA 4.0)",
                }
                if self._poses and self._poses.ensure(entry_id, gloss, url):
                    media["pose"] = f"/poses/{entry_id}.json"
                return media
        return None

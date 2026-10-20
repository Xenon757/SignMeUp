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
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Sequence, Tuple

from .translate import Sign

from .poses import CLIP_VERSION

if TYPE_CHECKING:
    from .poses import PoseStore

GLOSS_FILE = Path(__file__).resolve().parent / "data" / "signbank_glosses.json"
CHOICES_FILE = Path(__file__).resolve().parent / "data" / "sign_choices.json"
SITE = "https://aslsignbank.com"
USER_AGENT = "SignMeUp (+https://github.com/Xenon757/SignMeUp)"

log = logging.getLogger(__name__)

# Trailing variant marker: "CATf" -> "CAT", "WALK3" -> "WALK".
_VARIANT_SUFFIX = re.compile(r"[a-z0-9]+$")


def gloss_root(gloss: str) -> str:
    """The sign a gloss is a variant of, e.g. 'RUNasym' -> 'RUN'."""
    return _VARIANT_SUFFIX.sub("", gloss) or gloss


def _common_prefix(a: str, b: str) -> int:
    n = 0
    while n < min(len(a), len(b)) and a[n] == b[n]:
        n += 1
    return n


def same_word_family(word: str, gloss: str) -> bool:
    """True if one part of the gloss's name is the word or shares its stem.

    "limitation"/LIMIT, "explain"/EXPLANATION, "phone"/MOBILE-PHONE: yes.
    "ever"/NEVER, "national"/NORMAL: no. Parts are split on "-" and "_", and
    a leading "~" (Signbank's mark for some entries) is ignored.
    """
    word = word.lower()
    for part in re.split(r"[-_]", gloss_root(gloss).lstrip("~").lower()):
        if not part:
            continue
        shared = _common_prefix(part, word)
        if part == word or (shared >= 4 and shared >= 0.6 * min(len(part), len(word))):
            return True
    return False


class GlossIndex:
    """Maps an English base word to the Signbank entries that sign it.

    Candidates are tried best first:
      1. a gloss named after the word, then its variants (CAT, then CATf, CAT8);
      2. a reviewed choice for common words whose sign has another name
         ("you" -> IX, "already" -> FINISH; see data/sign_choices.json);
      3. an entry that lists the word as a translation and whose name is from
         the same word family ("limitation" -> LIMIT, "phone" -> MOBILE-PHONE),
         most specific entries (fewest translations) first.
    Translations alone are not trusted: they also link loosely related signs
    ("ever" is listed under NEVER), so a word with none of the above gets no sign.
    """

    def __init__(
        self,
        glosses: Dict[str, int],
        translations: Optional[Dict[str, List[str]]] = None,
        choices: Optional[Dict[str, str]] = None,
    ):
        self._exact: Dict[str, int] = dict(glosses)
        self._by_root: Dict[str, List[Tuple[str, int]]] = {}
        for gloss, entry_id in sorted(glosses.items()):
            self._by_root.setdefault(gloss_root(gloss), []).append((gloss, entry_id))
        self._translations = translations or {}
        self._by_translation: Dict[str, List[str]] = {}
        for gloss, words in sorted(self._translations.items()):
            for w in words:
                self._by_translation.setdefault(w, []).append(gloss)
        self._choices = {w.lower(): g for w, g in (choices or {}).items()}

    @classmethod
    def load(cls, path: Path = GLOSS_FILE, choices_path: Path = CHOICES_FILE) -> "GlossIndex":
        data = json.loads(path.read_text(encoding="utf-8"))
        choices = json.loads(choices_path.read_text(encoding="utf-8"))["choices"] if choices_path.exists() else {}
        return cls(data["glosses"], data.get("translations"), choices)

    def _named(self, key: str) -> List[Tuple[str, int]]:
        found: List[Tuple[str, int]] = []
        if key in self._exact:
            found.append((key, self._exact[key]))
        found.extend(c for c in self._by_root.get(key, []) if c[0] != key)
        return found

    def translations(self, gloss: str) -> List[str]:
        return self._translations.get(gloss, [])

    def candidates(self, word: str) -> List[Tuple[str, int]]:
        """Entries for a word, best first. Multi-word glosses use hyphens ("ice cream" -> ICE-CREAM)."""
        word = word.strip().lower()
        if not word:
            return []
        found = self._named(word.upper().replace(" ", "-"))
        if word in self._choices:
            found += [c for c in self._named(self._choices[word]) if c not in found]
        family = [g for g in self._by_translation.get(word, []) if same_word_family(word, g)]
        family.sort(key=lambda g: (len(self.translations(g)), g))
        found += [(g, self._exact[g]) for g in family if g in self._exact and (g, self._exact[g]) not in found]
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
    """Picks what to show for each sign: a Signbank video or fingerspelling.

    Fingerspelled letters use the bundled public-domain handshape images.
    Other signs use the first Signbank candidate that has a video (with a
    PoseStore, the first one whose video also makes a 2D animation, "pose").
    Words with no video are fingerspelled, as ASL does for words without a
    sign; numbers are not, since ASL signs them with number handshapes.
    """

    def __init__(
        self,
        index: GlossIndex,
        resolver: VideoResolver,
        poses: Optional["PoseStore"] = None,
        max_variants: int = 4,
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

    def for_signs(
        self, signs: Sequence[Sign], on_progress: Optional[Callable[[int, int], None]] = None
    ) -> List[Optional[dict]]:
        """Media for each sign. Words not seen before are looked up a few at a time.

        `on_progress(done, total)` is called as each distinct word is finished.
        """
        words = sorted({s.gloss for s in signs if s.kind != "fingerspell"})
        videos: Dict[str, Optional[dict]] = {}
        with ThreadPoolExecutor(max_workers=self._workers) as pool:
            futures = {pool.submit(self._video_for, w): w for w in words}
            for done, future in enumerate(as_completed(futures), start=1):
                videos[futures[future]] = future.result()
                if on_progress:
                    on_progress(done, len(words))
        return [
            self.for_sign(s) if s.kind == "fingerspell" else videos[s.gloss] or self._spelling_for(s)
            for s in signs
        ]

    @staticmethod
    def _spelling_for(sign: Sign) -> Optional[dict]:
        """Fingerspell a word that has no sign video."""
        if sign.kind == "number" or not sign.gloss.isalpha() or not sign.gloss.isascii():
            return None
        letters = sign.gloss.lower()
        return {
            "type": "spell",
            "letters": letters,
            "images": [LETTER_IMAGE.format(ch) for ch in letters],
            "source": "Wikimedia Commons (public domain)",
        }

    def _video_for(self, word: str) -> Optional[dict]:
        first_video: Optional[dict] = None
        for gloss, entry_id in self._index.candidates(word)[: self._max_variants]:
            url = self._resolver.video_url(entry_id)
            if not url:
                continue
            media = {
                "type": "video",
                "url": url,
                "gloss": gloss,
                "page": entry_page_url(entry_id),
                "source": "ASL Signbank (CC BY-NC-SA 4.0)",
            }
            if not self._poses:
                return media
            if self._poses.ensure(entry_id, gloss, url):
                # The version in the URL makes browsers fetch remade animations instead of old cached ones.
                media["pose"] = f"/poses/{entry_id}.json?v={CLIP_VERSION}"
                return media
            first_video = first_video or media  # keep looking for a variant that animates
        return first_video

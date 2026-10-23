"""Caption lines sent by the browser extension -> segments to sign.

The extension reads a YouTube video's own captions and sends them a chunk at a time, starting
where the viewer is, so nothing has to be transcribed and a long video starts signing at once.
Each caption line is signed as a unit, the way it's shown: auto-generated captions have no
punctuation, so sentences can't be found reliably.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import List, Optional

from .pipeline import timed_words
from .transcribe import Segment, SpokenWord

MAX_LINES = 400
MAX_LINE_CHARS = 1000
MAX_SECONDS = 24 * 3600

# Sound descriptions such as [Music] or [Applause], which aren't speech.
SOUND_NOTE = re.compile(r"\[[^\]]*\]")


class CaptionError(ValueError):
    """The request's captions aren't in the expected shape; the message says what's wrong."""


def _time(value, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise CaptionError(f"{what} must be a number of seconds.")
    if not 0 <= value <= MAX_SECONDS:
        raise CaptionError(f"{what} is out of range.")
    return float(value)


def _words(raw, start: float, end: float, text: str) -> List[SpokenWord]:
    """The line's own word timings if sent (auto-generated captions have them), else spread evenly."""
    if not raw:
        return timed_words(start, end, text)
    if not isinstance(raw, list) or len(raw) > 200:
        raise CaptionError("A line's words must be a list of {start, text}.")
    words = []
    for i, word in enumerate(raw):
        if not isinstance(word, dict) or not isinstance(word.get("text"), str):
            raise CaptionError("A line's words must be a list of {start, text}.")
        at = _time(word.get("start"), "A word's start")
        after = raw[i + 1].get("start") if i + 1 < len(raw) and isinstance(raw[i + 1], dict) else end
        words.append(SpokenWord(at, max(at, _time(after, "A word's start")), word["text"].strip()))
    return [w for w in words if w.text and not SOUND_NOTE.fullmatch(w.text)]


def parse_lines(data) -> List[Segment]:
    """Check a request's caption lines and turn them into segments, one per line with speech."""
    lines = data.get("lines") if isinstance(data, dict) else None
    if not isinstance(lines, list) or not lines:
        raise CaptionError("Send the captions as {\"lines\": [{\"start\", \"end\", \"text\"}, ...]}.")
    if len(lines) > MAX_LINES:
        raise CaptionError(f"Send at most {MAX_LINES} caption lines at a time.")
    segments = []
    for line in lines:
        if not isinstance(line, dict) or not isinstance(line.get("text"), str):
            raise CaptionError("Each caption line needs a start, an end and its text.")
        if len(line["text"]) > MAX_LINE_CHARS:
            raise CaptionError(f"Caption lines can be at most {MAX_LINE_CHARS} characters.")
        start, end = _time(line.get("start"), "A line's start"), _time(line.get("end"), "A line's end")
        if end < start:
            raise CaptionError("A caption line can't end before it starts.")
        text = " ".join(SOUND_NOTE.sub(" ", line["text"]).split())
        if not text:
            continue  # only a sound description
        segments.append(Segment(start, end, text, tuple(_words(line.get("words"), start, end, text))))
    return segments


def captions_key(segments: List[Segment]) -> str:
    """A name for these exact captions, so the same chunk is only translated once."""
    data = [[s.start, s.end, s.text, [[w.start, w.text] for w in s.words]] for s in segments]
    return hashlib.sha256(json.dumps(data).encode("utf-8")).hexdigest()


class CaptionTranscriber:
    """Hands over caption segments instead of listening to a file."""

    def __init__(self, segments: List[Segment]):
        self._segments = segments

    def transcribe(self, media_path: Optional[str | Path] = None) -> List[Segment]:
        return self._segments

"""Video -> timestamped ASL signs."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import bisect
from typing import List, Optional, Protocol, Sequence, Tuple

from .transcribe import Segment, SpokenWord
from .translate import Sign, gloss_string


class Transcriber(Protocol):
    def transcribe(self, media_path: str | Path) -> List[Segment]: ...


class Glosser(Protocol):
    def to_signs(self, text: str) -> List[Sign]: ...


class MediaFinder(Protocol):
    def for_signs(self, signs: List[Sign]) -> List[Optional[dict]]: ...


def word_positions(text: str, words: Sequence[SpokenWord]) -> List[Tuple[int, float]]:
    """Where each timed word starts in the segment text, with the time it was spoken.

    Whisper's words, joined, make up the segment text, so each one is found by
    searching forward from the end of the previous one. Words that can't be
    found (Whisper occasionally normalises them) are skipped.
    """
    found: List[Tuple[int, float]] = []
    cursor = 0
    for word in words:
        token = word.text.strip()
        at = text.find(token, cursor) if token else -1
        if at == -1:
            continue
        found.append((at, word.start))
        cursor = at + len(token)
    return found


def spoken_at(start_char: Optional[int], positions: List[Tuple[int, float]], fallback: float) -> float:
    """When the word starting at `start_char` was said: the last timed word starting at or before it."""
    if start_char is None or not positions:
        return fallback
    i = bisect.bisect_right([p for p, _ in positions], start_char) - 1
    return positions[max(i, 0)][1]


SENTENCE_ENDINGS = (".", "?", "!")


def split_sentences(seg: Segment) -> List[Segment]:
    """Split a Whisper segment into one segment per sentence.

    Whisper's segments can hold several sentences. Like closed captions, the
    page shows and signs one sentence at a time, so each sentence gets its own
    start and end from its first and last word. Segments without word timings
    are left whole.
    """
    if not seg.words:
        return [seg]
    groups: List[List[SpokenWord]] = [[]]
    for word in seg.words:
        groups[-1].append(word)
        if word.text.rstrip("\"')").endswith(SENTENCE_ENDINGS):
            groups.append([])
    return [
        Segment(words[0].start, words[-1].end, " ".join(w.text for w in words), tuple(words))
        for words in groups
        if words
    ]


def translate_video(
    media_path: str | Path, transcriber: Transcriber, glosser: Glosser, media: Optional[MediaFinder] = None
) -> dict:
    """Transcribe a video and convert each spoken sentence into ASL signs.

    Returns a JSON-ready dict:
      transcript: the full English transcript
      segments:   one per sentence: [{start, end, text, signs: [{text, gloss, kind, start, media}]}]
      result:     every gloss joined by spaces (what the current page displays)

    A sign's `start` is when its English word was spoken. Signs are in ASL
    order, which isn't always the order the words were said.

    `media` is what to show for a sign (a video or image), or None if there is
    nothing to show; it is only added when a media finder is passed in.
    """
    segments = transcriber.transcribe(media_path)
    out_segments = []
    all_signs: List[Sign] = []
    for seg in (sentence for segment in segments for sentence in split_sentences(segment)):
        signs = glosser.to_signs(seg.text)
        all_signs.extend(signs)
        positions = word_positions(seg.text, seg.words)
        out_signs = []
        for sign in signs:
            out = asdict(sign)
            out["start"] = round(spoken_at(out.pop("start_char"), positions, seg.start), 2)
            out_signs.append(out)
        out_segments.append(
            {
                "start": round(seg.start, 2),
                "end": round(seg.end, 2),
                "text": seg.text,
                "signs": out_signs,
            }
        )
    if media is not None:
        # One lookup for the whole video so repeated words are fetched once.
        found = iter(media.for_signs(all_signs))
        for seg in out_segments:
            for sign in seg["signs"]:
                sign["media"] = next(found)
    return {
        "transcript": " ".join(seg.text for seg in segments),
        "segments": out_segments,
        "result": gloss_string(all_signs),
    }

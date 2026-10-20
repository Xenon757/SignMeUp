"""Video -> timestamped ASL signs."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import List, Optional, Protocol

from .transcribe import Segment
from .translate import Sign, gloss_string


class Transcriber(Protocol):
    def transcribe(self, media_path: str | Path) -> List[Segment]: ...


class Glosser(Protocol):
    def to_signs(self, text: str) -> List[Sign]: ...


class MediaFinder(Protocol):
    def for_signs(self, signs: List[Sign]) -> List[Optional[dict]]: ...


def translate_video(
    media_path: str | Path, transcriber: Transcriber, glosser: Glosser, media: Optional[MediaFinder] = None
) -> dict:
    """Transcribe a video and convert each spoken segment into ASL signs.

    Returns a JSON-ready dict:
      transcript: the full English transcript
      segments:   [{start, end, text, signs: [{text, gloss, kind, media}]}]
      result:     every gloss joined by spaces (what the current page displays)

    `media` is what to show for a sign (a video or image), or None if there is
    nothing to show; it is only added when a media finder is passed in.
    """
    segments = transcriber.transcribe(media_path)
    out_segments = []
    all_signs: List[Sign] = []
    for seg in segments:
        signs = glosser.to_signs(seg.text)
        all_signs.extend(signs)
        out_segments.append(
            {
                "start": round(seg.start, 2),
                "end": round(seg.end, 2),
                "text": seg.text,
                "signs": [asdict(s) for s in signs],
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

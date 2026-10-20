"""Video -> timestamped ASL signs."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Protocol, List

from .transcribe import Segment
from .translate import Sign, gloss_string


class Transcriber(Protocol):
    def transcribe(self, media_path: str | Path) -> List[Segment]: ...


class Glosser(Protocol):
    def to_signs(self, text: str) -> List[Sign]: ...


def translate_video(media_path: str | Path, transcriber: Transcriber, glosser: Glosser) -> dict:
    """Transcribe a video and convert each spoken segment into ASL signs.

    Returns a JSON-ready dict:
      transcript: the full English transcript
      segments:   [{start, end, text, signs: [{text, gloss, kind}]}]
      result:     every gloss joined by spaces (what the current page displays)
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
    return {
        "transcript": " ".join(seg.text for seg in segments),
        "segments": out_segments,
        "result": gloss_string(all_signs),
    }

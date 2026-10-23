"""The built-in demo: "Me at the zoo", the first video on YouTube, signed by SignMeUp.

The video itself is never copied: the page embeds it with YouTube's own player and syncs the
signer to it. Since there's no audio file to transcribe, the transcript is written out here.

The sentence times are approximate (set by hand, not from the audio); each word is placed
evenly within its sentence. Adjust them here if the signing drifts from the speech.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from .pipeline import timed_words
from .transcribe import Segment

YOUTUBE_ID = "jNQXAC9IVRw"
TITLE = "Me at the zoo"
CREDIT = "“Me at the zoo” by jawed (Jawed Karim), 2005: the first video uploaded to YouTube."

# (start, end, text) for each spoken sentence, in seconds.
SENTENCES = [
    (1.0, 4.7, "All right, so here we are in front of the elephants."),
    (5.0, 11.9, "The cool thing about these guys is that they have really, really, really long trunks."),
    (12.2, 14.6, "And that's cool."),
    (15.0, 17.8, "And that's pretty much all there is to say."),
]


def demo_segments() -> List[Segment]:
    return [Segment(start, end, text, tuple(timed_words(start, end, text))) for start, end, text in SENTENCES]


class DemoTranscriber:
    """Returns the demo's written transcript instead of listening to a file."""

    def transcribe(self, media_path: str | Path | None = None) -> List[Segment]:
        return demo_segments()


def demo_info() -> dict:
    return {"youtube_id": YOUTUBE_ID, "title": TITLE, "credit": CREDIT}

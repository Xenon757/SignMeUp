"""Speech-to-text with Whisper, returning timestamped segments.

Timestamps matter: each segment knows when it was spoken, so its signs can be
shown at the right moment in the video instead of spread evenly across it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Segment:
    start: float  # seconds from the start of the video
    end: float
    text: str


class TranscriptionError(RuntimeError):
    pass


def _pick_device() -> str:
    """Use a CUDA GPU when there is one; faster-whisper can't use Apple's MPS."""
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
    except ImportError:
        pass
    return "cpu"


class WhisperTranscriber:
    """Wraps faster-whisper, falling back to OpenAI's whisper package.

    The model is loaded once, on first use.
    """

    def __init__(self, model_size: str = "tiny", device: Optional[str] = None):
        self.model_size = model_size
        self.device = device or _pick_device()
        self._model = None
        self._backend: Optional[str] = None

    def _load(self):
        if self._model is not None:
            return
        try:
            from faster_whisper import WhisperModel

            compute_type = "float16" if self.device == "cuda" else "int8"
            self._model = WhisperModel(self.model_size, device=self.device, compute_type=compute_type)
            self._backend = "faster-whisper"
        except ImportError:
            try:
                import whisper
            except ImportError as exc:
                raise TranscriptionError(
                    "No Whisper backend installed. Run: pip install faster-whisper"
                ) from exc
            self._model = whisper.load_model(self.model_size, device=self.device)
            self._backend = "whisper"
        log.info("Loaded Whisper %s (%s) on %s", self.model_size, self._backend, self.device)

    def transcribe(self, media_path: str | Path) -> List[Segment]:
        path = Path(media_path)
        if not path.exists():
            raise TranscriptionError(f"File not found: {path.name}")
        self._load()
        try:
            if self._backend == "faster-whisper":
                raw, _info = self._model.transcribe(str(path), language="en")
                segments = [Segment(s.start, s.end, s.text.strip()) for s in raw]
            else:
                result = self._model.transcribe(str(path), language="en")
                segments = [
                    Segment(s["start"], s["end"], s["text"].strip()) for s in result["segments"]
                ]
        except Exception as exc:  # decoding errors, unsupported audio, etc.
            raise TranscriptionError(f"Could not transcribe {path.name}: {exc}") from exc
        return [s for s in segments if s.text]

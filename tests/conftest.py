"""Shared test fakes. Whisper and Stanza are replaced so tests run offline in seconds."""

import pytest

from app import create_app
from asl_util.transcribe import Segment, TranscriptionError
from asl_util.translate import Sign


class FakeTranscriber:
    def __init__(self, segments=None, error=None):
        self.segments = segments if segments is not None else [
            Segment(0.0, 2.5, "Hello Aadi."),
            Segment(2.5, 5.0, "The cat is sleeping."),
        ]
        self.error = error
        self.seen_paths = []

    def transcribe(self, media_path):
        self.seen_paths.append(media_path)
        if self.error:
            raise TranscriptionError(self.error)
        return self.segments


class FakeGlosser:
    """Signs every word as itself, lowercased, without punctuation."""

    def to_signs(self, text):
        words = [t.strip(".,!?").lower() for t in text.split()]
        return [Sign(t, t, "sign") for t in words if t]


@pytest.fixture
def transcriber():
    return FakeTranscriber()


@pytest.fixture
def upload_dir(tmp_path):
    return tmp_path / "uploads"


@pytest.fixture
def client(transcriber, upload_dir):
    app = create_app(transcriber=transcriber, glosser=FakeGlosser(), upload_dir=str(upload_dir))
    app.config["TESTING"] = True
    return app.test_client()

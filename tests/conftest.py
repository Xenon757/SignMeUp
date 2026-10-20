"""Shared test fakes. Whisper and Stanza are replaced so tests run offline in seconds."""

import pytest

from app import create_app
from asl_util.signbank import GlossIndex, SignMedia, VideoResolver, entry_page_url
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


class FakePages:
    """Stands in for aslsignbank.com: returns canned pages and counts fetches."""

    def __init__(self, pages=None, error=None):
        self.pages = pages or {}
        self.error = error
        self.fetched = []

    def __call__(self, url):
        self.fetched.append(url)
        if self.error:
            raise self.error
        return self.pages.get(url, "<html>no video here</html>")


HELLO_VIDEO = "https://aslsignbank.com/dictionary/protected_media/glossvideo/ASL/HE/HELLO-482.mp4"


def fake_media():
    """Signbank with one sign, HELLO, that has a video."""
    page = f'<video id="videoplayer" src="{HELLO_VIDEO.removeprefix("https://aslsignbank.com")}"></video>'
    return SignMedia(GlossIndex({"HELLO": 482}), VideoResolver(fetch=FakePages({entry_page_url(482): page})))


@pytest.fixture
def transcriber():
    return FakeTranscriber()


@pytest.fixture
def upload_dir(tmp_path):
    return tmp_path / "uploads"


@pytest.fixture
def client(transcriber, upload_dir):
    app = create_app(
        transcriber=transcriber, glosser=FakeGlosser(), upload_dir=str(upload_dir), media=fake_media()
    )
    app.config["TESTING"] = True
    return app.test_client()

"""Shared test fakes. Whisper and Stanza are replaced so tests run offline in seconds."""

import pytest

from app import create_app
from asl_util.poses import PoseStore
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
    """Signs every word as itself, lowercased, without punctuation, keeping its position."""

    def to_signs(self, text):
        signs, cursor = [], 0
        for token in text.split():
            at = text.index(token, cursor)
            cursor = at + len(token)
            word = token.strip(".,!?").lower()
            if word:
                signs.append(Sign(word, word, "sign", at))
        return signs


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


def fake_media(poses=None):
    """Signbank with one sign, HELLO, that has a video."""
    page = f'<video id="videoplayer" src="{HELLO_VIDEO.removeprefix("https://aslsignbank.com")}"></video>'
    return SignMedia(GlossIndex({"HELLO": 482}), VideoResolver(fetch=FakePages({entry_page_url(482): page})), poses)


def fake_poses(cache_dir):
    """A PoseStore whose 'tracking' returns a short clip with the right hand raised."""
    rest = [[0.5, 0.2], [0.6, 0.4], [0.4, 0.4], [0.65, 0.6], [0.35, 0.6], [0.6, 0.9], [0.4, 0.9], [0.58, 0.9], [0.42, 0.9]]
    raised = [p[:] for p in rest]
    raised[6] = [0.4, 0.5]

    def track(video, model):
        frames = [{"pose": pose, "leftHand": None, "rightHand": None, "face": None} for pose in [rest] * 3 + [raised] * 3 + [rest] * 3]
        return frames, 24.0, 400, 200

    def download(url, dest):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"fake")

    return PoseStore(cache_dir, cache_dir / "model.task", download=download, track=track)


@pytest.fixture
def transcriber():
    return FakeTranscriber()


@pytest.fixture
def upload_dir(tmp_path):
    return tmp_path / "uploads"


@pytest.fixture
def poses(tmp_path):
    return fake_poses(tmp_path / "poses")


@pytest.fixture
def frontend(tmp_path, transcriber, upload_dir, poses):
    """A client whose app serves a tiny stand-in for the built React app."""
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text('<!doctype html><div id="root"></div>')
    (dist / "assets" / "app.js").write_text("console.log('app')")
    app = create_app(transcriber=transcriber, glosser=FakeGlosser(), upload_dir=str(upload_dir),
                     media=fake_media(poses), poses=poses, frontend_dir=dist, cache_dir=tmp_path / "cache")
    return app.test_client()


@pytest.fixture
def client(tmp_path, transcriber, upload_dir, poses):
    app = create_app(
        transcriber=transcriber,
        glosser=FakeGlosser(),
        upload_dir=str(upload_dir),
        media=fake_media(poses),
        poses=poses,
        cache_dir=tmp_path / "cache",
    )
    app.config["TESTING"] = True
    return app.test_client()

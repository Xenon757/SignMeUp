"""Tests for the /upload endpoint and the video -> signs pipeline."""

import io

from app import create_app
from asl_util.pipeline import translate_video
from asl_util.poses import CLIP_VERSION
from asl_util.transcribe import Segment

from conftest import HELLO_VIDEO, FakeGlosser, FakeTranscriber


def upload(client, name="talk.mp4", data=b"fake video bytes"):
    return client.post(
        "/upload",
        data={"file": (io.BytesIO(data), name)},
        content_type="multipart/form-data",
    )


def test_home_page_renders(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"SignMeUp" in res.data


def test_pose_prototype_page_renders(client):
    res = client.get("/prototype")
    assert res.status_code == 200
    assert b"2D signing prototype" in res.data


def test_healthz(client):
    assert client.get("/healthz").get_json() == {"status": "ok"}


def test_upload_returns_timestamped_signs(client):
    res = upload(client)
    assert res.status_code == 200
    body = res.get_json()
    assert body["result"] == "hello aadi the cat is sleeping"
    assert body["transcript"] == "Hello Aadi. The cat is sleeping."
    first = body["segments"][0]
    assert (first["start"], first["end"]) == (0.0, 2.5)
    assert [s["gloss"] for s in first["signs"]] == ["hello", "aadi"]


def test_upload_attaches_sign_media(client):
    first = upload(client).get_json()["segments"][0]
    hello, aadi = first["signs"]
    assert hello["media"]["type"] == "video"
    assert hello["media"]["url"] == HELLO_VIDEO
    assert hello["media"]["page"] == "https://aslsignbank.com/dictionary/gloss/482.html"
    assert aadi["media"] is None


def test_upload_makes_pose_animation_and_serves_it(client):
    hello = upload(client).get_json()["segments"][0]["signs"][0]
    assert hello["media"]["pose"] == f"/poses/482.json?v={CLIP_VERSION}"
    res = client.get(hello["media"]["pose"])
    assert res.status_code == 200
    assert res.get_json()["gloss"] == "HELLO"
    assert res.get_json()["frames"]


def test_unknown_pose_is_404_and_does_not_start_tracking(client, poses):
    res = client.get("/poses/999.json")
    assert res.status_code == 404
    assert "error" in res.get_json()
    assert not poses.path(999).exists()


def test_uploaded_file_is_deleted_after_processing(client, transcriber, upload_dir):
    upload(client)
    assert len(transcriber.seen_paths) == 1
    assert not transcriber.seen_paths[0].exists()
    assert list((upload_dir / "signmeup").iterdir()) == []


def test_filename_cannot_escape_the_upload_folder(client, transcriber, upload_dir):
    res = upload(client, name="../../../app.py.mp4")
    assert res.status_code == 200
    saved = transcriber.seen_paths[0]
    assert saved.parent == upload_dir / "signmeup"
    assert ".." not in saved.name and "app.py" not in saved.name


def test_missing_file_field(client):
    res = client.post("/upload", data={}, content_type="multipart/form-data")
    assert res.status_code == 400
    assert "No file" in res.get_json()["error"]


def test_empty_filename(client):
    res = upload(client, name="")
    assert res.status_code == 400


def test_rejects_unsupported_file_types(client, transcriber):
    res = upload(client, name="notes.exe")
    assert res.status_code == 415
    assert ".exe" in res.get_json()["error"]
    assert transcriber.seen_paths == []


def test_extension_check_is_case_insensitive(client):
    assert upload(client, name="CLIP.MP4").status_code == 200


def test_transcription_failure_returns_422(upload_dir):
    app = create_app(
        transcriber=FakeTranscriber(error="Could not transcribe talk.mp4: bad audio"),
        glosser=FakeGlosser(),
        upload_dir=str(upload_dir),
    )
    res = upload(app.test_client())
    assert res.status_code == 422
    assert "bad audio" in res.get_json()["error"]


def test_video_without_speech_returns_422(upload_dir):
    app = create_app(transcriber=FakeTranscriber(segments=[]), glosser=FakeGlosser(), upload_dir=str(upload_dir))
    res = upload(app.test_client())
    assert res.status_code == 422
    assert "No speech" in res.get_json()["error"]


def test_unexpected_error_returns_500_without_leaking_details(upload_dir):
    class BrokenGlosser:
        def to_signs(self, text):
            raise RuntimeError("secret internal detail")

    app = create_app(transcriber=FakeTranscriber(), glosser=BrokenGlosser(), upload_dir=str(upload_dir))
    res = upload(app.test_client())
    assert res.status_code == 500
    assert "secret" not in res.get_json()["error"]


def test_oversized_upload_returns_413(client):
    client.application.config["MAX_CONTENT_LENGTH"] = 10
    res = upload(client, data=b"x" * 100)
    assert res.status_code == 413
    assert "too large" in res.get_json()["error"]


def test_pipeline_keeps_each_segment_timing():
    segments = [Segment(1.234, 3.456, "Go home."), Segment(4.0, 6.0, "Now.")]
    out = translate_video("video.mp4", FakeTranscriber(segments=segments), FakeGlosser())
    assert [(s["start"], s["end"]) for s in out["segments"]] == [(1.23, 3.46), (4.0, 6.0)]
    assert out["result"] == "go home now"

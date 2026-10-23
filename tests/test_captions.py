"""Tests for signing a video's own captions (sent by the browser extension)."""

import pytest

from app import create_app
from asl_util.captions import CaptionError, captions_key, parse_lines
from conftest import FakeGlosser, fake_media


def test_each_caption_line_becomes_a_segment_without_sound_notes():
    segments = parse_lines({"lines": [
        {"start": 1.0, "end": 3.0, "text": "[Music] hello there"},
        {"start": 3.0, "end": 4.0, "text": "[Applause]"},
        {"start": 4.0, "end": 6.0, "text": "how are you"},
    ]})
    assert [(s.start, s.end, s.text) for s in segments] == [(1.0, 3.0, "hello there"), (4.0, 6.0, "how are you")]


def test_lines_without_word_timings_get_them_spread_across_the_line():
    (segment,) = parse_lines({"lines": [{"start": 2.0, "end": 4.0, "text": "hello there"}]})
    assert [w.text for w in segment.words] == ["hello", "there"]
    assert segment.words[0].start == 2.0 and abs(segment.words[-1].end - 4.0) < 0.02


def test_word_timings_from_auto_captions_are_kept():
    (segment,) = parse_lines({"lines": [{"start": 2.0, "end": 4.0, "text": "hello there",
                                         "words": [{"start": 2.0, "text": "hello"}, {"start": 3.5, "text": "there"}]}]})
    assert [(w.start, w.end, w.text) for w in segment.words] == [(2.0, 3.5, "hello"), (3.5, 4.0, "there")]


@pytest.mark.parametrize("bad", [
    None,
    {"lines": []},
    {"lines": "hello"},
    {"lines": [{"start": 1, "end": 2}]},
    {"lines": [{"start": "1", "end": 2, "text": "hi"}]},
    {"lines": [{"start": True, "end": 2, "text": "hi"}]},
    {"lines": [{"start": float("nan"), "end": 2, "text": "hi"}]},
    {"lines": [{"start": 3, "end": 2, "text": "hi"}]},
    {"lines": [{"start": 1, "end": 2, "text": "x" * 1001}]},
    {"lines": [{"start": 1, "end": 2, "text": "hi"}] * 401},
])
def test_badly_shaped_captions_are_refused(bad):
    with pytest.raises(CaptionError):
        parse_lines(bad)


def test_the_same_captions_get_the_same_key():
    lines = {"lines": [{"start": 1.0, "end": 2.0, "text": "hello"}]}
    assert captions_key(parse_lines(lines)) == captions_key(parse_lines(lines))
    other = {"lines": [{"start": 1.0, "end": 2.0, "text": "goodbye"}]}
    assert captions_key(parse_lines(lines)) != captions_key(parse_lines(other))


def test_endpoint_signs_each_line_at_its_words(client):
    res = client.post("/api/captions", json={"lines": [
        {"start": 5.0, "end": 7.0, "text": "hello friend",
         "words": [{"start": 5.0, "text": "hello"}, {"start": 6.0, "text": "friend"}]},
    ]})
    assert res.status_code == 200
    (segment,) = res.get_json()["segments"]
    assert segment["text"] == "hello friend"
    hello, friend = segment["signs"]
    assert (hello["gloss"], hello["start"], hello["media"]["gloss"]) == ("hello", 5.0, "HELLO")
    assert (friend["start"], friend["media"]["type"]) == (6.0, "spell")  # no sign in the fake Signbank


def test_endpoint_explains_bad_captions(client):
    res = client.post("/api/captions", json={"lines": [{"start": 3, "end": 2, "text": "hi"}]})
    assert res.status_code == 400
    assert "end before it starts" in res.get_json()["error"]


def test_endpoint_translates_the_same_captions_only_once(tmp_path, transcriber, upload_dir, poses):
    class CountingGlosser(FakeGlosser):
        calls = 0

        def to_signs(self, text):
            CountingGlosser.calls += 1
            return super().to_signs(text)

    app = create_app(transcriber=transcriber, glosser=CountingGlosser(), upload_dir=str(upload_dir),
                     media=fake_media(poses), poses=poses, cache_dir=tmp_path / "cache")
    client = app.test_client()
    lines = {"lines": [{"start": 1.0, "end": 2.0, "text": "hello"}]}
    first = client.post("/api/captions", json=lines).get_json()
    second = client.post("/api/captions", json=lines).get_json()
    assert first == second
    assert CountingGlosser.calls == 1

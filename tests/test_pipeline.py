"""Tests for timing each sign by when its word was spoken."""

from asl_util.pipeline import spoken_at, translate_video, word_positions
from asl_util.transcribe import Segment, SpokenWord
from asl_util.translate import Sign

from conftest import FakeTranscriber

TEXT = "The cat is sleeping."
WORDS = (SpokenWord(1.0, 1.2, "The"), SpokenWord(1.2, 1.6, "cat"), SpokenWord(1.6, 1.8, "is"), SpokenWord(1.8, 2.5, "sleeping."))


def test_word_positions_find_each_timed_word_in_order():
    assert word_positions(TEXT, WORDS) == [(0, 1.0), (4, 1.2), (8, 1.6), (11, 1.8)]


def test_word_positions_skip_words_not_in_text():
    words = (SpokenWord(0.0, 0.5, "Hi"), SpokenWord(0.5, 1.0, "forty-two"), SpokenWord(1.0, 1.5, "there"))
    assert word_positions("Hi 42 there", words) == [(0, 0.0), (6, 1.0)]


def test_repeated_words_are_matched_in_order():
    words = (SpokenWord(0.0, 0.3, "long"), SpokenWord(5.0, 5.3, "long"))
    assert word_positions("long long", words) == [(0, 0.0), (5, 5.0)]


def test_spoken_at_uses_the_word_containing_the_position():
    positions = word_positions(TEXT, WORDS)
    assert spoken_at(11, positions, fallback=0.0) == 1.8
    assert spoken_at(13, positions, fallback=0.0) == 1.8   # inside "sleeping"
    assert spoken_at(None, positions, fallback=9.0) == 9.0
    assert spoken_at(5, [], fallback=9.0) == 9.0


class ReorderingGlosser:
    """Signs 'The cat is sleeping.' in ASL order: SLEEP CAT."""

    def to_signs(self, text):
        return [Sign("sleeping", "sleep", "sign", 11), Sign("cat", "cat", "sign", 4)]


def test_each_sign_starts_when_its_word_was_spoken():
    out = translate_video("v.mp4", FakeTranscriber(segments=[Segment(1.0, 2.5, TEXT, WORDS)]), ReorderingGlosser())
    signs = out["segments"][0]["signs"]
    # ASL order puts SLEEP first, but it can't be shown before "sleeping" is said at 1.8s.
    assert [(s["gloss"], s["start"]) for s in signs] == [("sleep", 1.8), ("cat", 1.2)]
    assert "start_char" not in signs[0]


def test_signs_fall_back_to_segment_start_without_word_timing():
    out = translate_video("v.mp4", FakeTranscriber(segments=[Segment(3.0, 4.0, TEXT)]), ReorderingGlosser())
    assert {s["start"] for s in out["segments"][0]["signs"]} == {3.0}

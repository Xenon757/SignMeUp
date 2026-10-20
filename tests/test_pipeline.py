"""Tests for timing each sign by when its word was spoken."""

from asl_util.pipeline import split_sentences, spoken_at, translate_video, word_positions
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
    assert [s["start_char"] for s in signs] == [11, 4]  # where "sleeping" and "cat" are in the text


def test_signs_fall_back_to_segment_start_without_word_timing():
    out = translate_video("v.mp4", FakeTranscriber(segments=[Segment(3.0, 4.0, TEXT)]), ReorderingGlosser())
    assert {s["start"] for s in out["segments"][0]["signs"]} == {3.0}


THREE_SENTENCES = Segment(0.0, 8.4, "This is long. What's that? It's long", (
    SpokenWord(0.0, 0.3, "This"), SpokenWord(0.3, 0.5, "is"), SpokenWord(0.5, 1.0, "long."),
    SpokenWord(2.0, 2.4, "What's"), SpokenWord(2.4, 2.9, "that?"),
    SpokenWord(4.0, 4.3, "It's"), SpokenWord(4.3, 8.4, "long"),
))


def test_segment_is_split_into_sentences_with_their_own_timing():
    sentences = split_sentences(THREE_SENTENCES)
    assert [(s.start, s.end, s.text) for s in sentences] == [
        (0.0, 1.0, "This is long."),
        (2.0, 2.9, "What's that?"),
        (4.0, 8.4, "It's long"),
    ]
    assert [w.text for w in sentences[1].words] == ["What's", "that?"]


def test_sentence_ending_inside_quotes_still_splits():
    seg = Segment(0.0, 2.0, 'He said "go." Then left.', (
        SpokenWord(0.0, 0.5, "He"), SpokenWord(0.5, 0.8, "said"), SpokenWord(0.8, 1.0, '"go."'),
        SpokenWord(1.2, 1.5, "Then"), SpokenWord(1.5, 2.0, "left."),
    ))
    assert [s.text for s in split_sentences(seg)] == ['He said "go."', "Then left."]


def test_segment_without_word_timing_stays_whole():
    seg = Segment(0.0, 3.0, "One. Two.")
    assert split_sentences(seg) == [seg]


def test_video_output_has_one_segment_per_sentence():
    from conftest import FakeGlosser
    out = translate_video("v.mp4", FakeTranscriber(segments=[THREE_SENTENCES]), FakeGlosser())
    assert [(s["start"], s["text"]) for s in out["segments"]] == [(0.0, "This is long."), (2.0, "What's that?"), (4.0, "It's long")]
    assert out["transcript"] == THREE_SENTENCES.text

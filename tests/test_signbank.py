"""Tests for matching words to ASL Signbank entries. Uses a hand-built gloss list."""

from asl_util.signbank import GlossIndex, gloss_root

GLOSSES = {
    "CAT8": 347,
    "CATf": 1037,
    "HELLO": 482,
    "HELLOb": 900,
    "ICE-CREAMix": 2770,
    "WALK3": 1407,
    "WALKb": 314,
    "COMEroll": 55,
}


def test_gloss_root_strips_variant_suffix():
    assert gloss_root("CATf") == "CAT"
    assert gloss_root("WALK3") == "WALK"
    assert gloss_root("ICE-CREAMix") == "ICE-CREAM"
    assert gloss_root("HELLO") == "HELLO"


def test_gloss_root_keeps_all_lowercase_gloss():
    assert gloss_root("ix") == "ix"


def test_exact_gloss_comes_first():
    assert GlossIndex(GLOSSES).candidates("hello") == [("HELLO", 482), ("HELLOb", 900)]


def test_variants_are_found_when_there_is_no_exact_gloss():
    assert GlossIndex(GLOSSES).candidates("cat") == [("CAT8", 347), ("CATf", 1037)]


def test_multi_word_lemma_matches_hyphenated_gloss():
    assert GlossIndex(GLOSSES).candidates("ice cream") == [("ICE-CREAMix", 2770)]


def test_unknown_word_has_no_candidates():
    index = GlossIndex(GLOSSES)
    assert index.candidates("go") == []
    assert index.candidates("") == []


def test_bundled_gloss_file_loads():
    index = GlossIndex.load()
    assert index.candidates("hello")

"""Tests for the English -> ASL rules. No Stanza model needed: words are built by hand
in the same form Stanza's Universal Dependencies parser produces them."""

from types import SimpleNamespace

from asl_util.translate import (
    Sign,
    Word,
    fingerspell,
    gloss_string,
    number_sign,
    order_words,
    sentence_to_signs,
    words_from_stanza,
)


def w(index, head, text, lemma, upos, deprel="dep"):
    return Word(index, head, text, lemma, upos, deprel)


# "The cat is sleeping on the mat."
CAT_SENTENCE = [
    w(1, 2, "The", "the", "DET", "det"),
    w(2, 4, "cat", "cat", "NOUN", "nsubj"),
    w(3, 4, "is", "be", "AUX", "aux"),
    w(4, 0, "sleeping", "sleep", "VERB", "root"),
    w(5, 7, "on", "on", "ADP", "case"),
    w(6, 7, "the", "the", "DET", "det"),
    w(7, 4, "mat", "mat", "NOUN", "obl"),
    w(8, 4, ".", ".", "PUNCT", "punct"),
]


def test_full_sentence_drops_articles_be_and_prepositions():
    signs = sentence_to_signs(CAT_SENTENCE)
    assert gloss_string(signs) == "sleep cat mat"


def test_verbs_use_their_base_form():
    signs = sentence_to_signs([w(1, 0, "Running", "run", "VERB", "root")])
    assert signs == [Sign("running", "run", "sign")]


def test_words_are_grouped_by_the_word_they_attach_to():
    ordered = order_words(CAT_SENTENCE)
    assert [x.text for x in ordered][:3] == ["sleeping", "The", "cat"]


def test_subject_pronouns_are_dropped_but_object_pronouns_kept():
    # "I like you"
    words = [
        w(1, 2, "I", "I", "PRON", "nsubj"),
        w(2, 0, "like", "like", "VERB", "root"),
        w(3, 2, "you", "you", "PRON", "obj"),
    ]
    assert gloss_string(sentence_to_signs(words)) == "like you"


def test_that_as_a_connector_is_dropped():
    words = [w(1, 0, "that", "that", "SCONJ", "mark")]
    assert sentence_to_signs(words) == []


def test_names_are_fingerspelled():
    signs = sentence_to_signs([w(1, 0, "Aadi", "Aadi", "PROPN", "root")])
    assert [s.gloss for s in signs] == ["a", "a", "d", "i"]
    assert all(s.kind == "fingerspell" for s in signs)


def test_fingerspelling_skips_non_letters():
    assert [s.gloss for s in fingerspell("O'Neil-2")] == list("oneil")


def test_numbers_become_number_words():
    assert number_sign("42") == Sign("42", "forty-two", "number")
    assert number_sign("3.5,").gloss == "three point five"


def test_unparseable_number_falls_back_to_text():
    sign = number_sign("1,000")
    assert sign.kind == "sign" and sign.gloss == "1,000"


def test_symbols_particles_and_unknown_tags_are_dropped():
    words = [
        w(1, 0, "%", "%", "SYM"),
        w(2, 0, "to", "to", "PART"),
        w(3, 0, "xyz", "xyz", "X"),
        w(4, 0, "!", "!", "PUNCT"),
    ]
    assert sentence_to_signs(words) == []


def test_words_from_stanza_flattens_multiword_tokens():
    # Stanza splits contractions like "don't" into two words under one token.
    sentence = SimpleNamespace(
        tokens=[
            SimpleNamespace(words=[
                SimpleNamespace(id=1, head=3, text="do", lemma="do", upos="AUX", deprel="aux"),
                SimpleNamespace(id=2, head=3, text="n't", lemma="not", upos="PART", deprel="advmod"),
            ]),
            SimpleNamespace(words=[
                SimpleNamespace(id=3, head=0, text="go", lemma=None, upos="VERB", deprel="root"),
            ]),
        ]
    )
    words = words_from_stanza(sentence)
    assert [x.text for x in words] == ["do", "n't", "go"]
    assert words[2].lemma == "go"  # missing lemma falls back to the text

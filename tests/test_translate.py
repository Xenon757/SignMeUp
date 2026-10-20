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
    assert gloss_string(signs) == "cat sleep mat"


def test_verbs_use_their_base_form():
    signs = sentence_to_signs([w(1, 0, "Running", "run", "VERB", "root")])
    assert signs == [Sign("running", "run", "sign")]


def test_words_keep_spoken_order():
    shuffled = list(reversed(CAT_SENTENCE))
    assert [x.text for x in order_words(shuffled)] == [x.text for x in CAT_SENTENCE]


# "What is your name?"
QUESTION = [
    w(1, 4, "What", "what", "PRON", "nsubj"),
    w(2, 4, "is", "be", "AUX", "cop"),
    w(3, 4, "your", "your", "PRON", "nmod:poss"),
    w(4, 0, "name", "name", "NOUN", "root"),
    w(5, 4, "?", "?", "PUNCT", "punct"),
]


def test_question_word_moves_to_the_end_of_a_question():
    assert gloss_string(sentence_to_signs(QUESTION)) == "your name what"


def test_question_word_stays_put_when_not_a_question():
    # "That's why I left."
    sentence = [
        w(1, 3, "That", "that", "PRON", "nsubj"),
        w(2, 3, "'s", "be", "AUX", "cop"),
        w(3, 0, "why", "why", "ADV", "root"),
        w(4, 5, "I", "I", "PRON", "nsubj"),
        w(5, 3, "left", "leave", "VERB", "advcl"),
        w(6, 3, ".", ".", "PUNCT", "punct"),
    ]
    assert gloss_string(sentence_to_signs(sentence)) == "why leave"


def test_reordering_only_moves_words_later():
    # Signs are shown once their word is said, so no word may move before an earlier one.
    for sentence in (CAT_SENTENCE, QUESTION):
        ordered = order_words(sentence)
        for before, after in zip(ordered, ordered[1:]):
            assert after.index > before.index or after.lemma.lower() in {"what", "where", "when", "who", "why", "how", "which"}


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


def test_signs_remember_where_their_word_starts():
    words = [Word(1, 2, "Aadi", "Aadi", "PROPN", "nsubj", start_char=0), Word(2, 0, "runs", "run", "VERB", "root", start_char=5)]
    signs = sentence_to_signs(words)
    assert [s.start_char for s in signs] == [0, 0, 0, 0, 5]  # A-A-D-I share the name's position, then RUN


def test_words_from_stanza_keeps_token_position():
    sentence = SimpleNamespace(tokens=[
        SimpleNamespace(start_char=4, words=[SimpleNamespace(id=1, head=0, text="cats", lemma="cat", upos="NOUN", deprel="root")]),
    ])
    assert words_from_stanza(sentence)[0].start_char == 4


def test_question_word_as_subject_is_not_dropped():
    # "Who called?"
    sentence = [w(1, 2, "Who", "who", "PRON", "nsubj"), w(2, 0, "called", "call", "VERB", "root"), w(3, 2, "?", "?", "PUNCT", "punct")]
    assert gloss_string(sentence_to_signs(sentence)) == "call who"


def test_negation_is_always_signed():
    # "I do n't know." -- Stanza splits "don't" into "do" + "n't" (lemma "not", tagged PART).
    sentence = [
        w(1, 4, "I", "I", "PRON", "nsubj"),
        w(2, 4, "do", "do", "AUX", "aux"),
        w(3, 4, "n't", "not", "PART", "advmod"),
        w(4, 0, "know", "know", "VERB", "root"),
    ]
    assert gloss_string(sentence_to_signs(sentence)) == "not know"


def test_no_as_a_determiner_is_signed():
    # "No matter what."
    sentence = [w(1, 2, "No", "no", "DET", "det"), w(2, 0, "matter", "matter", "NOUN", "root")]
    assert gloss_string(sentence_to_signs(sentence)) == "no matter"


def test_quantifiers_are_signed_but_articles_are_not():
    sentence = [w(1, 2, "All", "all", "DET", "det"), w(2, 0, "cats", "cat", "NOUN", "root"), w(3, 2, "the", "the", "DET", "det")]
    assert gloss_string(sentence_to_signs(sentence)) == "all cat"


def test_base_form_verb_keeps_its_own_form():
    # "not to bore you": the lemmatizer says "bear" (bore = past of bear), but VB means base form.
    bore = Word(1, 0, "bore", "bear", "VERB", "root", xpos="VB")
    assert sentence_to_signs([bore])[0].gloss == "bore"


def test_past_tense_verb_is_still_lemmatized():
    ran = Word(1, 0, "ran", "run", "VERB", "root", xpos="VBD")
    assert sentence_to_signs([ran])[0].gloss == "run"

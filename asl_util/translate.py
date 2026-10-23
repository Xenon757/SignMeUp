"""English -> ASL gloss translation.

ASL is not English word-for-word: it drops articles, most forms of "to be",
and prepositions, uses base word forms instead of tenses, and fingerspells
names letter by letter. This module applies those rules to words that have
already been parsed (part of speech, lemma, dependency relation).

The rules are pure functions over `Word` objects so they can be tested without
loading Stanza. `StanzaGlosser` is the thin layer that runs the real parser.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Iterable, List, Optional

from num2words import num2words


@dataclass(frozen=True)
class Word:
    """One parsed word, as produced by a Universal Dependencies parser."""

    index: int       # position in the sentence (1-based)
    head: int        # index of the word this one depends on (0 = root)
    text: str
    lemma: str
    upos: str        # universal part-of-speech tag, e.g. NOUN, VERB, PROPN
    deprel: str      # dependency relation to the head, e.g. nsubj, obj
    start_char: Optional[int] = None  # where the word starts in the sentence text
    xpos: Optional[str] = None        # Penn Treebank tag, e.g. VB (base form), VBD (past)


@dataclass(frozen=True)
class Sign:
    """One unit of ASL output."""

    text: str         # the English word it came from
    gloss: str        # what to sign (a base word, a letter, or a number word)
    kind: str         # "sign", "fingerspell" or "number"
    # Where the English word starts in the input text, used to find when it was spoken.
    # Not part of a sign's identity, so it's left out of comparisons.
    start_char: Optional[int] = field(default=None, compare=False)


# (surface text, lemma) pairs that ASL leaves out entirely.
DROPPED_WORDS = {
    ("is", "be"), ("are", "be"), ("the", "the"), ("of", "of"), ("by", "by"),
    ("a", "a"), ("an", "a"), (",", ","), (";", ";"), (":", ":"),
}

# Parts of speech that ASL drops: auxiliaries, determiners, prepositions,
# plus symbols, particles and unknown tokens.
DROPPED_POS = {"AUX", "DET", "ADP", "SYM", "X", "PART"}

SIGNED_POS = {"NOUN", "VERB", "ADJ", "ADV", "PRON", "INTJ", "CCONJ", "SCONJ"}

# Negation changes the meaning of a sentence, so it is always signed, even though
# parsers tag "not"/"n't" as particles and "no" as a determiner.
NEGATIONS = {"not", "no", "never", "nothing", "nobody", "none"}

# Quantifiers are determiners too, but carry meaning ASL signs ("ALL", "SOME", "MANY").
QUANTIFIERS = {"all", "some", "every", "each", "any", "many", "few", "both", "much", "more", "most"}

# Penn Treebank tags for verbs already in their base form ("to bore", "I bore").
BASE_FORM_VERB_TAGS = {"VB", "VBP"}


# Question words that ASL usually signs at the end of a question.
WH_WORDS = {"what", "where", "when", "who", "whom", "whose", "why", "how", "which"}


def order_words(words: Iterable[Word]) -> List[Word]:
    """Put a sentence's words in signing order.

    ASL's basic word order is subject-verb-object, like English, so words stay
    in the order they were spoken. In a question, the question word moves to
    the end ("What is your name?" -> YOUR NAME WHAT), as is common in ASL.

    Words are only ever moved later, never earlier. Signs are shown as their
    words are spoken, so moving a word earlier would make the signing wait
    for it to be said.
    """
    ordered = sorted(words, key=lambda w: w.index)
    if not any(w.text == "?" for w in ordered):
        return ordered
    wh = [w for w in ordered if w.lemma.lower() in WH_WORDS]
    rest = [w for w in ordered if w.lemma.lower() not in WH_WORDS]
    return rest + wh


def number_sign(text: str, start_char: Optional[int] = None) -> Sign:
    """Turn a numeral like '42' or '3.5' into a number sign ('forty-two')."""
    clean = text.strip(".,!?;:")
    try:
        if clean.isdigit():
            return Sign(text, num2words(int(clean)), "number", start_char)
        if "." in clean and clean.replace(".", "", 1).isdigit():
            return Sign(text, num2words(float(clean)), "number", start_char)
    except (ValueError, TypeError, OverflowError):
        pass
    return Sign(text, clean or text, "sign", start_char)


def fingerspell(text: str, start_char: Optional[int] = None) -> List[Sign]:
    """Spell a word letter by letter (used for names)."""
    return [Sign(ch, ch, "fingerspell", start_char) for ch in text.lower() if ch.isalpha()]


def word_to_signs(word: Word) -> List[Sign]:
    """Apply the ASL rules to a single word. Returns [] if it isn't signed."""
    text, lemma = word.text.lower(), word.lemma.lower()

    if lemma in NEGATIONS:
        return [Sign(text, "not" if lemma == "not" else lemma, "sign", word.start_char)]
    if word.upos == "DET" and lemma in QUANTIFIERS:
        return [Sign(text, lemma, "sign", word.start_char)]
    if (text, lemma) in DROPPED_WORDS or word.upos in DROPPED_POS:
        return []
    if word.upos == "PROPN":
        return fingerspell(text, word.start_char)
    if word.upos == "NUM":
        return [number_sign(text, word.start_char)]
    if word.upos not in SIGNED_POS:
        return []
    # Subject pronouns are usually implied in ASL; "that" as a connector is dropped.
    # Question words like "what" are kept even as subjects: they carry the question.
    if word.upos == "PRON" and word.deprel == "nsubj" and lemma not in WH_WORDS:
        return []
    if word.upos == "SCONJ" and lemma == "that":
        return []
    # A verb tagged as a base form is already its own lemma. Trusting the tag avoids
    # lemmatizer mix-ups between verbs whose forms collide ("bore" -> "bear").
    if word.upos == "VERB" and word.xpos in BASE_FORM_VERB_TAGS and text.isalpha():
        lemma = text
    return [Sign(text, lemma, "sign", word.start_char)]


def sentence_to_signs(words: Iterable[Word]) -> List[Sign]:
    signs: List[Sign] = []
    for word in order_words(words):
        signs.extend(word_to_signs(word))
    return signs


def gloss_string(signs: Iterable[Sign]) -> str:
    """Space-separated gloss, the format the web page expects."""
    return " ".join(sign.gloss for sign in signs)


# Stanza processors the translation needs (also downloaded ahead of time by scripts/download_models.py).
STANZA_PROCESSORS = "tokenize,pos,lemma,depparse"


class StanzaGlosser:
    """Parses English with Stanza and converts it to ASL signs.

    The Stanza model takes several seconds to load, so it is created once,
    on first use, and reused for every request.
    """

    def __init__(self, use_gpu: bool = False):
        self._use_gpu = use_gpu
        self._nlp = None
        self._lock = threading.Lock()  # the server warms up in one thread while a job may start in another
        self._run_lock = threading.Lock()  # uploads and caption requests share one parser

    def warm_up(self) -> None:
        """Load the parser now instead of on the first upload."""
        self._pipeline()

    def _pipeline(self):
        with self._lock:
            if self._nlp is None:
                self._nlp = self._load_pipeline()
        return self._nlp

    def _load_pipeline(self):
        import stanza  # heavy import, deferred until actually needed

        return stanza.Pipeline(
            lang="en",
            processors=STANZA_PROCESSORS,
            use_gpu=self._use_gpu,
            verbose=False,
            # Use models already on disk (baked into the deployed image) instead of
            # checking for updates online at every start; downloads only if missing.
            download_method=stanza.DownloadMethod.REUSE_RESOURCES,
        )

    def to_signs(self, text: str) -> List[Sign]:
        nlp = self._pipeline()
        with self._run_lock:
            doc = nlp(text)
        signs: List[Sign] = []
        for sentence in doc.sentences:
            signs.extend(sentence_to_signs(words_from_stanza(sentence)))
        return signs


def words_from_stanza(sentence) -> List[Word]:
    return [
        Word(
            index=int(w.id),
            head=int(w.head),
            text=w.text,
            lemma=w.lemma or w.text,
            upos=w.upos,
            deprel=w.deprel,
            xpos=getattr(w, "xpos", None),
            # Words inside a contraction ("do" in "don't") share the token's position.
            start_char=getattr(token, "start_char", None),
        )
        for token in sentence.tokens
        for w in token.words
    ]

"""Suggest synonyms for common words that have no animated sign, to review by hand.

For each of the most common English words (wordfreq) whose base form has no Signbank sign with
an animation, this looks through WordNet's senses of the word, most common sense first, for a
synonym that does have one, and prints: word, synonym, sign, and the WordNet sense used. The
output is a list to review, not to trust: WordNet senses don't always match how a word is meant,
so the accepted pairs go into asl_util/data/sign_synonyms.json by hand.

Needs (development only): pip install nltk wordfreq, then nltk.download("wordnet").

Usage:
    SIGNMEUP_CACHE_DIR=... python scripts/suggest_synonyms.py [N_WORDS] > suggestions.tsv
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nltk.corpus import wordnet as wn  # noqa: E402
from wordfreq import top_n_list, zipf_frequency  # noqa: E402

from asl_util.signbank import GlossIndex  # noqa: E402
from asl_util.translate import StanzaGlosser  # noqa: E402

SENSES = 3  # only a word's most common senses


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    cache_dir = Path(os.environ.get("SIGNMEUP_CACHE_DIR", Path(tempfile.gettempdir()) / "signmeup-cache"))
    animations = {p.stem for p in (cache_dir / "poses").glob("*.json")}
    index = GlossIndex.load()

    def sign_for(word: str) -> str | None:
        return next((gloss for gloss, entry in index.candidates(word)[:4] if str(entry) in animations), None)

    words = [w for w in top_n_list("en", n * 2) if re.fullmatch(r"[a-z]+", w)][:n]
    bases = []
    for signs in StanzaGlosser().to_signs_many(words):
        bases += [s.gloss for s in signs if s.kind == "sign" and s.gloss.isalpha()]
    missing = [w for w in dict.fromkeys(bases) if not sign_for(w)]
    found = 0
    for word in missing:
        best = None
        for rank, synset in enumerate(wn.synsets(word)[:SENSES]):
            related = list(synset.lemmas()) + [l for s in synset.similar_tos() for l in s.lemmas()]
            options = [l.name().replace("_", " ").lower() for l in related]
            options = sorted({o for o in options if o != word and " " not in o}, key=lambda o: -zipf_frequency(o, "en"))
            for option in options:
                gloss = sign_for(option)
                if gloss:
                    best = (option, gloss, synset.name(), synset.definition())
                    break
            if best:
                break
        if best:
            found += 1
            print("\t".join([word, *best]))
    print(f"# {len(missing)} of {len(dict.fromkeys(bases))} signed base words have no animated sign; "
          f"{found} have a WordNet synonym that does", file=sys.stderr)


if __name__ == "__main__":
    main()

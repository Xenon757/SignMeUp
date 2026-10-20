"""Find ASL Signbank entries for signed words.

ASL Signbank (https://aslsignbank.com, CC BY-NC-SA 4.0) has a reference video
for thousands of ASL signs. Its glosses are uppercase English words, with
lowercase or digit suffixes marking variants of the same sign: CATf and CATg
are two ways to sign CAT, WALK3 is one way to sign WALK.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Tuple

GLOSS_FILE = Path(__file__).resolve().parent / "data" / "signbank_glosses.json"

# Trailing variant marker: "CATf" -> "CAT", "WALK3" -> "WALK".
_VARIANT_SUFFIX = re.compile(r"[a-z0-9]+$")


def gloss_root(gloss: str) -> str:
    """The sign a gloss is a variant of, e.g. 'RUNasym' -> 'RUN'."""
    return _VARIANT_SUFFIX.sub("", gloss) or gloss


class GlossIndex:
    """Maps an English base word to the Signbank entries that sign it."""

    def __init__(self, glosses: Dict[str, int]):
        self._exact: Dict[str, int] = dict(glosses)
        self._by_root: Dict[str, List[Tuple[str, int]]] = {}
        for gloss, entry_id in sorted(glosses.items()):
            self._by_root.setdefault(gloss_root(gloss), []).append((gloss, entry_id))

    @classmethod
    def load(cls, path: Path = GLOSS_FILE) -> "GlossIndex":
        return cls(json.loads(path.read_text(encoding="utf-8"))["glosses"])

    def candidates(self, word: str) -> List[Tuple[str, int]]:
        """Entries for a word, best first: an exact gloss, then its variants.

        Multi-word glosses use hyphens ("ice cream" -> ICE-CREAM). Words with no
        gloss return [] rather than a loosely related sign.
        """
        key = word.strip().upper().replace(" ", "-")
        if not key:
            return []
        found: List[Tuple[str, int]] = []
        if key in self._exact:
            found.append((key, self._exact[key]))
        found.extend(c for c in self._by_root.get(key, []) if c[0] != key)
        return found

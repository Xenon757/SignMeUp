"""Build asl_util/data/signbank_glosses.json from ASL Signbank's gloss list.

ASL Signbank publishes every gloss, its entry ID and its English translations
as an ELAN controlled vocabulary (.ecv). We keep the gloss -> ID pairs and the
translations (used to find signs for words that aren't gloss names); the video
for an entry is looked up from its page when a sign is first needed (see
asl_util/signbank.py).

Usage:
    python scripts/build_signbank_index.py            # downloads the current list
    python scripts/build_signbank_index.py asl.ecv    # uses a local copy
"""

from __future__ import annotations

import json
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ECV_URL = "https://aslsignbank.com/static/ecv/asl.ecv"
OUT = Path(__file__).resolve().parent.parent / "asl_util" / "data" / "signbank_glosses.json"


def parse_ecv(xml_text: str) -> tuple[dict[str, int], dict[str, list[str]]]:
    """Gloss -> entry ID, and gloss -> its English translations (lowercase)."""
    glosses, translations = {}, {}
    for entry in ET.fromstring(xml_text).iter("CV_ENTRY_ML"):
        value = entry.find("CVE_VALUE")
        if value is not None and value.text:
            gloss = value.text.strip()
            glosses[gloss] = int(entry.get("CVE_ID"))
            words = [w.strip().lower() for w in (value.get("DESCRIPTION") or "").split(",")]
            if any(words):
                translations[gloss] = [w for w in words if w]
    return glosses, translations


def main() -> None:
    if len(sys.argv) > 1:
        xml_text = Path(sys.argv[1]).read_text(encoding="utf-8")
    else:
        with urllib.request.urlopen(ECV_URL, timeout=30) as resp:
            xml_text = resp.read().decode("utf-8")

    glosses, translations = parse_ecv(xml_text)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {
                "source": "ASL Signbank (Hochgesang, Crasborn & Lillo-Martin), https://aslsignbank.com",
                "license": "CC BY-NC-SA 4.0",
                "glosses": dict(sorted(glosses.items())),
                "translations": dict(sorted(translations.items())),
            },
            indent=0,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(glosses)} glosses to {OUT}")


if __name__ == "__main__":
    main()

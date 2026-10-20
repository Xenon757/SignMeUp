# SignMeUp - The ASL Subtitle

SignMeUp bridges the gap for deaf and hard-of-hearing viewers by turning English captions into ASL subtitles, making stories, lessons, and conversations truly accessible to everyone.

## What it does
A user uploads a video. SignMeUp transcribes its audio with OpenAI's Whisper model, keeping the time each phrase was spoken. Each phrase goes through an English-to-ASL translation step that reorders it and applies ASL grammar rules. Each sign is shown over the video as a reference video from [ASL Signbank](https://aslsignbank.com), and fingerspelled names are shown letter by letter as handshape images.

## How the translation works
ASL is not English word-for-word, so the text is parsed with [Stanza](https://stanfordnlp.github.io/stanza/) (part-of-speech tags, base word forms and dependency relations) and these rules are applied:

- Articles, forms of "to be", auxiliaries and prepositions are dropped ("The cat is sleeping on the mat" → `SLEEP CAT MAT`).
- Words are signed in their base form ("running" → `RUN`).
- Subject pronouns are dropped because ASL usually implies them.
- Names are fingerspelled letter by letter.
- Numerals become number words ("42" → `FORTY-TWO`).

## Project layout

| Path | What it does |
|---|---|
| `app.py` | Flask app: the page, `POST /upload`, `GET /healthz` |
| `asl_util/transcribe.py` | Whisper speech-to-text, returning timestamped segments |
| `asl_util/translate.py` | English → ASL rules (pure functions) and the Stanza parser wrapper |
| `asl_util/signbank.py` | Finds the ASL Signbank video for each sign, and the letter image for fingerspelling |
| `asl_util/data/` | ASL Signbank's gloss list (rebuilt with `scripts/build_signbank_index.py`) |
| `asl_util/pipeline.py` | Video → timestamped signs |
| `templates/`, `static/` | Web page, styles and fingerspelling images |
| `tests/` | Offline tests (Whisper and Stanza are replaced by fakes) |

## Running it

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt
python app.py            # open http://localhost:5000
```

The Whisper and Stanza models download on the first upload, so the first request is slow.

Settings (environment variables): `SIGNMEUP_WHISPER_MODEL` (default `tiny`), `SIGNMEUP_MAX_UPLOAD_MB` (default 200), `SIGNMEUP_UPLOAD_DIR` (default: the system temp folder), `SIGNMEUP_CACHE_DIR` (where found sign videos are remembered; default: a `signmeup-cache` folder in the system temp folder).

### API

`POST /upload` with a `file` form field (mp4, mov, m4v, webm, mkv, mp3, wav or m4a) returns:

```json
{
  "transcript": "Hello Aadi. The cat is sleeping.",
  "segments": [
    {"start": 0.0, "end": 2.5, "text": "Hello Aadi.",
     "signs": [{"text": "hello", "gloss": "hello", "kind": "sign",
                "media": {"type": "video",
                          "url": "https://aslsignbank.com/dictionary/protected_media/glossvideo/ASL/HE/HELLO-482.mp4",
                          "gloss": "HELLO",
                          "page": "https://aslsignbank.com/dictionary/gloss/482.html",
                          "source": "ASL Signbank (CC BY-NC-SA 4.0)"}},
               {"text": "a", "gloss": "a", "kind": "fingerspell",
                "media": {"type": "image", "url": "/static/img/fingerspelling/a.svg",
                          "source": "Wikimedia Commons (public domain)"}},
               ...]},
    {"start": 2.5, "end": 5.0, "text": "The cat is sleeping.",
     "signs": [{"text": "sleeping", "gloss": "sleep", "kind": "sign", "media": {"type": "video", ...}},
               {"text": "cat", "gloss": "cat", "kind": "sign", "media": {"type": "video", ...}}]}
  ],
  "result": "hello a a d i sleep cat"
}
```

`media` is `null` when there is no video for a sign; the page then shows the gloss as text.

Errors return `{"error": "..."}` with status 400 (no file), 413 (too large), 415 (unsupported type) or 422 (no speech found or the audio couldn't be transcribed).

## Sign media and licenses

| What | Source | License | How it's used |
|---|---|---|---|
| Sign videos | [ASL Signbank](https://aslsignbank.com) — Hochgesang, J. A., Crasborn, O., & Lillo-Martin, D. (2017–2026). ASL Signbank. https://doi.org/10.6084/m9.figshare.9741788 | [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) | Not copied into this repo. The page plays each video from aslsignbank.com and links to its Signbank entry. |
| Gloss list (`asl_util/data/signbank_glosses.json`) | ASL Signbank's published gloss vocabulary (`asl.ecv`) | CC BY-NC-SA 4.0 | Gloss names and entry IDs only, used to match words to entries. |
| Fingerspelling images (`static/img/fingerspelling/`) | [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Sign_language_A.svg), from wpclipart.com | Public domain | Bundled unmodified. See `CREDITS.md` there. |

How a word is matched: Signbank glosses are uppercase English words, and a lowercase or digit suffix marks a variant (`CATf`, `CAT8`). A word uses its exact gloss if there is one, otherwise the first variant (of up to three) that has a video. The video's address isn't part of the gloss list, so the server reads the entry's page the first time a sign is needed and caches the result. Words with no matching gloss show as text rather than a loosely related sign.

Because the Signbank material is licensed for non-commercial use only, this project is non-commercial.

Other sources that were checked and not used: ASL-LEX's sign videos are © ASL-LEX.org (only its database is openly licensed), ASL Citizen and WLASL are licensed for research use only, and Lifeprint and similar dictionary sites don't allow reuse in apps.

## Tests

```bash
pytest
```

The tests run offline in under a second: hand-built parses check each translation rule, and fake models check the upload endpoint, including that an uploaded filename like `../../app.py` can't write outside the upload folder.

## Built with
- Flask
- PyTorch
- TailwindCSS
- Whisper
- Stanza
- ASL Signbank

## History
Built at Hello World 2025 by the SignMeUp team ([original repo](https://github.com/ShlokShar/SignMeUp)) — Winner Gold Track (3rd Place) 🥉

This fork continues the project after the hackathon. Changes so far:
- Split the pipeline into tested modules and load the models once instead of on every upload
- Keep Whisper's timestamps so each sign can be shown when its phrase is spoken
- Store uploads under random names (the original used the uploaded filename as a path), limit file size and type, and delete uploads after processing
- Added offline tests
- Replaced the ASL-LEX handshape image (which showed only the hand shape, not the sign) with ASL Signbank sign videos, and added public-domain fingerspelling images

# SignMeUp - The ASL Subtitle

SignMeUp bridges the gap for deaf and hard-of-hearing viewers by turning English captions into ASL subtitles, making stories, lessons, and conversations truly accessible to everyone.

## What it does
A user uploads a video. SignMeUp transcribes its audio with OpenAI's Whisper model, keeping the time each phrase was spoken. Each phrase goes through an English-to-ASL translation step that applies ASL grammar rules. Each sign is shown over the video as a reference video from [ASL Signbank](https://aslsignbank.com), and fingerspelled names are shown letter by letter as handshape images.

A second page, `/prototype`, signs the video with a 2D animated figure instead. Dictionary videos are too slow to keep up with speech (each one starts and ends with the hands at rest, and runs about 2.5 seconds), so the figure plays only the part of each sign where the hands are moving, moves straight from one sign into the next, and speeds up (from 1.5× to 3×) the further it falls behind. No sign starts before its word is said. If the signing still falls behind, it catches up during pauses, and the page shows the sentence being signed next to the one being spoken.

## How the translation works
ASL is not English word-for-word, so the text is parsed with [Stanza](https://stanfordnlp.github.io/stanza/) (part-of-speech tags, base word forms and dependency relations) and these rules are applied:

- Articles, forms of "to be", auxiliaries and prepositions are dropped ("The cat is sleeping on the mat" → `CAT SLEEP MAT`).
- Words are signed in their base form ("running" → `RUN`).
- Subject pronouns are dropped because ASL usually implies them. Question words are kept even as subjects ("Who called?" → `CALL WHO`).
- Words keep their spoken order, since ASL's basic order is subject–verb–object like English. In a question, the question word moves to the end ("What is your name?" → `YOUR NAME WHAT`).

Words are only ever moved later in a sentence, never earlier. Signs appear once their word has been spoken, so moving a word earlier would make the signing wait for it. (The original version grouped words by their parse, which often put a sentence's last word first and held up the whole sentence.)
- Names are fingerspelled letter by letter.
- Numerals become number words ("42" → `FORTY-TWO`).

## Project layout

| Path | What it does |
|---|---|
| `app.py` | Flask app: the page, `POST /upload`, `GET /healthz` |
| `asl_util/transcribe.py` | Whisper speech-to-text, returning timestamped segments |
| `asl_util/translate.py` | English → ASL rules (pure functions) and the Stanza parser wrapper |
| `asl_util/signbank.py` | Finds the ASL Signbank video for each sign, and the letter image for fingerspelling |
| `asl_util/poses.py` | Turns a sign video into a 2D animation (MediaPipe tracking, trimming, shoulder-relative coordinates) and caches it |
| `asl_util/data/` | ASL Signbank's gloss list (rebuilt with `scripts/build_signbank_index.py`) |
| `asl_util/pipeline.py` | Video → timestamped signs |
| `templates/`, `static/` | Web pages (`index.html`, and `pose_prototype.html` for the 2D figure), styles and fingerspelling images |
| `scripts/` | Rebuild the gloss list; make animations from local video files |
| `tests/` | Offline tests (Whisper and Stanza are replaced by fakes) |

## Running it

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt
python app.py            # open http://localhost:5000
```

The Whisper, Stanza and MediaPipe models download on the first upload, so the first request is slow. Each sign's 2D animation is also made the first time that sign appears (about a second per sign) and reused after that.

Settings (environment variables): `SIGNMEUP_WHISPER_MODEL` (default `tiny`), `SIGNMEUP_MAX_UPLOAD_MB` (default 200), `SIGNMEUP_UPLOAD_DIR` (default: the system temp folder), `SIGNMEUP_CACHE_DIR` (where found sign videos and made animations are kept; default: a `signmeup-cache` folder in the system temp folder), `SIGNMEUP_POSE_MODEL` (path to MediaPipe's holistic model; downloaded into the cache folder if not set).

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
                          "source": "ASL Signbank (CC BY-NC-SA 4.0)",
                          "pose": "/poses/482.json"}},
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

`media` is `null` when there is no video for a sign; the page then shows the gloss as text. `pose` is missing if the animation couldn't be made. `GET /poses/<id>.json` returns an animation made during an earlier upload: a `rest` frame and the signing `frames`, each with `pose` (9 body points), `leftHand`/`rightHand` (21 points each) and `face` (outline points), in shoulder widths from the point between the shoulders.

Errors return `{"error": "..."}` with status 400 (no file), 413 (too large), 415 (unsupported type) or 422 (no speech found or the audio couldn't be transcribed).

## Sign media and licenses

| What | Source | License | How it's used |
|---|---|---|---|
| Sign videos | [ASL Signbank](https://aslsignbank.com) — Hochgesang, J. A., Crasborn, O., & Lillo-Martin, D. (2017–2026). ASL Signbank. https://doi.org/10.6084/m9.figshare.9741788 | [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) | Not copied into this repo. The page plays each video from aslsignbank.com and links to its Signbank entry. |
| Gloss list (`asl_util/data/signbank_glosses.json`) | ASL Signbank's published gloss vocabulary (`asl.ecv`) | CC BY-NC-SA 4.0 | Gloss names and entry IDs only, used to match words to entries. |
| 2D animations (made in the cache folder, not in this repo) | Tracked with [MediaPipe](https://ai.google.dev/edge/mediapipe) from the ASL Signbank videos | CC BY-NC-SA 4.0 (adapted from the videos) | Made the first time a sign is needed, then served from the cache. |
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
- MediaPipe

## History
Built at Hello World 2025 by the SignMeUp team ([original repo](https://github.com/ShlokShar/SignMeUp)) — Winner Gold Track (3rd Place) 🥉

This fork continues the project after the hackathon. Changes so far:
- Split the pipeline into tested modules and load the models once instead of on every upload
- Keep Whisper's timestamps so each sign can be shown when its phrase is spoken
- Store uploads under random names (the original used the uploaded filename as a path), limit file size and type, and delete uploads after processing
- Added offline tests
- Replaced the ASL-LEX handshape image (which showed only the hand shape, not the sign) with ASL Signbank sign videos, and added public-domain fingerspelling images
- Added a 2D animated signer (prototype page) built from the Signbank videos with MediaPipe, paced to keep up with speech
- Timed each sign by when its word is spoken (Whisper word timestamps), so no sign appears before its word is said
- Replaced the word-order rule: spoken order, with question words moved to the end of questions

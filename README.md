# SignMeUp - The ASL Subtitle

SignMeUp bridges the gap for deaf and hard-of-hearing viewers by turning English captions into ASL subtitles, making stories, lessons, and conversations truly accessible to everyone.

## What it does
A user uploads a video. SignMeUp transcribes its audio with OpenAI's Whisper model, keeping the time each phrase was spoken. Each phrase goes through an English-to-ASL translation step that reorders it and applies ASL grammar rules. The resulting signs are matched against the ASL-LEX database to find sign images, which are overlaid on the video as ASL subtitles.

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
| `asl_util/pipeline.py` | Video → timestamped signs |
| `templates/`, `static/` | Web page, styles and the ASL-LEX data |
| `tests/` | Offline tests (Whisper and Stanza are replaced by fakes) |

## Running it

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt
python app.py            # open http://localhost:5000
```

The Whisper and Stanza models download on the first upload, so the first request is slow.

Settings (environment variables): `SIGNMEUP_WHISPER_MODEL` (default `tiny`), `SIGNMEUP_MAX_UPLOAD_MB` (default 200), `SIGNMEUP_UPLOAD_DIR` (default: the system temp folder).

### API

`POST /upload` with a `file` form field (mp4, mov, m4v, webm, mkv, mp3, wav or m4a) returns:

```json
{
  "transcript": "Hello Aadi. The cat is sleeping.",
  "segments": [
    {"start": 0.0, "end": 2.5, "text": "Hello Aadi.",
     "signs": [{"text": "hello", "gloss": "hello", "kind": "sign"},
               {"text": "a", "gloss": "a", "kind": "fingerspell"},
               {"text": "a", "gloss": "a", "kind": "fingerspell"},
               {"text": "d", "gloss": "d", "kind": "fingerspell"},
               {"text": "i", "gloss": "i", "kind": "fingerspell"}]},
    {"start": 2.5, "end": 5.0, "text": "The cat is sleeping.",
     "signs": [{"text": "sleeping", "gloss": "sleep", "kind": "sign"},
               {"text": "cat", "gloss": "cat", "kind": "sign"}]}
  ],
  "result": "hello a a d i sleep cat"
}
```

Errors return `{"error": "..."}` with status 400 (no file), 413 (too large), 415 (unsupported type) or 422 (no speech found or the audio couldn't be transcribed).

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
- ASL-LEX

## History
Built at Hello World 2025 by the SignMeUp team ([original repo](https://github.com/ShlokShar/SignMeUp)) — Winner Gold Track (3rd Place) 🥉

This fork continues the project after the hackathon. Changes so far:
- Split the pipeline into tested modules and load the models once instead of on every upload
- Keep Whisper's timestamps so each sign can be shown when its phrase is spoken
- Store uploads under random names (the original used the uploaded filename as a path), limit file size and type, and delete uploads after processing
- Added offline tests

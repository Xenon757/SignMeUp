# SignMeUp - The ASL Subtitle

SignMeUp bridges the gap for deaf and hard-of-hearing viewers by turning English captions into ASL subtitles, making stories, lessons, and conversations truly accessible to everyone.

## What it does
A user uploads a video or audio file. SignMeUp transcribes it with OpenAI's Whisper model, keeping the time each word was spoken. Each sentence goes through an English-to-ASL translation step that applies ASL grammar rules, and the page signs it with a 2D animated figure built from reference videos on [ASL Signbank](https://aslsignbank.com). Like a TV sign language interpreter, the figure sits in a solid box in a corner of the video (any corner, three sizes); it can also be shown side by side with the video, which is the default on phones and for audio. A full-screen mode keeps the signer and subtitles on screen. While the file is processed, the page shows each real stage (uploading, transcribing, translating sentence by sentence, preparing the sign animations word by word). The layout stacks on phones so the video and the figure fit on one screen.

Dictionary videos are too slow to keep up with speech (each one starts and ends with the hands at rest, and runs about 2.5 seconds), so the figure plays only the part of each sign where the hands are moving, and moves straight from one sign into the next. Each sentence is signed in one of two modes. When the speech is slow enough, each sign is lined up with its word (starting within half a second of it). In fast stretches, it works like closed captions instead: the sentence's signs start when the sentence starts and share the time until the next one. Signs play at 1.5×, and up to 3× when needed. Under the figure, the sentence being signed is shown with the current word highlighted. Words with no sign are fingerspelled, shown as a row of letter handshapes that is never sped up.

Tracked points are smoothed over time (a Gaussian over about 3 frames), which cuts finger jitter by about two thirds on the test video's signs. When the hands overlap, the tracker sometimes reports one hand as both; that duplicate is removed and the hidden hand is found again by running MediaPipe's hand model on a zoomed-in crop around its wrist. Hands are drawn as solid shapes with fingers in depth order, the nearer arm and hand in front, and the palm is shaded differently from the back of the hand so palm orientation is visible. `/compare` plays any animated sign's Signbank video next to its animation, frame by frame, to check accuracy.

An **Optimize for ASL** button slows the video down (keeping the audio's pitch) so the signs have more time. It picks the fastest speed at which 90% of sentences can be signed at a comfortable pace, and never goes below 0.5×. The 30-second test video is dense enough that it uses 0.5×; at that speed 10 of its 12 sentences line up with the speech, against 4 at normal speed.

## How the translation works
ASL is not English word-for-word, so the text is parsed with [Stanza](https://stanfordnlp.github.io/stanza/) (part-of-speech tags, base word forms and dependency relations) and these rules are applied:

- Articles, forms of "to be", auxiliaries and prepositions are dropped ("The cat is sleeping on the mat" → `CAT SLEEP MAT`).
- Words are signed in their base form ("running" → `RUN`). Verbs the parser tags as already being in base form are kept as written, which avoids mix-ups like "bore" → `BEAR`.
- Negation is always signed ("don't know" → `NOT KNOW`, "no matter" → `NO MATTER`), and so are quantifiers like `ALL`, `SOME` and `MANY`.
- Subject pronouns are dropped because ASL usually implies them. Question words are kept even as subjects ("Who called?" → `CALL WHO`).
- Words keep their spoken order, since ASL's basic order is subject–verb–object like English. In a question, the question word moves to the end ("What is your name?" → `YOUR NAME WHAT`).

Words are only ever moved later in a sentence, never earlier. Signs appear once their word has been spoken, so moving a word earlier would make the signing wait for it. (The original version grouped words by their parse, which often put a sentence's last word first and held up the whole sentence.)
- Names are fingerspelled letter by letter.
- Numerals become number words ("42" → `FORTY-TWO`).

## Project layout

| Path | What it does |
|---|---|
| `app.py` | Flask app: serves the React app, the jobs API (`/api/jobs`), `POST /upload`, sign animations (`/poses/`) and `GET /healthz` |
| `asl_util/jobs.py` | Runs uploads in the background, one at a time, and tracks their progress |
| `asl_util/transcribe.py` | Whisper speech-to-text, returning timestamped segments |
| `asl_util/translate.py` | English → ASL rules (pure functions) and the Stanza parser wrapper |
| `asl_util/signbank.py` | Finds the ASL Signbank video for each sign, and the letter image for fingerspelling |
| `asl_util/poses.py` | Turns a sign video into a 2D animation (MediaPipe tracking, trimming, shoulder-relative coordinates) and caches it |
| `asl_util/data/` | ASL Signbank's gloss list (rebuilt with `scripts/build_signbank_index.py`) |
| `asl_util/pipeline.py` | Video → timestamped signs |
| `frontend/` | The web page: React + TypeScript (Vite). `src/signer/` draws the figure and times the signs (with Vitest tests), `src/pages/` has the home and compare pages |
| `static/` | Images served by Flask, including the fingerspelling handshapes |
| `scripts/` | Rebuild the gloss list; make animations from local video files |
| `tests/` | Offline tests (Whisper and Stanza are replaced by fakes) |

## Running it

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt
(cd frontend && npm install && npm run build)    # builds the page into frontend/dist
flask --app "app:create_app()" run --port 5001   # open http://localhost:5001
```

To work on the page with live reloading, keep Flask running and start Vite's dev server in `frontend/` with `npm run dev`; it forwards API requests to Flask on port 5001.

The Whisper, Stanza and MediaPipe models download on the first upload, so the first request is slow. Each sign's 2D animation is also made the first time that sign appears (about a second per sign) and reused after that.

Settings (environment variables): `SIGNMEUP_WHISPER_MODEL` (default `tiny`), `SIGNMEUP_MAX_UPLOAD_MB` (default 200), `SIGNMEUP_UPLOAD_DIR` (default: the system temp folder), `SIGNMEUP_CACHE_DIR` (where found sign videos and made animations are kept; default: a `signmeup-cache` folder in the system temp folder), `SIGNMEUP_POSE_MODEL` (path to MediaPipe's holistic model; downloaded into the cache folder if not set).

### API

`POST /api/jobs` with a `file` form field starts processing in the background and returns `202` with a job id. `GET /api/jobs/<id>` returns its `status` (`queued`, `transcribing`, `translating`, `animating`, `done` or `error`), progress counts (`done`, `total`) while it runs, and `result` (below) when done. Jobs run one at a time; a queued job reports how many are `ahead` of it.

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

There is one segment per sentence, timed from its first to its last word (Whisper's own segments can hold several sentences). A sign's `start` is when its English word was spoken, and `start_char` is where that word starts in the sentence's `text`. `media` is `null` when there is no video for a sign; the page then shows the gloss as text. `pose` is missing if the animation couldn't be made. `GET /poses/<id>.json` returns an animation made during an earlier upload: a `rest` frame and the signing `frames`, each with `pose` (9 body points), `leftHand`/`rightHand` (21 points each) and `face` (outline points), in shoulder widths from the point between the shoulders.

Errors return `{"error": "..."}` with status 400 (no file), 413 (too large), 415 (unsupported type) or 422 (no speech found or the audio couldn't be transcribed).

## Sign media and licenses

| What | Source | License | How it's used |
|---|---|---|---|
| Sign videos | [ASL Signbank](https://aslsignbank.com) — Hochgesang, J. A., Crasborn, O., & Lillo-Martin, D. (2017–2026). ASL Signbank. https://doi.org/10.6084/m9.figshare.9741788 | [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) | Not copied into this repo. The page plays each video from aslsignbank.com and links to its Signbank entry. |
| Gloss list (`asl_util/data/signbank_glosses.json`) | ASL Signbank's published gloss vocabulary (`asl.ecv`) | CC BY-NC-SA 4.0 | Gloss names, entry IDs and English translations, used to match words to entries. |
| 2D animations (made in the cache folder, not in this repo) | Tracked with [MediaPipe](https://ai.google.dev/edge/mediapipe) from the ASL Signbank videos | CC BY-NC-SA 4.0 (adapted from the videos) | Made the first time a sign is needed, then served from the cache. |
| Fingerspelling images (`static/img/fingerspelling/`) | [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Sign_language_A.svg), from wpclipart.com | Public domain | Bundled unmodified. See `CREDITS.md` there. |

How a word is matched: Signbank glosses are uppercase English words, and a lowercase or digit suffix marks a variant (`CATf`, `CAT8`). Signbank also lists English translations for each entry. A word is matched, best first, to:

1. a gloss named after it, then its variants;
2. a reviewed choice for common words whose sign has another name ("you" → `IX`, "my" → `POSS_1`, "already" → `FINISH`), listed in `asl_util/data/sign_choices.json`. Every choice is one of the entries Signbank lists the word under (a test checks this). They were picked by the developers, not by a fluent signer;
3. an entry that lists the word as a translation *and* is from the same word family ("limitation" → `LIMIT`, "phone" → `MOBILE-PHONE`). Translations alone aren't trusted, because they also link loosely related or opposite signs ("ever" is listed under `NEVER`).

The first candidate (of up to four) with a video that can be animated is used. Words with no match are fingerspelled, as ASL does for words without a sign; numbers are not. Of the 1,437 distinct signed words among the 2,000 most common English words ([wordfreq](https://github.com/rspeer/wordfreq)), 75% have a Signbank match with these rules, up from 59% with gloss names alone. In the 30-second test video, 64 of 68 words are animated and the other 4 are fingerspelled.

The video's address isn't part of the gloss list, so the server reads the entry's page the first time a sign is needed and caches the result.

Because the Signbank material is licensed for non-commercial use only, this project is non-commercial.

Other sources that were checked and not used: ASL-LEX's sign videos are © ASL-LEX.org (only its database is openly licensed), ASL Citizen and WLASL are licensed for research use only, and Lifeprint and similar dictionary sites don't allow reuse in apps.

## Tests

```bash
pytest                       # Python: translation, pipeline, tracking clean-up, jobs, endpoints
(cd frontend && npm test)    # TypeScript: sign timing and frame blending
```

The tests run offline in under a second: hand-built parses check each translation rule, and fake models check the upload endpoint, including that an uploaded filename like `../../app.py` can't write outside the upload folder.

## Built with
- Flask
- React, TypeScript and Vite
- PyTorch
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
- Timed each sentence and sign with Whisper's word timestamps, and sign sentence by sentence like closed captions
- Replaced the word-order rule: spoken order, with question words moved to the end of questions
- Signed negation and quantifiers (previously dropped), and fixed base-form verbs being mis-lemmatized ("bore" → `BEAR`)
- Matched more words to signs (Signbank translations of the same word family, plus reviewed choices for common words like pronouns), and fingerspelled the rest
- Rebuilt the web page in React around the 2D signer, with real processing progress (a background jobs API), audio uploads and a phone layout

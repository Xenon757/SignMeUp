"""SignMeUp web app: upload a video, get ASL sign subtitles back."""

from __future__ import annotations

import logging
import os
import re
import tempfile
import threading
import uuid
from pathlib import Path

import flask
from werkzeug.utils import secure_filename

from asl_util.demo import DemoTranscriber, demo_info
from asl_util.jobs import JobFailed, JobRunner
from asl_util.pipeline import translate_video
from asl_util.poses import PoseStore
from asl_util.signbank import GlossIndex, SignMedia, VideoResolver
from asl_util.transcribe import TranscriptionError, WhisperTranscriber
from asl_util.translate import Sign, StanzaGlosser

# The React app (frontend/), built with `npm run build`.
FRONTEND_DIST = Path(__file__).resolve().parent / "frontend" / "dist"

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".mp3", ".wav", ".m4a"}
MAX_UPLOAD_MB = int(os.environ.get("SIGNMEUP_MAX_UPLOAD_MB", "200"))

# Signs looped on the landing page, picked by eye for clear, readable animations
# (hands near the face or chest, steady tracking).
PREVIEW_WORDS = ["hello", "elephant", "thank", "drink", "friend"]

# A word typed on the compare page: letters, with hyphens, apostrophes or spaces between them.
WORD = re.compile(r"[a-z]+(?:['\- ][a-z]+)*")

log = logging.getLogger("signmeup")


def all_animated(result: dict) -> bool:
    """True if every sign with a Signbank video got its 2D animation."""
    return all(
        "pose" in sign["media"]
        for segment in result["segments"]
        for sign in segment["signs"]
        if sign.get("media") and sign["media"].get("type") == "video"
    )


def create_app(
    transcriber=None, glosser=None, upload_dir: str | None = None, media=None, poses=None, frontend_dir=None
) -> flask.Flask:
    """Build the app. Tests pass in fake models so nothing heavy loads."""
    app = flask.Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024

    # Models load lazily on the first upload and are shared by every request after.
    transcriber = transcriber or WhisperTranscriber(os.environ.get("SIGNMEUP_WHISPER_MODEL", "tiny"))
    glosser = glosser or StanzaGlosser()
    uploads = Path(upload_dir or os.environ.get("SIGNMEUP_UPLOAD_DIR", tempfile.gettempdir())) / "signmeup"
    uploads.mkdir(parents=True, exist_ok=True)
    # Sign videos are looked up on ASL Signbank once per sign, and turned into 2D pose
    # animations the first time each sign is needed. Both are cached on disk.
    cache_dir = Path(os.environ.get("SIGNMEUP_CACHE_DIR", Path(tempfile.gettempdir()) / "signmeup-cache"))
    poses = poses or PoseStore(cache_dir / "poses")
    media = media or SignMedia(GlossIndex.load(), VideoResolver(cache_dir / "signbank_videos.json"), poses)

    jobs = JobRunner()
    frontend = Path(frontend_dir or FRONTEND_DIST)

    def error(message: str, status: int):
        return flask.jsonify({"error": message}), status

    def save_upload():
        """Check and save the uploaded file. Returns (path, None) or (None, error response)."""
        file = flask.request.files.get("file")
        if file is None:
            return None, error("No file was uploaded. Send the video in a form field named 'file'.", 400)
        if not file.filename:
            return None, error("No file selected.", 400)
        suffix = Path(secure_filename(file.filename)).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
            return None, error(f"Unsupported file type '{suffix or 'none'}'. Upload one of: {allowed}.", 415)
        # Never trust the uploaded name as a path: store under a random name instead.
        path = uploads / f"{uuid.uuid4().hex}{suffix}"
        file.save(path)
        return path, None

    @app.get("/")
    @app.get("/demo")
    @app.get("/compare")
    def page():
        # The React app handles both pages; it picks one from the URL.
        if not (frontend / "index.html").exists():
            return (
                "<h1>SignMeUp</h1><p>The web page hasn't been built yet. Run <code>npm install</code> and "
                "<code>npm run build</code> in <code>frontend/</code>, then reload.</p>",
                503,
            )
        return flask.send_from_directory(frontend, "index.html", max_age=0)

    @app.get("/assets/<path:name>")
    def frontend_asset(name: str):
        # Built files have a content hash in their names, so they can be cached for long.
        return flask.send_from_directory(frontend / "assets", name, max_age=31536000)

    @app.get("/poses/")
    def pose_list():
        # Animations already made, for the comparison page.
        return flask.jsonify(poses.animations())

    @app.get("/poses/<int:entry_id>.mp4")
    def pose_video(entry_id: int):
        # The source video of an animated sign, served locally so the browser can seek in it.
        path = poses.video_path(entry_id)
        if path is None:
            return error("No video for this sign.", 404)
        return flask.send_file(path, mimetype="video/mp4", conditional=True, max_age=86400)

    @app.get("/poses/<int:entry_id>.json")
    def pose(entry_id: int):
        # Only animations already made during an upload are served; this never starts tracking.
        if not poses.has_animation(entry_id):
            return error("No animation for this sign.", 404)
        return flask.send_file(poses.path(entry_id), mimetype="application/json", max_age=86400)

    preview: list = []  # the landing page's signs, kept once all are animated
    preview_lock = threading.Lock()

    @app.get("/api/preview")
    def preview_signs():
        """The landing page's example signs, making their animations the first time."""
        with preview_lock:  # so two first visitors don't make the same animations twice
            if not preview:
                found = media.for_signs([Sign(w, w, "sign") for w in PREVIEW_WORDS])
                signs = [{"gloss": m["gloss"], "pose": m["pose"]} for m in found if m and "pose" in m]
                if len(signs) < len(PREVIEW_WORDS):
                    return flask.jsonify(signs)  # try the missing ones again next time
                preview.extend(signs)
        return flask.jsonify(preview)

    @app.get("/api/sign")
    def look_up_sign():
        """Find a word's ASL Signbank sign and make its animation if needed (for the compare page)."""
        word = " ".join(flask.request.args.get("word", "").lower().split())
        if not word or len(word) > 40 or not WORD.fullmatch(word):
            return error("Type a single English word (letters only), like 'hello'.", 400)
        found = media.for_sign(Sign(word, word.replace(" ", "-"), "sign"))
        if not found:
            # Try the base form an upload would sign ("running" -> RUN).
            for sign in glosser.to_signs(word):
                if sign.kind == "sign" and sign.gloss != word:
                    found = media.for_sign(sign)
                    if found:
                        break
        if not found:
            return error(f"ASL Signbank has no sign for '{word}'. In a video it would be fingerspelled.", 404)
        if "pose" not in found:
            return error(f"Found {found['gloss']} on ASL Signbank, but its video couldn't be animated.", 422)
        return flask.jsonify({"word": word, **{k: found[k] for k in ("gloss", "id", "pose", "page")}})

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.post("/api/jobs")
    def start_job():
        """Start processing an upload in the background; poll GET /api/jobs/<id> for progress."""
        path, failed = save_upload()
        if failed:
            return failed

        def process(report):
            try:
                result = translate_video(path, transcriber, glosser, media, progress=report)
            except TranscriptionError as exc:
                log.warning("Transcription failed: %s", exc)
                raise JobFailed(str(exc)) from exc
            if not result["segments"]:
                raise JobFailed("No speech was found in this file.")
            return result

        job_id = jobs.submit(process, cleanup=lambda: path.unlink(missing_ok=True))
        return flask.jsonify(jobs.status(job_id)), 202

    demo_result: dict = {}  # the demo's result, kept after the first run

    @app.post("/api/demo")
    def start_demo():
        """Sign the built-in demo (Me at the zoo). Same job flow as an upload; instant once done."""

        def process(report):
            if demo_result:
                return demo_result
            result = translate_video(None, DemoTranscriber(), glosser, media, progress=report)
            # Keep it only if every sign got its animation, so a failed one is retried next time.
            if all_animated(result):
                demo_result.update(result)
            return result

        status = jobs.status(jobs.submit(process))
        return flask.jsonify({**status, "demo": demo_info()}), 202

    @app.get("/api/jobs/<job_id>")
    def job_status(job_id: str):
        status = jobs.status(job_id)
        if status is None:
            return error("No such job. It may have finished more than an hour ago.", 404)
        return flask.jsonify(status)

    @app.post("/upload")
    def upload():
        """Process an upload and return the result in one request (simple API clients)."""
        path, failed = save_upload()
        if failed:
            return failed
        file = flask.request.files["file"]
        try:
            result = translate_video(path, transcriber, glosser, media)
        except TranscriptionError as exc:
            log.warning("Transcription failed: %s", exc)
            return error(str(exc), 422)
        except Exception:
            log.exception("Unexpected error while processing upload")
            return error("Something went wrong while processing the video. Please try again.", 500)
        finally:
            path.unlink(missing_ok=True)

        if not result["segments"]:
            return error("No speech was found in this file.", 422)
        return flask.jsonify({"message": "File processed", "filename": secure_filename(file.filename), **result})

    @app.errorhandler(413)
    def too_large(_exc):
        return error(f"File is too large. The limit is {MAX_UPLOAD_MB} MB.", 413)

    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    create_app().run(debug=os.environ.get("FLASK_DEBUG") == "1")

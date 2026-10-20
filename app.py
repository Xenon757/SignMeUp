"""SignMeUp web app: upload a video, get ASL sign subtitles back."""

from __future__ import annotations

import logging
import os
import tempfile
import uuid
from pathlib import Path

import flask
from werkzeug.utils import secure_filename

from asl_util.pipeline import translate_video
from asl_util.transcribe import TranscriptionError, WhisperTranscriber
from asl_util.translate import StanzaGlosser

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".mp3", ".wav", ".m4a"}
MAX_UPLOAD_MB = int(os.environ.get("SIGNMEUP_MAX_UPLOAD_MB", "200"))

log = logging.getLogger("signmeup")


def create_app(transcriber=None, glosser=None, upload_dir: str | None = None) -> flask.Flask:
    """Build the app. Tests pass in fake models so nothing heavy loads."""
    app = flask.Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024

    # Models load lazily on the first upload and are shared by every request after.
    transcriber = transcriber or WhisperTranscriber(os.environ.get("SIGNMEUP_WHISPER_MODEL", "tiny"))
    glosser = glosser or StanzaGlosser()
    uploads = Path(upload_dir or os.environ.get("SIGNMEUP_UPLOAD_DIR", tempfile.gettempdir())) / "signmeup"
    uploads.mkdir(parents=True, exist_ok=True)

    def error(message: str, status: int):
        return flask.jsonify({"error": message}), status

    @app.get("/")
    def home():
        return flask.render_template("index.html")

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.post("/upload")
    def upload():
        file = flask.request.files.get("file")
        if file is None:
            return error("No file was uploaded. Send the video in a form field named 'file'.", 400)
        if not file.filename:
            return error("No file selected.", 400)

        suffix = Path(secure_filename(file.filename)).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
            return error(f"Unsupported file type '{suffix or 'none'}'. Upload one of: {allowed}.", 415)

        # Never trust the uploaded name as a path: store under a random name instead.
        path = uploads / f"{uuid.uuid4().hex}{suffix}"
        file.save(path)
        try:
            result = translate_video(path, transcriber, glosser)
        except TranscriptionError as exc:
            log.warning("Transcription failed: %s", exc)
            return error(str(exc), 422)
        except Exception:
            log.exception("Unexpected error while processing upload")
            return error("Something went wrong while processing the video. Please try again.", 500)
        finally:
            path.unlink(missing_ok=True)

        if not result["segments"]:
            return error("No speech was found in this video.", 422)
        return flask.jsonify({"message": "File processed", "filename": secure_filename(file.filename), **result})

    @app.errorhandler(413)
    def too_large(_exc):
        return error(f"File is too large. The limit is {MAX_UPLOAD_MB} MB.", 413)

    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    create_app().run(debug=os.environ.get("FLASK_DEBUG") == "1")

"""Download every model SignMeUp needs, so a deployed server never fetches them at runtime.

Used by the Dockerfile at build time; also handy to warm up a local install.

    python scripts/download_models.py MODELS_DIR

- Whisper (faster-whisper, size from SIGNMEUP_WHISPER_MODEL, default "tiny") goes to the
  Hugging Face cache (set HF_HOME to choose where).
- Stanza's English models go to STANZA_RESOURCES_DIR (default ~/stanza_resources).
- MediaPipe's holistic and hand models go to MODELS_DIR/mediapipe; point
  SIGNMEUP_POSE_MODEL at MODELS_DIR/mediapipe/holistic_landmarker.task.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from asl_util.poses import HAND_MODEL_URL, MODEL_URL, download  # noqa: E402
from asl_util.translate import STANZA_PROCESSORS  # noqa: E402


def main() -> None:
    models = Path(sys.argv[1] if len(sys.argv) > 1 else "models")

    from faster_whisper import WhisperModel

    size = os.environ.get("SIGNMEUP_WHISPER_MODEL", "tiny")
    WhisperModel(size, device="cpu", compute_type="int8")  # downloads into the Hugging Face cache
    print(f"Whisper {size}: ready")

    import stanza

    stanza.download("en", processors=STANZA_PROCESSORS, verbose=False)
    print("Stanza English: ready")

    pose_dir = models / "mediapipe"
    for url, name in ((MODEL_URL, "holistic_landmarker.task"), (HAND_MODEL_URL, "hand_landmarker.task")):
        if not (pose_dir / name).exists():
            download(url, pose_dir / name)
    print(f"MediaPipe models: {pose_dir}")


if __name__ == "__main__":
    main()

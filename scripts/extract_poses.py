"""Make pose animations from sign videos on disk, for checking how a sign tracks.

The app does this itself the first time a sign is needed (asl_util/poses.py);
this script runs the same steps on local files.

Usage:
    python scripts/extract_poses.py MODEL.task OUT_DIR VIDEO.mp4 [VIDEO.mp4 ...]

MODEL.task is MediaPipe's holistic landmarker (see asl_util.poses.MODEL_URL).
Each video's file name (without .mp4) is used as its gloss.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from asl_util.poses import build_clip, track_video  # noqa: E402


def main() -> None:
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    model, out_dir, videos = Path(sys.argv[1]), Path(sys.argv[2]), [Path(v) for v in sys.argv[3:]]
    out_dir.mkdir(parents=True, exist_ok=True)
    for video in videos:
        frames, fps, width, height = track_video(video, model)
        clip = build_clip(video.stem, frames, fps, width, height)
        (out_dir / f"{video.stem}.json").write_text(json.dumps(clip, separators=(",", ":")))
        print(f"{video.stem:12} {len(frames) / fps:4.1f}s -> {len(clip['frames']) / fps:4.1f}s signing")


if __name__ == "__main__":
    main()

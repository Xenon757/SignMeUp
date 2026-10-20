"""Turn ASL Signbank sign videos into 2D pose animations (prototype).

For each video, MediaPipe's holistic model tracks the upper body, both hands
and the outline of the face on every frame. We keep those points and mark
the frames where the hands are actually signing, so the player can skip the
hands-at-rest lead-in and lead-out that every dictionary clip has.

The output (static/poses/<GLOSS>.json) is derived from ASL Signbank videos
and is therefore CC BY-NC-SA 4.0, like the videos.

Usage:
    python scripts/extract_poses.py MODEL.task OUT_DIR VIDEO.mp4 [VIDEO.mp4 ...]

MODEL.task is MediaPipe's holistic landmarker:
https://storage.googleapis.com/mediapipe-models/holistic_landmarker/holistic_landmarker/float16/latest/holistic_landmarker.task
Each video's file name (without .mp4) is used as its gloss.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import av
import mediapipe as mp
import numpy as np

# Body points we draw: nose, shoulders, elbows, wrists, hips (MediaPipe pose indices).
POSE_POINTS = [0, 11, 12, 13, 14, 15, 16, 23, 24]

# Face mesh outlines that carry ASL grammar: eyebrows, eyes, mouth, plus the face edge.
FACE_OUTLINES = {
    "oval": [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377,
             152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109],
    "lips": [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 409, 270, 269, 267, 0, 37, 39, 40, 185],
    "leftEye": [263, 249, 390, 373, 374, 380, 381, 382, 362, 398, 384, 385, 386, 387, 388, 466],
    "rightEye": [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246],
    "leftBrow": [276, 283, 282, 295, 285, 300, 293, 334, 296, 336],
    "rightBrow": [46, 53, 52, 65, 55, 70, 63, 105, 66, 107],
}
FACE_POINTS = [i for outline in FACE_OUTLINES.values() for i in outline]

# A hand counts as signing once its wrist rises this fraction of the
# shoulder-to-hip distance above where it rests at the start of the clip.
ACTIVE_RISE = 0.15


def points(landmarks, indices=None):
    if not landmarks:
        return None
    chosen = landmarks if indices is None else [landmarks[i] for i in indices]
    return [[round(p.x, 4), round(p.y, 4)] for p in chosen]


def active_range(frames: list[dict]) -> tuple[int, int]:
    """First and last frame where a hand is raised above its resting height."""
    bodies = [f["pose"] for f in frames if f["pose"]]
    if not bodies:
        return 0, len(frames) - 1
    first = bodies[0]
    # POSE_POINTS order: 0 nose, 1-2 shoulders, 3-4 elbows, 5-6 wrists, 7-8 hips
    shoulder_y = (first[1][1] + first[2][1]) / 2
    hip_y = (first[7][1] + first[8][1]) / 2
    rest_y = min(first[5][1], first[6][1])
    threshold = rest_y - ACTIVE_RISE * abs(hip_y - shoulder_y)

    active = [i for i, f in enumerate(frames) if f["pose"] and min(f["pose"][5][1], f["pose"][6][1]) < threshold]
    if not active:
        return 0, len(frames) - 1
    pad = 2
    return max(0, active[0] - pad), min(len(frames) - 1, active[-1] + pad)


# Where each hand's wrist is in the POSE_POINTS list (left wrist 15, right wrist 16).
WRIST_IN_POSE = {"leftHand": 5, "rightHand": 6}


def fill_hand_gaps(frames: list[dict], start: int, end: int) -> int:
    """Fill frames where hand tracking dropped out (usually motion blur).

    Between two tracked frames the hand is interpolated; before the first or
    after the last one, the nearest tracked hand is moved to follow the wrist.
    Only the signing range is filled; hands at rest are left out.
    Returns how many hands were filled in.
    """
    filled = 0
    for key, wrist in WRIST_IN_POSE.items():
        tracked = [i for i in range(start, end + 1) if frames[i][key]]
        if not tracked:
            continue
        for i in range(start, end + 1):
            if frames[i][key]:
                continue
            before = max((t for t in tracked if t < i), default=None)
            after = min((t for t in tracked if t > i), default=None)
            if before is not None and after is not None:
                a, b = np.array(frames[before][key]), np.array(frames[after][key])
                hand = a + (b - a) * (i - before) / (after - before)
            else:
                near = before if before is not None else after
                hand = np.array(frames[near][key])
                if frames[i]["pose"] and frames[near]["pose"]:
                    hand = hand + np.array(frames[i]["pose"][wrist]) - np.array(frames[near]["pose"][wrist])
            frames[i][key] = np.round(hand, 4).tolist()
            filled += 1
    return filled


def extract(video: Path, landmarker) -> dict:
    container = av.open(str(video))
    stream = container.streams.video[0]
    fps = float(stream.average_rate)
    frames = []
    for n, frame in enumerate(container.decode(stream)):
        rgb = np.ascontiguousarray(frame.to_ndarray(format="rgb24"))
        result = landmarker.detect_for_video(
            mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), int(n * 1000 / fps)
        )
        frames.append(
            {
                "pose": points(result.pose_landmarks, POSE_POINTS),
                # MediaPipe's "left"/"right" are from the signer's point of view.
                "leftHand": points(result.left_hand_landmarks),
                "rightHand": points(result.right_hand_landmarks),
                "face": points(result.face_landmarks, FACE_POINTS),
            }
        )
    width, height = stream.width, stream.height
    container.close()
    start, end = active_range(frames)
    fill_hand_gaps(frames, start, end)
    return {
        "gloss": video.stem,
        "fps": fps,
        "width": width,
        "height": height,
        "start": start,
        "end": end,
        "frames": frames,
    }


def main() -> None:
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    model, out_dir, videos = sys.argv[1], Path(sys.argv[2]), [Path(v) for v in sys.argv[3:]]
    out_dir.mkdir(parents=True, exist_ok=True)

    vision = mp.tasks.vision
    for video in videos:
        # A fresh landmarker per video: VIDEO mode needs timestamps that only increase.
        options = vision.HolisticLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=model),
            running_mode=vision.RunningMode.VIDEO,
        )
        with vision.HolisticLandmarker.create_from_options(options) as landmarker:
            data = extract(video, landmarker)
        missing = sum(1 for f in data["frames"] if not f["pose"])
        (out_dir / f"{data['gloss']}.json").write_text(json.dumps(data, separators=(",", ":")) + "\n")
        total = len(data["frames"]) / data["fps"]
        kept = (data["end"] - data["start"] + 1) / data["fps"]
        print(f"{data['gloss']:12} {total:4.1f}s -> {kept:4.1f}s signing  ({missing} frames without a body)")


if __name__ == "__main__":
    main()

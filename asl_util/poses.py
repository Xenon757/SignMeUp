"""2D sign animations made from ASL Signbank videos.

The first time a sign is needed, its Signbank video is downloaded and
MediaPipe's holistic model tracks the upper body, both hands and the face
outline on every frame. We keep only the frames where the hands are actually
signing (every dictionary clip starts and ends with the hands at rest), fill
short hand-tracking dropouts, and express every point relative to the
signer's shoulders so that signs filmed with different signers and camera
distances line up. The result is cached as JSON and drawn by the page.

Pose files are derived from Signbank videos, so they are CC BY-NC-SA 4.0 too.
They are cached locally and never committed.

Everything except `track_video` is plain Python so it can be tested without
MediaPipe.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import urllib.request
from pathlib import Path
from typing import Callable, List, Optional, Tuple

log = logging.getLogger(__name__)

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/holistic_landmarker/"
    "holistic_landmarker/float16/latest/holistic_landmarker.task"
)
USER_AGENT = "SignMeUp (+https://github.com/Xenon757/SignMeUp)"

# Body points we keep: nose, shoulders, elbows, wrists, hips (MediaPipe pose indices).
# In a stored frame they are at positions 0 nose, 1-2 shoulders, 3-4 elbows, 5-6 wrists, 7-8 hips.
POSE_POINTS = [0, 11, 12, 13, 14, 15, 16, 23, 24]
LEFT_SHOULDER, RIGHT_SHOULDER, LEFT_WRIST, RIGHT_WRIST, LEFT_HIP, RIGHT_HIP = 1, 2, 5, 6, 7, 8

# Face mesh outlines that carry ASL grammar: eyebrows, eyes, mouth, plus the face edge.
# The page reads them back in this order, so keep it in sync with templates/pose_prototype.html.
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

PARTS = ("pose", "leftHand", "rightHand", "face")
WRIST_OF_HAND = {"leftHand": LEFT_WRIST, "rightHand": RIGHT_WRIST}

# A hand counts as signing once its wrist rises this fraction of the
# shoulder-to-hip distance above where it rests at the start of the clip.
ACTIVE_RISE = 0.15
ACTIVE_PAD = 2  # frames kept on each side of the signing range

# Within that range, the sign itself starts once the main hand has risen this
# fraction of the way from rest to its highest point, and ends when it drops
# back below it. Frames outside are the hand travelling to and from the waist.
IN_PLACE = 0.6
# A sign can also start or end by holding still. Frames at either end where the
# main hand moves less than this (shoulder widths per frame) are trimmed too.
HOLD_MOTION = 0.012
MIN_FRAMES = 6  # never trim a sign shorter than this

# Bump when the stored animation format or trimming changes, so cached files are remade.
CLIP_VERSION = 4

# Tracking wobbles a little from frame to frame. Each point is smoothed over time with a
# Gaussian of this spread (in frames). Measured on Signbank clips, sigma 1 cuts finger
# jitter by about 60% while moving points only ~0.03 shoulder widths (about 2 pixels).
SMOOTH_SIGMA = 1.0
SMOOTH_RADIUS = 3

Point = List[float]
Frame = dict  # {"pose": [Point] | None, "leftHand": ..., "rightHand": ..., "face": ...}


def active_range(frames: List[Frame]) -> Tuple[int, int]:
    """First and last frame where a hand is raised above its resting height."""
    bodies = [f["pose"] for f in frames if f["pose"]]
    if not bodies:
        return 0, len(frames) - 1
    first = bodies[0]
    shoulder_y = (first[LEFT_SHOULDER][1] + first[RIGHT_SHOULDER][1]) / 2
    hip_y = (first[LEFT_HIP][1] + first[RIGHT_HIP][1]) / 2
    rest_y = min(first[LEFT_WRIST][1], first[RIGHT_WRIST][1])
    threshold = rest_y - ACTIVE_RISE * abs(hip_y - shoulder_y)

    def raised(f: Frame) -> bool:
        return bool(f["pose"]) and min(f["pose"][LEFT_WRIST][1], f["pose"][RIGHT_WRIST][1]) < threshold

    active = [i for i, f in enumerate(frames) if raised(f)]
    if not active:
        return 0, len(frames) - 1
    return max(0, active[0] - ACTIVE_PAD), min(len(frames) - 1, active[-1] + ACTIVE_PAD)


def _lerp(a: List[Point], b: List[Point], k: float) -> List[Point]:
    return [[va + (vb - va) * k for va, vb in zip(pa, pb)] for pa, pb in zip(a, b)]


def _shift(points: List[Point], dx: float, dy: float) -> List[Point]:
    """Move points in x and y; a depth coordinate, if any, is kept."""
    return [[p[0] + dx, p[1] + dy, *p[2:]] for p in points]


def smooth_over_time(frames: List[Frame], sigma: float = SMOOTH_SIGMA, radius: int = SMOOTH_RADIUS) -> None:
    """Smooth every tracked point over time, in place, to remove frame-to-frame wobble.

    Each part (body, each hand, face) is smoothed separately over each run of
    consecutive frames where it was tracked; the ends of a run are mirrored so
    they don't drift. Runs shorter than 3 frames are left as they are.
    """
    weights = [2.718281828 ** (-0.5 * (i / sigma) ** 2) for i in range(-radius, radius + 1)]
    for part in PARTS:
        i = 0
        while i < len(frames):
            if not frames[i][part]:
                i += 1
                continue
            j = i
            while j < len(frames) and frames[j][part]:
                j += 1
            run = [frames[k][part] for k in range(i, j)]
            if len(run) >= 3:
                n = len(run)
                smoothed = []
                for t in range(n):
                    total, acc = 0.0, None
                    for w, off in zip(weights, range(-radius, radius + 1)):
                        u = t + off
                        u = -u if u < 0 else (2 * (n - 1) - u if u >= n else u)  # mirror at the ends
                        if not 0 <= u < n:
                            continue
                        total += w
                        pts = run[u]
                        acc = [[w * v for v in p] for p in pts] if acc is None else [
                            [a + w * v for a, v in zip(pa, p)] for pa, p in zip(acc, pts)
                        ]
                    smoothed.append([[v / total for v in p] for p in acc])
                for k, pts in zip(range(i, j), smoothed):
                    frames[k][part] = pts
            i = j


def fill_hand_gaps(frames: List[Frame], start: int, end: int) -> int:
    """Fill frames where hand tracking dropped out (usually motion blur).

    Between two tracked frames the hand is interpolated; before the first or
    after the last one, the nearest tracked hand is moved to follow the wrist.
    Only the signing range is filled. Returns how many hands were filled in.
    """
    filled = 0
    for key, wrist in WRIST_OF_HAND.items():
        tracked = [i for i in range(start, end + 1) if frames[i][key]]
        if not tracked:
            continue
        for i in range(start, end + 1):
            if frames[i][key]:
                continue
            before = max((t for t in tracked if t < i), default=None)
            after = min((t for t in tracked if t > i), default=None)
            if before is not None and after is not None:
                hand = _lerp(frames[before][key], frames[after][key], (i - before) / (after - before))
            else:
                near = before if before is not None else after
                hand = frames[near][key]
                if frames[i]["pose"] and frames[near]["pose"]:
                    (x1, y1), (x0, y0) = frames[i]["pose"][wrist], frames[near]["pose"][wrist]
                    hand = _shift(hand, x1 - x0, y1 - y0)
            frames[i][key] = hand
            filled += 1
    return filled


def to_body_space(frames: List[Frame], width: int, height: int, digits: int = 3) -> List[Frame]:
    """Re-express points relative to the signer's shoulders.

    MediaPipe gives x and y as fractions of the video's width and height. We
    convert to pixels (so x and y use the same unit), then put the origin
    between the shoulders on the first tracked frame and use the shoulder
    width as 1 unit. Every sign then has the same body size and position.
    Hand points also carry depth (z, relative to the wrist, smaller = nearer
    the camera, on the same scale as x), converted with the same unit.
    """
    first = next((f["pose"] for f in frames if f["pose"]), None)
    if first is None:
        return frames
    (lx, ly), (rx, ry) = first[LEFT_SHOULDER], first[RIGHT_SHOULDER]
    lx, ly, rx, ry = lx * width, ly * height, rx * width, ry * height
    cx, cy = (lx + rx) / 2, (ly + ry) / 2
    unit = ((lx - rx) ** 2 + (ly - ry) ** 2) ** 0.5 or 1.0

    def convert(points: Optional[List[Point]]) -> Optional[List[Point]]:
        if not points:
            return None
        return [
            [round((p[0] * width - cx) / unit, digits), round((p[1] * height - cy) / unit, digits)]
            + ([round(p[2] * width / unit, digits)] if len(p) > 2 else [])
            for p in points
        ]

    return [{part: convert(f[part]) for part in PARTS} for f in frames]


def _hand_motion(a: Frame, b: Frame, wrist: int, hand: str) -> float:
    """How far the main hand moves between two frames (mean point distance)."""
    if a[hand] and b[hand]:
        pairs = list(zip(a[hand], b[hand]))
    elif a["pose"] and b["pose"]:
        pairs = [(a["pose"][wrist], b["pose"][wrist])]
    else:
        return 0.0
    return sum(((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5 for p, q in pairs) / len(pairs)


def sign_core(frames: List[Frame], rest: Frame) -> Tuple[int, int]:
    """The frames of the sign itself, without the hand's trip up and down or still holds.

    `frames` and `rest` are in body space (y grows downwards). The main hand is
    the one that moves the most. Returns the first and last index to keep.
    """
    if len(frames) <= MIN_FRAMES or not rest or not rest["pose"]:
        return 0, len(frames) - 1
    bodies = [i for i, f in enumerate(frames) if f["pose"]]
    if not bodies:
        return 0, len(frames) - 1
    # The main hand is the one that moves the most over the clip.
    def total_motion(wrist: int, hand: str) -> float:
        return sum(_hand_motion(frames[i], frames[i + 1], wrist, hand) for i in range(len(frames) - 1))

    wrist, hand = max(((LEFT_WRIST, "leftHand"), (RIGHT_WRIST, "rightHand")), key=lambda wh: total_motion(*wh))
    rest_y = rest["pose"][wrist][1]
    top_y = min(frames[i]["pose"][wrist][1] for i in bodies)
    level = rest_y - IN_PLACE * (rest_y - top_y)
    in_place = [i for i in bodies if frames[i]["pose"][wrist][1] <= level]
    if not in_place:
        return 0, len(frames) - 1
    a, b = in_place[0], in_place[-1]
    while b - a + 1 > MIN_FRAMES and _hand_motion(frames[a], frames[a + 1], wrist, hand) < HOLD_MOTION:
        a += 1
    while b - a + 1 > MIN_FRAMES and _hand_motion(frames[b - 1], frames[b], wrist, hand) < HOLD_MOTION:
        b -= 1
    if b - a + 1 < MIN_FRAMES:  # very short signs: widen back out around the core
        extra = MIN_FRAMES - (b - a + 1)
        a = max(0, a - extra // 2)
        b = min(len(frames) - 1, a + MIN_FRAMES - 1)
    return a, b


def build_clip(gloss: str, frames: List[Frame], fps: float, width: int, height: int) -> dict:
    """Turn raw tracked frames into the animation the page plays.

    `rest` is the first frame (hands down), used when nothing is being signed.
    `frames` holds only the sign itself: no lead-in or lead-out with the hands
    at rest, no travel to and from the waist, and no still holds at the ends,
    so the sign is recognisable from its first frame.
    """
    if not any(f["pose"] for f in frames):
        return {"version": CLIP_VERSION, "gloss": gloss, "fps": fps, "rest": None, "frames": []}
    start, end = active_range(frames)
    fill_hand_gaps(frames, start, end)
    smooth_over_time(frames)
    body = to_body_space(frames, width, height)
    rest = next(f for f in body if f["pose"])
    signing = body[start : end + 1]
    a, b = sign_core(signing, rest)
    return {
        "version": CLIP_VERSION,
        "gloss": gloss,
        "fps": round(fps, 3),
        "first_frame": start + a,  # where the kept frames start in the original video
        "rest": rest,
        "frames": signing[a : b + 1],
    }


def track_video(video: Path, model_path: Path) -> Tuple[List[Frame], float, int, int]:
    """Run MediaPipe's holistic model over every frame of a video."""
    import av  # heavy imports, deferred until a pose is actually needed
    import mediapipe as mp
    import numpy as np

    vision = mp.tasks.vision
    options = vision.HolisticLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path)),
        running_mode=vision.RunningMode.VIDEO,
    )

    def points(landmarks, indices=None, depth=False):
        if not landmarks:
            return None
        chosen = landmarks if indices is None else [landmarks[i] for i in indices]
        return [[p.x, p.y, p.z] if depth else [p.x, p.y] for p in chosen]

    frames: List[Frame] = []
    # A new landmarker per video: VIDEO mode needs timestamps that only increase.
    with vision.HolisticLandmarker.create_from_options(options) as landmarker, av.open(str(video)) as container:
        stream = container.streams.video[0]
        fps = float(stream.average_rate or 30)
        for n, frame in enumerate(container.decode(stream)):
            rgb = np.ascontiguousarray(frame.to_ndarray(format="rgb24"))
            result = landmarker.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), int(n * 1000 / fps))
            frames.append(
                {
                    "pose": points(result.pose_landmarks, POSE_POINTS),
                    # MediaPipe's "left"/"right" are from the signer's point of view.
                    "leftHand": points(result.left_hand_landmarks, depth=True),
                    "rightHand": points(result.right_hand_landmarks, depth=True),
                    "face": points(result.face_landmarks, FACE_POINTS),
                }
            )
        width, height = stream.width, stream.height
    return frames, fps, width, height


def download(url: str, dest: Path, timeout: float = 30.0) -> None:
    """Download to a temporary name first so a half-written file is never used."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as resp, open(tmp, "wb") as out:
        while chunk := resp.read(1 << 16):
            out.write(chunk)
    tmp.replace(dest)


Tracker = Callable[[Path, Path], Tuple[List[Frame], float, int, int]]
Downloader = Callable[[str, Path], None]


class PoseStore:
    """Makes and caches the pose animation for each Signbank entry.

    `ensure()` is called during an upload for every sign that has a video. The
    first call for an entry downloads its video, tracks it and saves
    <cache>/<entry_id>.json; later calls just check the file. The MediaPipe
    model is downloaded on first use too, like the Whisper and Stanza models.
    Failures are logged and return False so the sign falls back to text.
    """

    def __init__(
        self,
        cache_dir: Path,
        model_path: Optional[Path] = None,
        download: Downloader = download,
        track: Tracker = track_video,
    ):
        self.cache_dir = cache_dir
        self._model_path = model_path or Path(
            os.environ.get("SIGNMEUP_POSE_MODEL", cache_dir.parent / "models" / "holistic_landmarker.task")
        )
        self._download = download
        self._track = track
        self._model_lock = threading.Lock()

    def path(self, entry_id: int) -> Path:
        return self.cache_dir / f"{entry_id}.json"

    def _cached(self, entry_id: int) -> Optional[dict]:
        """The cached animation, or None if missing, unreadable or made by an older version."""
        try:
            clip = json.loads(self.path(entry_id).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return clip if clip.get("version") == CLIP_VERSION else None

    def has_animation(self, entry_id: int) -> bool:
        """True if a current cached animation exists and has signing frames."""
        clip = self._cached(entry_id)
        return bool(clip and clip["frames"])

    def animations(self) -> List[dict]:
        """Every current cached animation with frames: [{id, gloss, video}], by gloss."""
        found = []
        for path in self.cache_dir.glob("*.json") if self.cache_dir.exists() else []:
            if not path.stem.isdigit():
                continue
            clip = self._cached(int(path.stem))
            if clip and clip["frames"]:
                found.append({"id": int(path.stem), "gloss": clip["gloss"], "video": clip.get("video")})
        return sorted(found, key=lambda a: a["gloss"])

    def video_path(self, entry_id: int) -> Optional[Path]:
        """A local copy of an animated sign's source video, for the comparison page.

        Signbank doesn't serve byte ranges, so its videos can't be seeked in a browser;
        a local copy can. Only signs that already have an animation are fetched.
        """
        clip = self._cached(entry_id)
        if not clip or not clip.get("video"):
            return None
        path = self.cache_dir.parent / "videos" / f"{entry_id}.mp4"
        if not path.exists():
            try:
                self._download(clip["video"], path)
            except Exception as exc:
                log.warning("Could not download the video for %s: %s", entry_id, exc)
                return None
        return path

    def ensure(self, entry_id: int, gloss: str, video_url: str) -> bool:
        if self._cached(entry_id) is not None:
            return self.has_animation(entry_id)
        try:
            self._ensure_model()
            with tempfile.TemporaryDirectory() as tmp:
                video = Path(tmp) / "sign.mp4"
                self._download(video_url, video)
                frames, fps, width, height = self._track(video, self._model_path)
            clip = build_clip(gloss, frames, fps, width, height)
            clip["video"] = video_url
        except Exception as exc:  # network errors, unreadable videos, MediaPipe errors
            log.warning("Could not make a pose animation for %s (%s): %s", gloss, entry_id, exc)
            return False
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        tmp_file = self.path(entry_id).with_suffix(".tmp")
        tmp_file.write_text(json.dumps(clip, separators=(",", ":")), encoding="utf-8")
        tmp_file.replace(self.path(entry_id))
        return bool(clip["frames"])

    def _ensure_model(self) -> None:
        with self._model_lock:
            if not self._model_path.exists():
                log.info("Downloading the MediaPipe holistic model to %s", self._model_path)
                self._download(MODEL_URL, self._model_path)

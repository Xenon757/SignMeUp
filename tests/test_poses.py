"""Tests for turning tracked frames into sign animations. Frames are built by hand;
MediaPipe and the network are replaced by fakes."""

import json

from asl_util.poses import (
    CLIP_VERSION,
    MIN_FRAMES,
    PoseStore,
    active_range,
    build_clip,
    fill_hand_gaps,
    sign_core,
    to_body_space,
)

# A 400x200 video. Shoulders at y=0.4, hips at y=0.9, wrists resting at y=0.9.
SHOULDERS = [[0.6, 0.4], [0.4, 0.4]]   # signer's left shoulder is on the image's right


def frame(wrist_y=0.9, left_hand=None, right_hand=None, body=True):
    if not body:
        return {"pose": None, "leftHand": left_hand, "rightHand": right_hand, "face": None}
    pose = [[0.5, 0.2], *SHOULDERS, [0.65, 0.6], [0.35, 0.6], [0.6, wrist_y], [0.4, wrist_y], [0.58, 0.9], [0.42, 0.9]]
    return {"pose": pose, "leftHand": left_hand, "rightHand": right_hand, "face": None}


def hand(x, y):
    return [[x, y]] * 21


def test_active_range_skips_hands_at_rest():
    frames = [frame()] * 5 + [frame(wrist_y=0.5)] * 4 + [frame()] * 6
    assert active_range(frames) == (5 - 2, 8 + 2)


def test_active_range_keeps_everything_when_hands_never_rise():
    assert active_range([frame()] * 4) == (0, 3)


def test_active_range_without_any_body():
    assert active_range([frame(body=False)] * 3) == (0, 2)


def test_hand_gap_between_tracked_frames_is_interpolated():
    frames = [frame(right_hand=hand(0.0, 0.0)), frame(), frame(right_hand=hand(1.0, 0.5))]
    assert fill_hand_gaps(frames, 0, 2) == 1
    assert frames[1]["rightHand"][0] == [0.5, 0.25]


def test_hand_gap_at_edge_follows_the_wrist():
    frames = [frame(wrist_y=0.5, right_hand=hand(0.4, 0.5)), frame(wrist_y=0.45)]
    fill_hand_gaps(frames, 0, 1)
    assert frames[1]["rightHand"][0][0] == 0.4
    assert abs(frames[1]["rightHand"][0][1] - 0.45) < 1e-9


def test_hand_never_tracked_is_left_empty():
    frames = [frame(), frame()]
    assert fill_hand_gaps(frames, 0, 1) == 0
    assert frames[0]["leftHand"] is None


def test_body_space_centres_on_shoulders_in_shoulder_widths():
    body = to_body_space([frame()], width=400, height=200)[0]["pose"]
    # Shoulders are 80 px apart; the nose is 40 px above the shoulder line.
    assert body[1] == [0.5, 0.0] and body[2] == [-0.5, 0.0]
    assert body[0] == [0.0, -0.5]


def test_body_space_makes_different_framings_match():
    # The same body filmed twice as large and shifted gives the same points.
    near = frame()
    far = {k: v for k, v in near.items()}
    far["pose"] = [[0.25 + x / 2, 0.1 + y / 2] for x, y in near["pose"]]
    assert to_body_space([near], 400, 200)[0]["pose"] == to_body_space([far], 400, 200)[0]["pose"]


def signing_video():
    """Rest, the right hand travelling up, signing (moving side to side), travelling down, rest."""
    up = [frame(wrist_y=y) for y in (0.85, 0.8, 0.7)]
    signing = [frame(wrist_y=0.5, right_hand=hand(0.40 + 0.03 * (i % 2), 0.5)) for i in range(8)]
    down = [frame(wrist_y=y) for y in (0.7, 0.8, 0.85)]
    return [frame()] * 4 + up + signing + down + [frame()] * 4


def test_build_clip_keeps_only_the_sign_itself_and_a_rest_frame():
    clip = build_clip("CAT", signing_video(), fps=24.0, width=400, height=200)
    assert len(clip["frames"]) == 8
    signing_y = clip["frames"][4]["pose"][6][1]
    rest_y = clip["rest"]["pose"][6][1]
    # Every kept frame is near signing height, none travelling (smoothing blends the ends a little).
    assert all(abs(f["pose"][6][1] - signing_y) < 0.25 * (rest_y - signing_y) for f in clip["frames"])
    assert clip["rest"]["pose"][6][1] > clip["frames"][0]["pose"][6][1]  # wrist lower at rest
    assert clip["version"] == CLIP_VERSION


def test_sign_core_trims_still_holds_at_both_ends():
    still = frame(wrist_y=0.5, right_hand=hand(0.4, 0.5))
    moving = [frame(wrist_y=0.5, right_hand=hand(0.40 + 0.03 * (i % 2), 0.5)) for i in range(8)]
    frames = to_body_space([frame()] + [still] * 5 + moving + [still] * 5, 400, 200)
    a, b = sign_core(frames[1:], frames[0])
    assert (a, b) == (5, 13)  # from the first moving frame to where the hand comes to rest


def test_sign_core_keeps_a_minimum_length():
    still = frame(wrist_y=0.5, right_hand=hand(0.4, 0.5))
    frames = to_body_space([frame()] + [still] * 12, 400, 200)
    a, b = sign_core(frames[1:], frames[0])
    assert b - a + 1 == MIN_FRAMES


def test_build_clip_without_body_has_no_frames():
    clip = build_clip("CAT", [frame(body=False)] * 3, fps=24.0, width=400, height=200)
    assert clip["frames"] == []


class FakeTools:
    def __init__(self, frames=None, fail=False):
        self.frames = frames if frames is not None else [frame()] * 3 + [frame(wrist_y=0.5)] * 3 + [frame()] * 3
        self.fail = fail
        self.downloads = []
        self.tracked = 0

    def download(self, url, dest):
        self.downloads.append(url)
        if self.fail:
            raise OSError("offline")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"fake")

    def track(self, video, model):
        self.tracked += 1
        return self.frames, 24.0, 400, 200


def store(tmp_path, tools):
    return PoseStore(tmp_path / "poses", tmp_path / "models" / "m.task", download=tools.download, track=tools.track)


def test_store_makes_each_animation_once(tmp_path):
    tools = FakeTools()
    poses = store(tmp_path, tools)
    assert poses.ensure(1037, "CATf", "https://example/cat.mp4")
    assert poses.ensure(1037, "CATf", "https://example/cat.mp4")
    assert tools.tracked == 1
    assert tools.downloads.count("https://example/cat.mp4") == 1
    assert json.loads(poses.path(1037).read_text())["gloss"] == "CATf"


def test_store_downloads_model_once(tmp_path):
    tools = FakeTools()
    poses = store(tmp_path, tools)
    poses.ensure(1, "A", "https://example/a.mp4")
    poses.ensure(2, "B", "https://example/b.mp4")
    assert sum(1 for url in tools.downloads if url.endswith(".task")) == 1


def test_store_remembers_signs_that_could_not_be_tracked(tmp_path):
    tools = FakeTools(frames=[frame(body=False)] * 3)
    poses = store(tmp_path, tools)
    assert not poses.ensure(5, "X", "https://example/x.mp4")
    assert not poses.ensure(5, "X", "https://example/x.mp4")
    assert tools.tracked == 1


def test_store_remakes_animations_from_an_older_version(tmp_path):
    tools = FakeTools()
    poses = store(tmp_path, tools)
    poses.cache_dir.mkdir(parents=True)
    poses.path(1037).write_text(json.dumps({"gloss": "CATf", "frames": [{}]}))  # no version: old format
    assert not poses.has_animation(1037)
    assert poses.ensure(1037, "CATf", "https://example/cat.mp4")
    assert tools.tracked == 1
    assert json.loads(poses.path(1037).read_text())["version"] == CLIP_VERSION


def test_store_retries_after_download_error(tmp_path):
    poses = store(tmp_path, FakeTools(fail=True))
    assert not poses.ensure(1037, "CATf", "https://example/cat.mp4")
    assert not poses.path(1037).exists()


def test_clip_records_where_it_starts_in_the_original_video():
    clip = build_clip("CAT", signing_video(), fps=24.0, width=400, height=200)
    assert clip["first_frame"] == 7  # 4 rest frames + 3 frames travelling up


def test_store_lists_its_animations(tmp_path):
    poses = store(tmp_path, FakeTools())
    poses.ensure(1037, "CATf", "https://example/cat.mp4")
    assert poses.animations() == [{"id": 1037, "gloss": "CATf", "video": "https://example/cat.mp4"}]


def test_smoothing_reduces_wobble_but_keeps_steady_points():
    from asl_util.poses import smooth_over_time
    wobble = [0.5 + (0.02 if i % 2 else -0.02) for i in range(12)]
    frames = [{"pose": None, "leftHand": None, "face": None, "rightHand": [[0.4, y, 0.0]] * 21} for y in wobble]
    smooth_over_time(frames)
    ys = [f["rightHand"][0][1] for f in frames]
    assert max(ys[3:-3]) - min(ys[3:-3]) < 0.01  # was 0.04
    steady = [{"pose": None, "leftHand": None, "face": None, "rightHand": [[0.4, 0.5, 0.1]] * 21} for _ in range(8)]
    smooth_over_time(steady)
    assert all(abs(f["rightHand"][0][1] - 0.5) < 1e-9 and abs(f["rightHand"][0][2] - 0.1) < 1e-9 for f in steady)


def test_smoothing_leaves_untracked_frames_alone():
    from asl_util.poses import smooth_over_time
    frames = [frame(right_hand=hand(0.4, 0.5)), frame(), frame(right_hand=hand(0.4, 0.6))]
    smooth_over_time(frames)
    assert frames[1]["rightHand"] is None
    assert frames[0]["rightHand"][0] == [0.4, 0.5]  # a run of one frame is left as is


def test_hand_depth_is_kept_in_body_space():
    f = frame(right_hand=[[0.4, 0.5, -0.02]] * 21)
    body = to_body_space([f], width=400, height=200)[0]
    assert body["rightHand"][0][2] == round(-0.02 * 400 / 80, 3)  # same unit as x: shoulder widths

import type { Frame, Point } from '../types';

type HandKey = 'leftHand' | 'rightHand';
// Where each hand's wrist and elbow are in a frame's pose points (see types.ts).
const WRIST: Record<HandKey, number> = { leftHand: 5, rightHand: 6 };
const ELBOW: Record<HandKey, number> = { leftHand: 3, rightHand: 4 };

function lerpPoints(a: Point[] | null, b: Point[] | null, k: number): Point[] | null {
  if (!a) return b;
  if (!b) return a;
  return a.map((p, i) => p.map((v, d) => v + ((b[i]?.[d] ?? v) - v) * k));
}

/**
 * A hand moved onto a frame's arm: its wrist placed on the arm's wrist and turned so it points
 * along the forearm (wrist to middle knuckle in line with elbow to wrist), keeping its shape.
 */
export function handOnArm(hand: Point[], pose: Point[], key: HandKey): Point[] {
  const wrist = pose[WRIST[key]];
  const elbow = pose[ELBOW[key]];
  const forearm = Math.atan2(wrist[1] - elbow[1], wrist[0] - elbow[0]);
  const pointing = Math.atan2(hand[9][1] - hand[0][1], hand[9][0] - hand[0][0]);
  const turn = forearm - pointing;
  const cos = Math.cos(turn), sin = Math.sin(turn);
  return hand.map(p => {
    const dx = p[0] - hand[0][0], dy = p[1] - hand[0][1];
    return [wrist[0] + dx * cos - dy * sin, wrist[1] + dx * sin + dy * cos, ...p.slice(2)];
  });
}

/**
 * Fill in hands a frame is missing from another frame's hands. The tracker doesn't see hands
 * resting at the signer's sides, so rest frames have none; without this, the hands would freeze
 * while easing to rest and then vanish, and the arms would jump. Instead the other frame's
 * handshape hangs from this frame's wrist, so hands move smoothly to and from rest.
 */
export function withHands(frame: Frame, donor: Frame): Frame {
  if (!frame.pose || frame.pose.length <= WRIST.rightHand) return frame; // no arms to hang hands from
  const out = { ...frame };
  for (const key of ['leftHand', 'rightHand'] as HandKey[]) {
    if (out[key]) continue;
    // The same hand from the other frame (easing to or from rest). If it isn't tracked in
    // either (the idle hand in a one-handed sign), a neutral relaxed hand: copying the other
    // hand's shape would wrongly sign with both hands.
    out[key] = handOnArm(donor[key] ?? relaxedHand(key), frame.pose, key);
  }
  return out;
}

// A relaxed, slightly curled right hand in body units (shoulder widths), wrist at the origin,
// pointing down: thumb, then index to pinky, each from its base knuckle to its tip.
const RELAXED_RIGHT: Point[] = [
  [0, 0],
  [0.05, 0.04], [0.085, 0.09], [0.1, 0.14], [0.105, 0.18],
  [0.045, 0.16], [0.05, 0.22], [0.048, 0.26], [0.042, 0.29],
  [0.012, 0.17], [0.012, 0.235], [0.01, 0.28], [0.006, 0.31],
  [-0.018, 0.165], [-0.02, 0.225], [-0.02, 0.265], [-0.018, 0.295],
  [-0.045, 0.15], [-0.05, 0.2], [-0.05, 0.23], [-0.047, 0.255],
];

function relaxedHand(key: HandKey): Point[] {
  return key === 'rightHand' ? RELAXED_RIGHT : RELAXED_RIGHT.map(([x, y]) => [-x, y]);
}

/** A frame `k` of the way (0..1) from `a` to `b`. A hand missing at one end hangs from that end's arm. */
export function lerpFrame(a: Frame | null, b: Frame | null, k: number): Frame | null {
  if (!a || !b) return a || b;
  const from = withHands(a, b);
  const to = withHands(b, a);
  return {
    pose: lerpPoints(from.pose, to.pose, k),
    leftHand: lerpPoints(from.leftHand, to.leftHand, k),
    rightHand: lerpPoints(from.rightHand, to.rightHand, k),
    face: lerpPoints(from.face, to.face, k),
  };
}

/** The frame `progress` (0..1) through a clip, blended between the two nearest recorded frames. */
export function frameAt(frames: Frame[], progress: number): Frame | null {
  const at = Math.max(0, Math.min(frames.length - 1, progress * (frames.length - 1)));
  const i = Math.floor(at);
  return lerpFrame(frames[i], frames[Math.min(frames.length - 1, i + 1)], at - i);
}

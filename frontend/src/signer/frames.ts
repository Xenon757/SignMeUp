import type { Frame, Point } from '../types';

function lerpPoints(a: Point[] | null, b: Point[] | null, k: number): Point[] | null {
  if (!a) return b;
  if (!b) return a;
  return a.map((p, i) => p.map((v, d) => v + ((b[i]?.[d] ?? v) - v) * k));
}

/** A frame `k` of the way (0..1) from `a` to `b`. Parts missing in one frame come from the other. */
export function lerpFrame(a: Frame | null, b: Frame | null, k: number): Frame | null {
  if (!a || !b) return a || b;
  return {
    pose: lerpPoints(a.pose, b.pose, k),
    leftHand: lerpPoints(a.leftHand, b.leftHand, k),
    rightHand: lerpPoints(a.rightHand, b.rightHand, k),
    face: lerpPoints(a.face, b.face, k),
  };
}

/** The frame `progress` (0..1) through a clip, blended between the two nearest recorded frames. */
export function frameAt(frames: Frame[], progress: number): Frame | null {
  const at = Math.max(0, Math.min(frames.length - 1, progress * (frames.length - 1)));
  const i = Math.floor(at);
  return lerpFrame(frames[i], frames[Math.min(frames.length - 1, i + 1)], at - i);
}

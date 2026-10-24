// Shapes of the data the Flask API returns (see app.py and asl_util/).

/** [x, y] or [x, y, z]: body space, origin between the shoulders, 1 unit = shoulder width, y down. */
export type Point = number[];

/** One animation frame. Any part may be missing when it wasn't tracked. */
export interface Frame {
  pose: Point[] | null; // 0 nose, 1-2 shoulders, 3-4 elbows, 5-6 wrists, 7-8 hips
  leftHand: Point[] | null; // signer's left; 21 MediaPipe hand points
  rightHand: Point[] | null;
  face: Point[] | null; // outlines, see FACE_OUTLINES in signer/draw.ts
}

/** A sign's animation, from GET /poses/<id>.json. */
export interface PoseClip {
  version: number;
  gloss: string;
  fps: number;
  first_frame: number; // where `frames` start in the original Signbank video
  rest: Frame | null; // the signer at rest, hands down
  frames: Frame[];
  video?: string;
}

export type Media =
  | { type: 'video'; url: string; gloss: string; page: string; source: string; pose?: string }
  | { type: 'image'; url: string; source: string }
  | { type: 'spell'; letters: string; images: string[]; source: string };

export interface Sign {
  text: string; // the English word
  gloss: string; // what is signed
  kind: 'sign' | 'fingerspell' | 'number' | 'interjection'; // interjections without a sign are only highlighted
  start: number; // when the English word was said, in seconds
  start_char: number | null; // where the word starts in the sentence text
  media?: Media | null;
}

/** One spoken sentence and its signs, in ASL order. */
export interface Segment {
  start: number;
  end: number;
  text: string;
  signs: Sign[];
}

export interface Result {
  transcript: string;
  segments: Segment[];
  result: string;
}

export type Stage = 'queued' | 'transcribing' | 'translating' | 'animating' | 'done' | 'error';

/** GET /api/jobs/<id> */
export interface JobStatus {
  id: string;
  status: Stage;
  stages: Stage[];
  done?: number | null;
  total?: number | null;
  ahead?: number; // jobs ahead in line, while queued
  result?: Result;
  error?: string;
}

/** GET /poses/ */
export interface AnimationInfo {
  id: number;
  gloss: string;
  video: string | null;
}

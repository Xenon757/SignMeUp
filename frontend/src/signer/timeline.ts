// When each sign plays, on the media's clock.
//
// Each sentence is signed in one of two modes:
//  - aligned: when the speech is slow enough, each sign starts as its word is said;
//  - sentence: in fast stretches, like closed captions, the sentence's signs start when it
//    starts and share the time until the next sentence, whatever the word timing.
// Dictionary clips are slower than conversational signing, so signs play at BASE_SPEED, and
// faster (up to MAX_SPEED) when needed.
import type { Frame, PoseClip, Segment } from '../types';
import { frameAt, lerpFrame } from './frames';

export const BASE_SPEED = 1.5;
export const MAX_SPEED = 3;
export const ALIGN_TOLERANCE = 0.5; // a sign may start this many seconds after its word and still count as aligned
export const LAST_SENTENCE_EXTRA = 1.0; // seconds the last sentence may run past the speech
export const BLEND = 0.12; // seconds to blend one sign straight into the next
export const HOLD = 0.4; // in a pause, hold the last sign this long...
export const EASE = 0.3; // ...then ease to or from the resting pose over this long
// Fingerspelling is shown as a row of still handshape pictures, which need time to read, so it
// is never sped up: a spelled word stays up for SPELL_TIME plus a little per letter, and the
// animated signs around it absorb any speed-up instead.
export const SPELL_TIME = 0.8;
export const SPELL_TIME_PER_LETTER = 0.05;
export const UNSIGNED_WORD_TIME = 0.45; // a word with no sign at all: only highlighted in the sentence
// "Optimize for ASL": slow the media until most sentences fit at BASE_SPEED, but not below MIN_RATE.
export const OPTIMIZE_SHARE = 0.9;
export const MIN_RATE = 0.5;

export const spellTime = (letters: number) => SPELL_TIME + SPELL_TIME_PER_LETTER * letters;

/** Signbank marks variants of a sign with a lowercase or digit suffix (THIRTYneut, WALK3). */
export const signName = (gloss: string) => gloss.replace(/[a-z0-9]+$/, '') || gloss;

export type ClipKind = 'pose' | 'spell' | 'word';

/** A sign before it is placed in time. */
export interface DraftClip {
  kind: ClipKind;
  label: string;
  natural: number; // how long it takes at 1x, in media seconds
  word: number; // when its English word is said
  char: number | null; // where that word starts in the sentence
  pose?: PoseClip;
}

export interface Clip extends DraftClip {
  start: number;
  length: number;
  speed: number;
  behind: number; // how late it starts, in media seconds
  mode: 'aligned' | 'sentence';
  text: string; // its sentence
}

type Placement = Pick<Clip, 'start' | 'length' | 'speed' | 'behind'>;

/** How long a clip lasts at a given speed. Fingerspelling always plays at its own pace. */
const lengthAt = (clip: DraftClip, speed: number) => (clip.kind === 'spell' ? clip.natural : clip.natural / speed);

/**
 * A sentence's signs as clips, before timing. `rate` is the media's playback rate: at 0.7 a
 * media-second lasts 1/0.7 real seconds, so a sign needs only 0.7 media-seconds per real second.
 */
export function sentenceClips(seg: Segment, poses: Record<string, PoseClip>, rate = 1): DraftClip[] {
  const own: DraftClip[] = [];
  for (const sign of seg.signs) {
    const media = sign.media;
    const pose = media?.type === 'video' && media.pose ? poses[media.pose] : undefined;
    const last = own.at(-1);
    const word = sign.start ?? seg.start;
    const char = sign.start_char ?? null;
    if (pose?.frames.length && media?.type === 'video') {
      own.push({ kind: 'pose', label: signName(media.gloss), pose, natural: pose.frames.length / pose.fps, word, char });
    } else if (media?.type === 'spell' || (media?.type === 'video' && sign.kind === 'sign' && /^[a-z]+$/i.test(sign.gloss))) {
      // No sign animation for this word: fingerspell it, as ASL does for words without a sign.
      const letters = media.type === 'spell' ? media.letters : sign.gloss;
      own.push({ kind: 'spell', label: letters.toUpperCase(), natural: spellTime(letters.length), word, char });
    } else if (sign.kind === 'fingerspell' && last?.kind === 'spell' && last.word === word) {
      last.label += sign.gloss.toUpperCase(); // letters of the same name
      last.natural = spellTime(last.label.length);
    } else if (sign.kind === 'fingerspell') {
      own.push({ kind: 'spell', label: sign.gloss.toUpperCase(), natural: spellTime(1), word, char });
    } else {
      own.push({ kind: 'word', label: sign.gloss.toUpperCase(), natural: UNSIGNED_WORD_TIME, word, char });
    }
  }
  own.forEach(clip => (clip.natural *= rate));
  return own;
}

/**
 * Try to line each sign up with its word. Each starts when its word is said (or when the
 * previous sign ends) and speeds up, within MAX_SPEED, to finish before the next sign's word.
 * Returns null if a sign would start more than ALIGN_TOLERANCE late or the sentence would run
 * past windowEnd: the sentence is too fast to align.
 */
export function tryAlign(own: DraftClip[], from: number, windowEnd: number): Placement[] | null {
  const placed: Placement[] = [];
  let free = from;
  own.forEach((clip, k) => {
    const start = Math.max(clip.word, free);
    const nextAt = k + 1 < own.length ? Math.max(own[k + 1].word, start) : windowEnd;
    const room = nextAt - start - BLEND / BASE_SPEED;
    const speed = Math.min(MAX_SPEED, Math.max(BASE_SPEED, clip.natural / Math.max(0.05, room)));
    placed.push({ start, speed, length: lengthAt(clip, speed), behind: start - clip.word });
    free = start + lengthAt(clip, speed) + BLEND / speed;
  });
  const late = placed.some(p => p.behind > ALIGN_TOLERANCE);
  return late || free > windowEnd + ALIGN_TOLERANCE ? null : placed;
}

/** Fit all of a sentence's signs, in order, between `from` and windowEnd. */
export function packSentence(own: DraftClip[], from: number, windowEnd: number, sentenceStart: number): Placement[] {
  // Fingerspelling keeps its time; the animated signs share whatever is left.
  const spelling = own.filter(c => c.kind === 'spell').reduce((t, c) => t + c.natural, 0);
  const needed = own.filter(c => c.kind !== 'spell').reduce((t, c) => t + c.natural, 0) + BLEND * (own.length - 1);
  const room = Math.max(0.3, windowEnd - from - spelling);
  const speed = Math.min(MAX_SPEED, Math.max(BASE_SPEED, needed / room));
  let t = from;
  return own.map(clip => {
    const placed = { start: t, speed, length: lengthAt(clip, speed), behind: from - sentenceStart };
    t += placed.length + BLEND / speed;
    return placed;
  });
}

const windowEndOf = (segments: Segment[], i: number) => segments[i + 1]?.start ?? segments[i].end + LAST_SENTENCE_EXTRA;

/** Every sign as a clip on the media's clock. */
export function buildTimeline(segments: Segment[], poses: Record<string, PoseClip>, rate = 1): Clip[] {
  const clips: Clip[] = [];
  let free = 0; // when the previous sentence's signing finishes
  segments.forEach((seg, i) => {
    const own = sentenceClips(seg, poses, rate);
    if (!own.length) return;
    // The sentence has until the next one starts. If the previous one ran over, this one
    // starts late and has less time.
    const windowEnd = windowEndOf(segments, i);
    const aligned = tryAlign(own, free, windowEnd);
    const placed = aligned ?? packSentence(own, Math.max(seg.start, free), windowEnd, seg.start);
    const mode = aligned ? 'aligned' : 'sentence';
    own.forEach((clip, k) => clips.push({ ...clip, ...placed[k], mode, text: seg.text }));
    const last = clips.at(-1)!;
    free = last.start + last.length + BLEND / last.speed;
  });
  return clips;
}

/**
 * "Optimize for ASL": the fastest playback rate at which most sentences (OPTIMIZE_SHARE) can be
 * signed at BASE_SPEED before the next one starts, rounded down to a 0.05 step, never below MIN_RATE.
 */
export function optimalRate(segments: Segment[], poses: Record<string, PoseClip>): number {
  const fits: number[] = [];
  segments.forEach((seg, i) => {
    const own = sentenceClips(seg, poses, 1);
    if (!own.length) return;
    const atBase = own.reduce((t, c) => t + (c.kind === 'spell' ? c.natural : c.natural / BASE_SPEED), 0);
    const blends = (BLEND * (own.length - 1)) / BASE_SPEED;
    fits.push((windowEndOf(segments, i) - seg.start - blends) / atBase); // the rate at which it just fits
  });
  if (!fits.length) return 1;
  fits.sort((a, b) => a - b);
  const rate = fits[Math.floor((1 - OPTIMIZE_SHARE) * fits.length)];
  return Math.min(1, Math.max(MIN_RATE, Math.floor(rate * 20) / 20));
}

const smooth = (k: number) => k * k * (3 - 2 * k);
const firstFrame = (clip?: Clip) => (clip?.kind === 'pose' ? clip.pose!.frames[0] : null);
const lastFrame = (clip?: Clip) => (clip?.kind === 'pose' ? clip.pose!.frames.at(-1)! : null);

/**
 * The pose between clips. If the next sign comes soon, the hands move straight from one sign to
 * the next. In a longer pause they hold briefly, ease down to rest, and rise again just before
 * the next sign, so the sign itself starts on time.
 */
function between(prev: Clip | undefined, next: Clip | undefined, t: number, rest: Frame | null): Frame | null {
  const prevEnd = prev ? prev.start + prev.length : -Infinity;
  const gap = next ? next.start - prevEnd : Infinity;
  const from = lastFrame(prev) || rest;
  const to = firstFrame(next) || from;
  if (prev && next && gap <= HOLD + 2 * EASE) {
    return lerpFrame(from, to, smooth(Math.min(1, Math.max(0, (t - prevEnd) / gap))));
  }
  const since = t - prevEnd;
  let frame = since < HOLD ? from : lerpFrame(from, rest, smooth(Math.min(1, (since - HOLD) / EASE)));
  const until = next ? next.start - t : Infinity;
  if (until < EASE) frame = lerpFrame(frame, to, smooth(1 - until / EASE));
  return frame;
}

/** What the figure shows at media time t, and which clip (if any) is playing. */
export function stateAt(timeline: Clip[], t: number, rest: Frame | null): { frame: Frame | null; clip: Clip | null } {
  for (let i = 0; i < timeline.length; i++) {
    const clip = timeline[i];
    if (t < clip.start) return { frame: between(timeline[i - 1], clip, t, rest), clip: null };
    if (t < clip.start + clip.length) {
      const held = between(timeline[i - 1], clip, clip.start, rest);
      const frame = clip.kind === 'pose' ? frameAt(clip.pose!.frames, (t - clip.start) / clip.length) : held;
      return { frame, clip };
    }
  }
  return { frame: between(timeline.at(-1), undefined, t, rest), clip: null };
}

/** The sentence being spoken at t, shown like a closed caption until the next one starts. */
export const CAPTION_LINGER = 1.5;
export function captionAt(segments: Segment[], t: number): Segment | null {
  const current = segments.filter(s => s.start <= t).at(-1);
  return current && t < current.end + CAPTION_LINGER ? current : null;
}

/** The latest sign started by t, kept a moment after it ends so the highlight doesn't flicker. */
export function latestClip(timeline: Clip[], t: number): Clip | null {
  const latest = timeline.filter(c => c.start <= t).at(-1);
  return latest && t < latest.start + latest.length + HOLD ? latest : null;
}

/** The resting pose to use between signs: the first animation's. */
export const restFrameOf = (poses: Record<string, PoseClip>) => Object.values(poses).find(p => p.rest)?.rest ?? null;

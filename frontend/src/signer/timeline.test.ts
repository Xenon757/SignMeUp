import { describe, expect, it } from 'vitest';
import type { Frame, PoseClip, Segment, Sign } from '../types';
import { frameAt, lerpFrame } from './frames';
import {
  ALIGN_TOLERANCE, BASE_SPEED, MIN_RATE, buildTimeline, captionAt, optimalRate, signName, spellTime, stateAt,
} from './timeline';

const frame = (x: number): Frame => ({ pose: [[x, 0]], leftHand: null, rightHand: null, face: null });

// A one-second animation (24 frames at 24 fps) for every animated sign.
const POSE: PoseClip = { version: 6, gloss: 'X', fps: 24, first_frame: 0, rest: frame(-1), frames: Array.from({ length: 24 }, (_, i) => frame(i)) };
const POSES = { '/poses/1.json': POSE };

const animated = (word: string, start: number, char = 0): Sign => ({
  text: word, gloss: word, kind: 'sign', start, start_char: char,
  media: { type: 'video', url: '', gloss: word.toUpperCase(), page: '', source: '', pose: '/poses/1.json' },
});
const spelled = (word: string, start: number): Sign => ({
  text: word, gloss: word, kind: 'sign', start, start_char: 0,
  media: { type: 'spell', letters: word, images: [], source: '' },
});
const sentence = (start: number, end: number, signs: Sign[], text = 'text'): Segment => ({ start, end, text, signs });

describe('frames', () => {
  it('blends between the two nearest frames', () => {
    expect(lerpFrame(frame(0), frame(10), 0.25)!.pose).toEqual([[2.5, 0]]);
    expect(frameAt([frame(0), frame(10)], 0.5)!.pose).toEqual([[5, 0]]);
  });
});

describe('timeline', () => {
  it('shows sign names without Signbank variant codes', () => {
    expect(signName('THIRTYneut')).toBe('THIRTY');
    expect(signName('WALK3')).toBe('WALK');
    expect(signName('HELLO')).toBe('HELLO');
  });

  it('aligns signs with their words when the speech is slow', () => {
    const segs = [sentence(0, 6, [animated('cat', 0), animated('sleep', 3)])];
    const [a, b] = buildTimeline(segs, POSES);
    expect(a.mode).toBe('aligned');
    expect(a.start).toBe(0);
    expect(b.start).toBe(3);
    expect(a.speed).toBe(BASE_SPEED);
  });

  it('falls back to sentence mode when signs come too fast to align', () => {
    const words = ['a', 'b', 'c', 'd', 'e', 'f'].map((w, i) => animated(w, i * 0.1));
    const segs = [sentence(0, 1, words), sentence(2, 3, [animated('g', 2)])];
    const clips = buildTimeline(segs, POSES);
    expect(clips[0].mode).toBe('sentence');
    expect(clips.some(c => c.behind > ALIGN_TOLERANCE) || clips[0].speed > BASE_SPEED).toBe(true);
  });

  it('never speeds up fingerspelling', () => {
    const words = ['a', 'b', 'c'].map((w, i) => animated(w, i * 0.1));
    const clips = buildTimeline([sentence(0, 1, [...words, spelled('mat', 0.4)])], POSES);
    const spell = clips.find(c => c.kind === 'spell')!;
    expect(spell.length).toBeCloseTo(spellTime(3));
  });

  it('gives each sign less media time when the media is slowed down', () => {
    const segs = [sentence(0, 10, [animated('cat', 0)])];
    const normal = buildTimeline(segs, POSES, 1)[0];
    const slowed = buildTimeline(segs, POSES, 0.5)[0];
    expect(slowed.length).toBeCloseTo(normal.length / 2);
  });

  it('picks a slower rate for dense speech, never below the minimum', () => {
    const relaxed = [sentence(0, 10, [animated('cat', 0)])];
    expect(optimalRate(relaxed, POSES)).toBe(1);
    const dense = [sentence(0, 0.5, ['a', 'b', 'c', 'd'].map(w => animated(w, 0)))];
    expect(optimalRate(dense, POSES)).toBe(MIN_RATE);
  });

  it('plays the right frame of the right clip, and rests between signs', () => {
    const clips = buildTimeline([sentence(0, 10, [animated('cat', 0), animated('dog', 5)])], POSES);
    const mid = stateAt(clips, clips[0].start + clips[0].length / 2, POSE.rest);
    expect(mid.clip).toBe(clips[0]);
    expect(mid.frame!.pose![0][0]).toBeGreaterThan(5);
    expect(stateAt(clips, 3, POSE.rest).frame!.pose).toEqual(POSE.rest!.pose); // long pause: at rest
  });

  it('keeps a caption up until the next sentence', () => {
    const segs = [sentence(0, 2, [], 'one'), sentence(5, 6, [], 'two')];
    expect(captionAt(segs, 1)?.text).toBe('one');
    expect(captionAt(segs, 3)?.text).toBe('one'); // lingers briefly after it ends
    expect(captionAt(segs, 4)).toBeNull();
    expect(captionAt(segs, 5.5)?.text).toBe('two');
  });
});

describe('resting hands', () => {
  const pose = [[0, -0.6], [0.5, 0], [-0.5, 0], [0.6, 0.8], [-0.6, 0.8], [0.6, 1.6], [-0.6, 1.6], [0.3, 1.7], [-0.3, 1.7]];
  const hand = (x: number, y: number) => Array.from({ length: 21 }, (_, i) => [x + (i % 5) * 0.02, y - (i >= 9 ? 0.2 : 0.05)]);
  const signing: Frame = { pose, leftHand: null, rightHand: hand(-0.2, 0.2), face: null };
  const rest: Frame = { pose, leftHand: null, rightHand: null, face: null };

  it('gives a rest frame hands that hang from its wrists', () => {
    const settled = lerpFrame(signing, rest, 1)!;
    expect(settled.rightHand![0]).toEqual(pose[6]); // wrist on the arm's wrist
    expect(settled.rightHand![9][1]).toBeGreaterThan(pose[6][1]); // fingers point down the forearm
    expect(settled.leftHand![0]).toEqual(pose[5]); // never tracked: a relaxed hand hangs there instead
    expect(settled.leftHand![9][1]).toBeGreaterThan(pose[5][1]);
  });

  it('moves the hand smoothly to rest instead of jumping', () => {
    const steps = [0, 0.25, 0.5, 0.75, 1].map(k => lerpFrame(signing, rest, k)!.rightHand![0][1]);
    for (let i = 1; i < steps.length; i++) expect(steps[i]).toBeGreaterThan(steps[i - 1]);
    expect(steps[4] - steps[3]).toBeLessThan(0.6); // no snap at the end
  });
});

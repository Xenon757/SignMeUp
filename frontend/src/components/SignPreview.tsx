import { useEffect, useRef, useState } from 'react';
import { getPose, listAnimations } from '../api';
import { drawFigure } from '../signer/draw';
import { frameAt, lerpFrame } from '../signer/frames';
import { signName } from '../signer/timeline';
import type { PoseClip } from '../types';

// Signs to show first if they've been animated on this server; otherwise any that has.
const FAVOURITES = ['HELLO', 'THANK-YOU', 'NAME', 'WHAT', 'TIME'];
const HOLD = 0.6; // seconds at rest between loops

/**
 * A real sign, looping on the landing page, so visitors see the signer before uploading.
 * Uses animations this server has already made; shows nothing if there are none yet.
 */
export function SignPreview() {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [clips, setClips] = useState<PoseClip[]>([]);
  const [label, setLabel] = useState('');

  useEffect(() => {
    let cancelled = false;
    listAnimations().then(async list => {
      const byName = (g: string) => FAVOURITES.indexOf(signName(g)) + 1 || FAVOURITES.length + 1;
      const picks = [...list].sort((a, b) => byName(a.gloss) - byName(b.gloss)).slice(0, 4);
      const loaded = (await Promise.all(picks.map(p => getPose(p.id).catch(() => null)))).filter(Boolean) as PoseClip[];
      if (!cancelled) setClips(loaded.filter(c => c.frames.length && c.rest));
    });
    return () => { cancelled = true; };
  }, []);

  // Cycle through the signs: ease up from rest, sign at 1.25x, ease back down, pause.
  useEffect(() => {
    const ctx = canvas.current?.getContext('2d');
    if (!ctx || !clips.length) return;
    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    let raf = 0;
    const started = performance.now();
    const ease = 0.35;
    const lengths = clips.map(c => c.frames.length / c.fps / 1.25);
    const cycle = lengths.reduce((t, l) => t + l + 2 * ease + HOLD, 0);
    let shown = '';
    const tick = (now: number) => {
      let t = reduced ? lengths[0] / 2 + ease : ((now - started) / 1000) % cycle;
      let i = 0;
      while (t > lengths[i] + 2 * ease + HOLD) { t -= lengths[i] + 2 * ease + HOLD; i++; }
      const clip = clips[i];
      const s = (k: number) => k * k * (3 - 2 * k);
      let frame;
      if (t < ease) frame = lerpFrame(clip.rest, clip.frames[0], s(t / ease));
      else if (t < ease + lengths[i]) frame = frameAt(clip.frames, (t - ease) / lengths[i]);
      else if (t < 2 * ease + lengths[i]) frame = lerpFrame(clip.frames.at(-1)!, clip.rest, s((t - ease - lengths[i]) / ease));
      else frame = lerpFrame(clip.frames.at(-1)!, clip.rest, 1); // at rest, hands hanging at the sides
      drawFigure(ctx, frame);
      const name = signName(clip.gloss);
      if (name !== shown) { shown = name; setLabel(name); }
      if (!reduced) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [clips]);

  if (!clips.length) return null;
  return (
    <figure className="sign-preview" aria-label={`An animated signer signing ${label}`}>
      <canvas ref={canvas} width={800} height={800} />
      <figcaption>
        <span className="preview-chip">{label}</span>
        <span className="muted small">A real ASL sign, animated from a dictionary video</span>
      </figcaption>
    </figure>
  );
}

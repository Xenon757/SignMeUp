import { useEffect, useRef, useState } from 'react';
import { ApiError, getPose, listAnimations, lookUpSign } from '../api';
import { drawFigure } from '../signer/draw';
import { lerpFrame } from '../signer/frames';
import { signName } from '../signer/timeline';
import type { AnimationInfo, PoseClip } from '../types';

/**
 * A sign's original Signbank video next to the animation made from it, frame-matched, to
 * judge how accurate the tracking is. Any word can be looked up; signs animated so far are listed.
 */
export function ComparePage() {
  const video = useRef<HTMLVideoElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [signs, setSigns] = useState<AnimationInfo[] | null>(null);
  const [id, setId] = useState<number | null>(null);
  const [clip, setClip] = useState<PoseClip | null>(null);
  const [speed, setSpeed] = useState(1);
  const [paused, setPaused] = useState(false);
  const [state, setState] = useState('');
  const [query, setQuery] = useState('');
  const [search, setSearch] = useState<{ busy: boolean; message: string; error: boolean }>({ busy: false, message: '', error: false });

  useEffect(() => {
    listAnimations().then(list => {
      setSigns(list);
      if (list.length) setId(list[0].id);
    });
  }, []);

  useEffect(() => {
    if (id != null) getPose(id).then(setClip);
  }, [id]);

  useEffect(() => {
    if (video.current) video.current.playbackRate = speed;
  }, [speed, clip]);

  // Draw the animation frame matching the video's current frame. The animation keeps only the
  // frames of the sign itself, starting at clip.first_frame in the original video.
  useEffect(() => {
    const el = video.current;
    const ctx = canvas.current?.getContext('2d');
    if (!el || !ctx || !clip) return;
    let raf = 0;
    let shown = '';
    const tick = () => {
      const at = el.currentTime * clip.fps - clip.first_frame;
      const inside = at >= 0 && at <= clip.frames.length - 1;
      const i = Math.max(0, Math.min(clip.frames.length - 1, at));
      const frame = lerpFrame(clip.frames[Math.floor(i)], clip.frames[Math.ceil(i)], i - Math.floor(i));
      drawFigure(ctx, inside ? frame : clip.rest);
      if (!inside) {
        ctx.fillStyle = 'rgba(251,250,247,.6)';
        ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);
      }
      const text = inside ? `Frame ${Math.round(at) + 1} of ${clip.frames.length} kept` : 'Outside the sign (trimmed: hands travelling or at rest)';
      if (text !== shown) { shown = text; setState(text); }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [clip]);

  const lookUp = async (e: React.FormEvent) => {
    e.preventDefault();
    const word = query.trim();
    if (!word || search.busy) return;
    setSearch({ busy: true, message: `Looking up “${word}”… a new sign takes a few seconds to animate.`, error: false });
    try {
      const found = await lookUpSign(word);
      setSigns(list => (list?.some(s => s.id === found.id) ? list : [{ id: found.id, gloss: found.gloss, video: null }, ...(list ?? [])]));
      setId(found.id);
      setSearch({ busy: false, message: `“${found.word}” is signed ${signName(found.gloss)} (ASL Signbank entry ${found.gloss}).`, error: false });
    } catch (err) {
      setSearch({ busy: false, message: err instanceof ApiError ? err.message : 'Could not look up this word. Please try again.', error: true });
    }
  };

  const step = () => {
    const el = video.current;
    if (!el || !clip) return;
    el.pause();
    el.currentTime = Math.min(el.duration, el.currentTime + 1 / clip.fps);
  };

  return (
    <main className="compare">
      <h1>Compare signs</h1>
      <p className="muted">
        The original ASL Signbank video next to the animation made from it, frame by frame, to check how accurate it is.
      </p>
      <form className="word-search" onSubmit={lookUp}>
        <input
          type="search"
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Type any word, like “hello”"
          aria-label="Word to look up"
          maxLength={40}
          autoCapitalize="none"
          spellCheck={false}
        />
        <button type="submit" disabled={search.busy}>{search.busy ? 'Looking up…' : 'Show sign'}</button>
      </form>
      <p className={`search-status small ${search.error ? 'error' : 'muted'}`} role="status">{search.message}</p>
      {id == null ? (
        signs && <p className="muted">No signs have been animated on this server yet. Type a word above, or upload a video on the home page.</p>
      ) : (
        <>
          <div className="controls row">
            <label>
              Sign{' '}
              <select value={id ?? ''} onChange={e => setId(Number(e.target.value))}>
                {signs?.map(s => <option key={s.id} value={s.id}>{s.gloss}</option>)}
              </select>
            </label>
            <label>
              Speed{' '}
              <select value={speed} onChange={e => setSpeed(Number(e.target.value))}>
                <option value={1}>1×</option>
                <option value={0.5}>0.5×</option>
                <option value={0.25}>0.25×</option>
              </select>
            </label>
            <button type="button" onClick={() => (paused ? video.current?.play() : video.current?.pause())}>
              {paused ? 'Play' : 'Pause'}
            </button>
            <button type="button" className="secondary" onClick={step}>Next frame</button>
          </div>
          <div className="stage">
            <section className="pane">
              <h2 className="tag">Signbank video</h2>
              {/* A local copy: Signbank's own server doesn't allow seeking. */}
              <video
                ref={video}
                src={`/poses/${id}.mp4`}
                muted
                loop
                autoPlay
                playsInline
                controls
                onPlay={() => setPaused(false)}
                onPause={() => setPaused(true)}
              />
            </section>
            <section className="pane">
              <h2 className="tag">Animation</h2>
              <canvas ref={canvas} width={1000} height={1000} />
              <p className="muted small">{state}</p>
            </section>
          </div>
          <p className="muted small">
            Source: <a href={`https://aslsignbank.com/dictionary/gloss/${id}.html`} target="_blank" rel="noreferrer">this sign on ASL Signbank</a> (CC BY-NC-SA 4.0)
          </p>
        </>
      )}
    </main>
  );
}

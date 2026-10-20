import { useEffect, useMemo, useRef, useState } from 'react';
import { drawFigure, drawSpelling, preloadLetters } from '../signer/draw';
import type { Clip } from '../signer/timeline';
import { buildTimeline, captionAt, latestClip, optimalRate, restFrameOf, stateAt } from '../signer/timeline';
import type { PoseClip, Segment } from '../types';

interface Props {
  src: string; // object URL of the uploaded file
  audioOnly: boolean;
  segments: Segment[];
  poses: Record<string, PoseClip>;
}

/** The sentence with the word being signed highlighted. */
function Highlighted({ text, char }: { text: string; char: number | null }) {
  const word = char == null ? null : text.slice(char).match(/^[\w'’-]+/);
  if (!word || char == null) return <>{text}</>;
  return (
    <>
      {text.slice(0, char)}
      <mark>{word[0]}</mark>
      {text.slice(char + word[0].length)}
    </>
  );
}

type Layout = 'overlay' | 'side';
type Corner = 'bottom-right' | 'bottom-left' | 'top-right' | 'top-left';
type Size = 'small' | 'medium' | 'large';
interface Prefs { layout: Layout; corner: Corner; size: Size }

const CORNERS: Corner[] = ['bottom-right', 'bottom-left', 'top-right', 'top-left'];
const SIZES: Size[] = ['small', 'medium', 'large'];
const PREFS_KEY = 'signmeup.player';

/**
 * Where the signer goes. By default it sits in a corner box inside the video, like a TV
 * interpreter, on screens wide enough for that box to be readable; phones start side by side
 * (stacked). The viewer's last choice is remembered on this device.
 */
function loadPrefs(): Prefs {
  const wide = typeof window !== 'undefined' && window.matchMedia?.('(min-width: 860px)').matches;
  const fallback: Prefs = { layout: wide ? 'overlay' : 'side', corner: 'bottom-right', size: 'medium' };
  try {
    const saved = JSON.parse(localStorage.getItem(PREFS_KEY) ?? 'null');
    if (!saved) return fallback;
    return {
      layout: saved.layout === 'side' || saved.layout === 'overlay' ? saved.layout : fallback.layout,
      corner: CORNERS.includes(saved.corner) ? saved.corner : fallback.corner,
      size: SIZES.includes(saved.size) ? saved.size : fallback.size,
    };
  } catch {
    return fallback; // storage unavailable (private mode, blocked)
  }
}

function savePrefs(prefs: Prefs) {
  try { localStorage.setItem(PREFS_KEY, JSON.stringify(prefs)); } catch { /* not essential */ }
}

interface View {
  caption: Segment | null;
  latest: Clip | null;
  playing: Clip | null;
}

/** The uploaded video (or audio) next to the signing figure. */
export function Player({ src, audioOnly, segments, poses }: Props) {
  const media = useRef<HTMLVideoElement & HTMLAudioElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const viewer = useRef<HTMLDivElement>(null);
  const [optimized, setOptimized] = useState(false);
  const [prefs, setPrefs] = useState<Prefs>(loadPrefs);
  const [fullscreen, setFullscreen] = useState(false);
  // Audio has no picture to put the signer in, so it is always side by side.
  const layout: Layout = audioOnly ? 'side' : prefs.layout;
  const update = (change: Partial<Prefs>) => setPrefs(p => { const next = { ...p, ...change }; savePrefs(next); return next; });

  // Full screen is for the whole viewer (video, signer and subtitles), not just the video:
  // the browser's own video full screen would leave the signer behind.
  const canFullscreen = typeof document !== 'undefined' && document.fullscreenEnabled;
  useEffect(() => {
    const onChange = () => setFullscreen(document.fullscreenElement === viewer.current);
    document.addEventListener('fullscreenchange', onChange);
    return () => document.removeEventListener('fullscreenchange', onChange);
  }, []);
  const toggleFullscreen = () => {
    if (document.fullscreenElement) document.exitFullscreen();
    else viewer.current?.requestFullscreen().catch(() => {});
  };
  const [view, setView] = useState<View>({ caption: null, latest: null, playing: null });

  const rest = useMemo(() => restFrameOf(poses), [poses]);
  const bestRate = useMemo(() => optimalRate(segments, poses), [segments, poses]);
  const rate = optimized ? bestRate : 1;
  const timeline = useMemo(() => buildTimeline(segments, poses, rate), [segments, poses, rate]);

  // "Optimize for ASL" slows the media down; browsers keep the audio's pitch when doing so.
  useEffect(() => {
    if (!media.current) return;
    media.current.playbackRate = rate;
    media.current.defaultPlaybackRate = rate;
  }, [rate]);

  useEffect(preloadLetters, []);

  // Draw every animation frame from the media's clock. Signing can run past the end of the
  // media, so once it ends the clock keeps going. React state changes only when what's shown
  // in text changes, not on every frame.
  useEffect(() => {
    const el = media.current;
    const ctx = canvas.current?.getContext('2d');
    if (!el || !ctx) return;
    let endedAt: number | null = null;
    let shown = '';
    let raf = 0;
    const onEnded = () => { endedAt = performance.now(); };
    const onRestart = () => { endedAt = null; };
    el.addEventListener('ended', onEnded);
    el.addEventListener('play', onRestart);
    el.addEventListener('seeked', onRestart);

    const tick = () => {
      const t = endedAt === null ? el.currentTime : (el.duration || 0) + ((performance.now() - endedAt) / 1000) * el.playbackRate;
      const { frame, clip } = stateAt(timeline, t, rest);
      drawFigure(ctx, frame);
      if (clip?.kind === 'spell') drawSpelling(ctx, clip.label);
      const latest = latestClip(timeline, t);
      const caption = captionAt(segments, t);
      const key = `${caption?.start}|${latest?.start}|${clip?.start}`;
      if (key !== shown) {
        shown = key;
        setView({ caption, latest, playing: clip });
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      el.removeEventListener('ended', onEnded);
      el.removeEventListener('play', onRestart);
      el.removeEventListener('seeked', onRestart);
    };
  }, [timeline, rest, segments]);

  const summary = useMemo(() => {
    const animated = timeline.filter(c => c.kind === 'pose').length;
    const spelled = timeline.filter(c => c.kind === 'spell').length;
    return `${animated} signs animated${spelled ? `, ${spelled} fingerspelled` : ''}`;
  }, [timeline]);

  const { playing, latest, caption } = view;
  const lag = playing ? playing.behind / rate : 0;
  const pace = playing?.kind === 'spell' ? 'fingerspelling' : playing ? `${playing.speed.toFixed(1)}×` : '';

  return (
    <div className="player">
      <div className="player-controls">
        <button
          type="button"
          className="toggle"
          aria-pressed={optimized}
          onClick={() => setOptimized(o => !o)}
          title="Slow the video down so the signs have time to be read"
        >
          Optimize for ASL
        </button>
        <span className="muted">
          {optimized ? `Playing at ${rate.toFixed(2)}× speed` : bestRate < 1 ? `Suggested: ${bestRate.toFixed(2)}× speed` : 'This video’s pace suits ASL'}
        </span>
      </div>

      {!audioOnly && (
        <div className="player-controls layout-controls">
          <div className="segmented" role="group" aria-label="Where the signer goes">
            <button type="button" aria-pressed={layout === 'overlay'} onClick={() => update({ layout: 'overlay' })}>In the video</button>
            <button type="button" aria-pressed={layout === 'side'} onClick={() => update({ layout: 'side' })}>Side by side</button>
          </div>
          {layout === 'overlay' && (
            <>
              <label>
                Corner{' '}
                <select value={prefs.corner} onChange={e => update({ corner: e.target.value as Corner })}>
                  {CORNERS.map(c => <option key={c} value={c}>{c.replace('-', ' ')}</option>)}
                </select>
              </label>
              <div className="segmented" role="group" aria-label="Signer size">
                {SIZES.map(size => (
                  <button key={size} type="button" aria-pressed={prefs.size === size} onClick={() => update({ size })}>
                    {size[0].toUpperCase() + size.slice(1)}
                  </button>
                ))}
              </div>
            </>
          )}
          {canFullscreen && (
            <button type="button" className="secondary" onClick={toggleFullscreen}>
              {fullscreen ? 'Exit full screen' : 'Full screen'}
            </button>
          )}
        </div>
      )}

      {/* The same elements in every layout (only CSS changes), so the canvas is never re-created. */}
      <div ref={viewer} className={`viewer ${layout} ${prefs.corner} ${prefs.size}`}>
        <div className="media-box" aria-label="Your upload">
          {audioOnly ? (
            <div className="audio-card">
              <span aria-hidden="true">♪</span>
              <audio ref={media} src={src} controls preload="auto" />
            </div>
          ) : (
            <video ref={media} src={src} controls playsInline preload="auto" />
          )}
        </div>
        <div className="signer-box" aria-label="ASL signing">
          <canvas ref={canvas} width={1000} height={1000} role="img" aria-label={playing ? `Signing ${playing.label}` : 'Signer'} />
          {/* The sign being made. One line of fixed height, sized to the box, so a long word
              never makes the box or the figure change size (it is cut off with "…" instead).
              Hidden from screen readers: the highlighted sentence below already says it. */}
          <p className="sign-label" aria-hidden="true" title={latest?.label}>{latest?.label ?? '\u00a0'}</p>
        </div>
        <div className="subtitles">
          <p className="signing" aria-live="polite">
            {latest ? <Highlighted text={latest.text} char={latest.char} /> : '\u00a0'}
          </p>
          <p className="caption">
            <span className="tag">Spoken</span> {caption?.text ?? '\u00a0'}
          </p>
          <p className="stats">
            {playing && (
              <>
                {playing.mode === 'aligned' ? 'aligned to speech' : 'sentence mode'} · {pace}
                {lag > 0.3 && <span className="behind"> · {lag.toFixed(1)}s behind</span>}
              </>
            )}
          </p>
        </div>
      </div>
      <p className="summary muted">{summary}</p>
    </div>
  );
}

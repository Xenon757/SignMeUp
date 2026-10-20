import { useEffect, useMemo, useRef, useState } from 'react';
import { drawFigure, drawSpelling, preloadLetters } from '../signer/draw';
import type { Clip } from '../signer/timeline';
import { buildTimeline, captionAt, latestClip, optimalRate, restFrameOf, stateAt } from '../signer/timeline';
import type { PoseClip, Segment } from '../types';

const SPELL_FADE = 0.15; // seconds a fingerspelled word takes to fade in and out

interface Props {
  title: string; // the uploaded file's name
  onReset: () => void; // start over with another file
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
export function Player({ title, onReset, src, audioOnly, segments, poses }: Props) {
  const media = useRef<HTMLVideoElement & HTMLAudioElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const viewer = useRef<HTMLDivElement>(null);
  const menu = useRef<HTMLDetailsElement>(null);
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
  // Close the "Signer box" menu on a click or tap anywhere outside it, or on Escape.
  useEffect(() => {
    const close = (e: Event) => {
      const el = menu.current;
      if (!el?.open) return;
      if (e instanceof KeyboardEvent ? e.key === 'Escape' : !el.contains(e.target as Node)) el.open = false;
    };
    document.addEventListener('pointerdown', close);
    document.addEventListener('keydown', close);
    return () => {
      document.removeEventListener('pointerdown', close);
      document.removeEventListener('keydown', close);
    };
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
      if (clip?.kind === 'spell') {
        // Fade in over the first and out over the last SPELL_FADE seconds (real time).
        const fade = SPELL_FADE * el.playbackRate;
        const appear = Math.min((t - clip.start) / fade, (clip.start + clip.length - t) / fade, 1);
        drawSpelling(ctx, clip.label, (t - clip.start) / clip.length, appear);
      }
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
    const sentences = segments.length;
    return `${sentences} sentence${sentences === 1 ? '' : 's'} · ${animated} signs${spelled ? ` · ${spelled} fingerspelled` : ''}`;
  }, [timeline, segments]);

  const { playing, latest, caption } = view;
  const lag = playing ? playing.behind / rate : 0;
  // The spoken sentence is only worth showing when the signing is on a different one.
  const spokenElsewhere = caption && latest && caption.text !== latest.text ? caption.text : null;
  const cornerLabel: Record<Corner, string> = { 'top-left': '↖', 'top-right': '↗', 'bottom-left': '↙', 'bottom-right': '↘' };

  return (
    <div className="player">
      <div className="player-head">
        <div>
          <h2 className="file-name">{title}</h2>
          <p className="muted small">{summary}</p>
        </div>
        <button type="button" className="secondary" onClick={onReset}>New video</button>
      </div>

      {/* The same elements in every layout (only CSS changes), so the canvas is never re-created. */}
      <div ref={viewer} className={`theatre ${layout} ${prefs.corner} ${prefs.size}`}>
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
          {/* The sign being made. Fixed height and sized to the box, so a long word never makes
              the box or the figure change size. Hidden from screen readers: the caption says it. */}
          <p className="sign-label" aria-hidden="true">
            <span className={latest ? '' : 'empty'} title={latest?.label}>{latest?.label ?? '\u00a0'}</span>
          </p>
        </div>
        <div className="subtitles">
          <p className="signing" aria-live="polite">
            {latest ? <Highlighted text={latest.text} char={latest.char} /> : '\u00a0'}
          </p>
          {/* Always takes its line, so the strip doesn't jump when it appears. */}
          <p className={`spoken${spokenElsewhere ? '' : ' hidden'}`}>
            Now saying: {spokenElsewhere ?? '\u00a0'}
            {lag > 0.3 && <span className="behind"> · signing {lag.toFixed(1)}s behind</span>}
          </p>
        </div>
      </div>

      <div className="toolbar">
        <div className="toolbar-group">
          <button
            type="button"
            className="toggle"
            aria-pressed={optimized}
            onClick={() => setOptimized(o => !o)}
            title="Slow the video down so the signs have time to be read"
          >
            Optimize for ASL
          </button>
          <span className="muted small">
            {optimized ? `Playing at ${rate.toFixed(2)}×` : bestRate < 1 ? `${bestRate.toFixed(2)}× suggested` : 'Pace already suits ASL'}
          </span>
        </div>

        {!audioOnly && (
          <div className="toolbar-group">
            <div className="segmented" role="group" aria-label="Where the signer goes">
              <button type="button" aria-pressed={layout === 'overlay'} onClick={() => update({ layout: 'overlay' })}>In the video</button>
              <button type="button" aria-pressed={layout === 'side'} onClick={() => update({ layout: 'side' })}>Side by side</button>
            </div>
            {layout === 'overlay' && (
              <details className="menu" ref={menu}>
                <summary>Signer box</summary>
                <div className="menu-panel">
                  <p className="menu-title">Corner</p>
                  <div className="corner-grid" role="group" aria-label="Corner">
                    {(['top-left', 'top-right', 'bottom-left', 'bottom-right'] as Corner[]).map(c => (
                      <button key={c} type="button" aria-pressed={prefs.corner === c} aria-label={c.replace('-', ' ')} onClick={() => update({ corner: c })}>
                        {cornerLabel[c]}
                      </button>
                    ))}
                  </div>
                  <p className="menu-title">Size</p>
                  <div className="segmented" role="group" aria-label="Signer size">
                    {SIZES.map(size => (
                      <button key={size} type="button" aria-pressed={prefs.size === size} onClick={() => update({ size })}>
                        {size[0].toUpperCase() + size.slice(1)}
                      </button>
                    ))}
                  </div>
                </div>
              </details>
            )}
            {canFullscreen && (
              <button type="button" className="secondary" onClick={toggleFullscreen}>
                {fullscreen ? 'Exit full screen' : 'Full screen'}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

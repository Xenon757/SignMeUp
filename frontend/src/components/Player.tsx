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

interface View {
  caption: Segment | null;
  latest: Clip | null;
  playing: Clip | null;
}

/** The uploaded video (or audio) next to the signing figure. */
export function Player({ src, audioOnly, segments, poses }: Props) {
  const media = useRef<HTMLVideoElement & HTMLAudioElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [optimized, setOptimized] = useState(false);
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
          className="optimize"
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

      <div className="stage">
        <section className="pane media-pane" aria-label="Your upload">
          {audioOnly ? (
            <div className="audio-card">
              <span aria-hidden="true">♪</span>
              <audio ref={media} src={src} controls preload="auto" />
            </div>
          ) : (
            <video ref={media} src={src} controls playsInline preload="auto" />
          )}
          <p className="caption">
            <span className="tag">Spoken</span> {caption?.text ?? ' '}
          </p>
        </section>

        <section className="pane signer-pane" aria-label="ASL signing">
          <canvas ref={canvas} width={1000} height={1000} role="img" aria-label={playing ? `Signing ${playing.label}` : 'Signer'} />
          <p className="signing" aria-live="polite">
            {latest ? <Highlighted text={latest.text} char={latest.char} /> : ' '}
          </p>
          <p className="stats">
            {playing && (
              <>
                {playing.mode === 'aligned' ? 'aligned to speech' : 'sentence mode'} · {pace}
                {lag > 0.3 && <span className="behind"> · {lag.toFixed(1)}s behind</span>}
              </>
            )}
          </p>
        </section>
      </div>
      <p className="summary muted">{summary}</p>
    </div>
  );
}

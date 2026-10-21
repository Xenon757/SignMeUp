import { useEffect, useRef, useState } from 'react';
import { ApiError, followJob, loadPoses, startDemo } from '../api';
import { Player } from '../components/Player';
import type { Activity } from '../components/Progress';
import { Progress } from '../components/Progress';
import type { PoseClip, Segment } from '../types';

type State =
  | { phase: 'working'; activity: Activity }
  | { phase: 'ready'; videoId: string; title: string; credit: string; segments: Segment[]; poses: Record<string, PoseClip> }
  | { phase: 'error'; message: string };

/**
 * The built-in demo: "Me at the zoo", played in YouTube's own player with SignMeUp signing it.
 * The server signs it from a written transcript the first time, then it's instant.
 */
export function DemoPage() {
  const [state, setState] = useState<State>({ phase: 'working', activity: { step: 'loading' } });
  const live = useRef(true);

  useEffect(() => {
    live.current = true;
    const update = (next: State) => { if (live.current) setState(next); };
    (async () => {
      try {
        const job = await startDemo();
        const result = await followJob(job, j => update({ phase: 'working', activity: { step: 'job', job: j } }), () => live.current);
        if (!result) return;
        update({ phase: 'working', activity: { step: 'loading' } });
        const poses = await loadPoses(result.segments);
        update({ phase: 'ready', videoId: job.demo.youtube_id, title: job.demo.title, credit: job.demo.credit, segments: result.segments, poses });
      } catch (err) {
        update({ phase: 'error', message: err instanceof ApiError ? err.message : 'Could not load the demo. Please try again.' });
      }
    })();
    return () => { live.current = false; };
  }, []);

  return (
    <main className="home">
      {state.phase === 'working' && <Progress activity={state.activity} fileName="the demo" />}
      {state.phase === 'error' && (
        <section className="error-card" role="alert">
          <h2>The demo didn’t load</h2>
          <p>{state.message}</p>
          <div className="row">
            <button type="button" onClick={() => window.location.reload()}>Try again</button>
            <a href="/">Upload your own video</a>
          </div>
        </section>
      )}
      {state.phase === 'ready' && (
        <Player
          title={`Demo: ${state.title}`}
          onReset={() => { window.location.href = '/'; }}
          resetLabel="Upload your own"
          source={{ kind: 'youtube', videoId: state.videoId }}
          segments={state.segments}
          poses={state.poses}
          note={
            <>
              {state.credit} Embedded from YouTube; SignMeUp adds the signing from a written transcript, so its timing is
              approximate.
            </>
          }
        />
      )}
    </main>
  );
}

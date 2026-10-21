import { useEffect, useRef, useState } from 'react';
import { ApiError, followJob, isAudio, loadPoses, startJob } from '../api';
import { Player } from '../components/Player';
import type { Activity } from '../components/Progress';
import { Progress } from '../components/Progress';
import { Landing } from '../components/Landing';
import type { PoseClip, Segment } from '../types';

type State =
  | { phase: 'idle' }
  | { phase: 'working'; file: File; activity: Activity }
  | { phase: 'ready'; file: File; url: string; segments: Segment[]; poses: Record<string, PoseClip> }
  | { phase: 'error'; file: File; message: string };


export function HomePage() {
  const [state, setState] = useState<State>({ phase: 'idle' });
  const run = useRef(0); // ignores results from an upload the user has moved on from

  // Free the uploaded file's object URL when it's no longer shown.
  useEffect(() => () => { if (state.phase === 'ready') URL.revokeObjectURL(state.url); }, [state]);

  const process = async (file: File) => {
    const id = ++run.current;
    const update = (next: State) => { if (run.current === id) setState(next); };
    try {
      update({ phase: 'working', file, activity: { step: 'uploading', fraction: 0 } });
      const job = await startJob(file, fraction => update({ phase: 'working', file, activity: { step: 'uploading', fraction } }));
      const result = await followJob(job, j => update({ phase: 'working', file, activity: { step: 'job', job: j } }), () => run.current === id);
      if (!result) return;
      update({ phase: 'working', file, activity: { step: 'loading' } });
      const poses = await loadPoses(result.segments);
      update({ phase: 'ready', file, url: URL.createObjectURL(file), segments: result.segments, poses });
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Something went wrong. Please try again.';
      update({ phase: 'error', file, message });
    }
  };

  const reset = () => { run.current++; setState({ phase: 'idle' }); };

  return (
    <main className="home">
      {state.phase === 'idle' && <Landing onFile={process} />}

      {state.phase === 'working' && <Progress activity={state.activity} fileName={state.file.name} />}

      {state.phase === 'error' && (
        <section className="error-card" role="alert">
          <h2>That didn’t work</h2>
          <p>{state.message}</p>
          <div className="row">
            <button type="button" onClick={() => process(state.file)}>Try again</button>
            <button type="button" className="secondary" onClick={reset}>Choose another file</button>
          </div>
        </section>
      )}

      {state.phase === 'ready' && (
        <Player
          title={state.file.name}
          onReset={reset}
          source={{ kind: 'file', src: state.url, audioOnly: isAudio(state.file) }}
          segments={state.segments}
          poses={state.poses}
        />
      )}
    </main>
  );
}

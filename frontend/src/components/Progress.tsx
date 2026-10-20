import { useEffect, useState } from 'react';
import type { JobStatus } from '../types';

/** Where the upload is: sending the file, a server-side job, or loading the result. */
export type Activity =
  | { step: 'uploading'; fraction: number }
  | { step: 'job'; job: JobStatus }
  | { step: 'loading' };

interface Step {
  key: string;
  label: string;
  detail?: string;
}

const STEPS: Step[] = [
  { key: 'uploading', label: 'Uploading' },
  { key: 'queued', label: 'Starting' }, // or waiting, if other uploads are ahead (see label())
  { key: 'transcribing', label: 'Transcribing the speech' },
  { key: 'translating', label: 'Translating to ASL' },
  { key: 'animating', label: 'Preparing sign animations', detail: 'Signs used for the first time take about a second each; after that they’re instant.' },
  { key: 'loading', label: 'Loading the animations' },
];

function current(activity: Activity): string {
  if (activity.step === 'job') return activity.job.status;
  return activity.step;
}

function label(step: Step, activity: Activity): string {
  // Every job is queued for a moment before it starts; only say "waiting" if others are ahead.
  const ahead = activity.step === 'job' ? activity.job.ahead ?? 0 : 0;
  if (step.key === 'queued' && ahead > 0) return `Waiting for ${ahead} other upload${ahead > 1 ? 's' : ''} to finish`;
  return step.label;
}

function count(activity: Activity): string | null {
  if (activity.step === 'uploading') return `${Math.round(activity.fraction * 100)}%`;
  if (activity.step !== 'job') return null;
  const { job } = activity;
  if (job.status === 'translating' && job.total) return `sentence ${Math.min(job.total, (job.done ?? 0) + 1)} of ${job.total}`;
  if (job.status === 'animating' && job.total) return `${job.done ?? 0} of ${job.total} words`;
  return null;
}

/** The real stages of processing, each waiting, running or done, with live counts. */
export function Progress({ activity, fileName }: { activity: Activity; fileName: string }) {
  const [started] = useState(() => Date.now());
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(timer);
  }, []);

  const at = current(activity);
  const order = STEPS.map(s => s.key);
  const index = order.indexOf(at);
  // The "waiting" step only shows if this upload actually had to wait.
  const steps = STEPS.filter(s => s.key !== 'queued' || at === 'queued');

  return (
    <section className="progress" aria-live="polite">
      <h2>Working on <span className="file-name">{fileName}</span></h2>
      <ol>
        {steps.map(step => {
          const i = order.indexOf(step.key);
          const state = i < index ? 'done' : i === index ? 'active' : 'pending';
          return (
            <li key={step.key} className={state}>
              <span className="marker" aria-hidden="true">{state === 'done' ? '✓' : ''}</span>
              <span className="step-text">
                <span className="step-label">
                  {label(step, activity)}
                  {state === 'active' && count(activity) && <span className="step-count"> · {count(activity)}</span>}
                </span>
                {state === 'active' && step.detail && <span className="step-detail">{step.detail}</span>}
              </span>
            </li>
          );
        })}
      </ol>
      <p className="elapsed">{Math.floor((now - started) / 1000)}s elapsed</p>
    </section>
  );
}

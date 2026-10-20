import type { AnimationInfo, JobStatus, PoseClip, Segment } from './types';

/** File types the server accepts (app.py ALLOWED_EXTENSIONS). */
export const ACCEPTED = ['.mp4', '.mov', '.m4v', '.webm', '.mkv', '.mp3', '.wav', '.m4a'];
export const AUDIO = ['.mp3', '.wav', '.m4a'];

export const extensionOf = (name: string) => (name.match(/\.[^.]+$/)?.[0] ?? '').toLowerCase();
export const isAudio = (file: File) => file.type.startsWith('audio/') || AUDIO.includes(extensionOf(file.name));

/** An error with a message that is safe and useful to show. */
export class ApiError extends Error {}

async function errorFrom(res: Response | XMLHttpRequest, fallback: string): Promise<ApiError> {
  try {
    const body = res instanceof Response ? await res.json() : JSON.parse(res.responseText);
    if (body?.error) return new ApiError(body.error);
  } catch {
    // not JSON
  }
  return new ApiError(fallback);
}

/**
 * Upload a file and start processing it. Uses XMLHttpRequest rather than fetch because
 * fetch can't report upload progress, and large videos take a while to send.
 */
export function startJob(file: File, onProgress: (fraction: number) => void): Promise<JobStatus> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/jobs');
    xhr.upload.onprogress = e => {
      if (e.lengthComputable) onProgress(e.loaded / e.total);
    };
    xhr.onload = async () => {
      if (xhr.status === 202) resolve(JSON.parse(xhr.responseText));
      else reject(await errorFrom(xhr, `Upload failed (${xhr.status}).`));
    };
    xhr.onerror = () => reject(new ApiError('Could not reach the server. Check that it is running.'));
    const form = new FormData();
    form.append('file', file);
    xhr.send(form);
  });
}

export async function getJob(id: string): Promise<JobStatus> {
  const res = await fetch(`/api/jobs/${id}`);
  if (!res.ok) throw await errorFrom(res, 'Lost track of this upload. Please try again.');
  return res.json();
}

/** Every sign animation the result uses, by URL. The server made them while processing. */
export async function loadPoses(segments: Segment[]): Promise<Record<string, PoseClip>> {
  const urls = new Set<string>();
  for (const seg of segments)
    for (const sign of seg.signs) if (sign.media?.type === 'video' && sign.media.pose) urls.add(sign.media.pose);
  const poses: Record<string, PoseClip> = {};
  await Promise.all(
    [...urls].map(async url => {
      const res = await fetch(url);
      if (res.ok) poses[url] = await res.json();
    }),
  );
  return poses;
}

export async function listAnimations(): Promise<AnimationInfo[]> {
  const res = await fetch('/poses/');
  return res.ok ? res.json() : [];
}

export async function getPose(id: number): Promise<PoseClip> {
  const res = await fetch(`/poses/${id}.json?nocache=${Date.now()}`);
  if (!res.ok) throw await errorFrom(res, 'Could not load this animation.');
  return res.json();
}

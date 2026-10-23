// Runs on YouTube watch pages: gets the video's captions (through page.ts), has the server sign
// them a minute at a time from where the viewer is, and draws the signer in a corner of the
// player, following the video's own clock. Uses the website's signer code unchanged.

import { drawFigure, drawSpelling, preloadLetters, setLetterBase } from '../../frontend/src/signer/draw';
import type { Clip } from '../../frontend/src/signer/timeline';
import { buildTimeline, latestClip, restFrameOf, stateAt } from '../../frontend/src/signer/timeline';
import type { Frame, PoseClip, Segment } from '../../frontend/src/types';
import type { Reply, Request } from './background';
import type { CaptionLine, Json3 } from './captions';
import { chunkLines, chunkOf, chunksToFetch, linesFromJson3 } from './captions';

const SPELL_FADE = 0.15; // seconds a fingerspelled word takes to fade in and out, as on the website

setLetterBase(chrome.runtime.getURL('letters/'));
preloadLetters();

// ---- State for the video being watched ----

let enabled = true;
let videoId: string | null = null;
let lines: CaptionLine[] = [];
let lastChunk = -1;
const requested = new Set<number>();
const chunks = new Map<number, Segment[]>();
const poses: Record<string, PoseClip> = {};
let timeline: Clip[] = [];
let rest: Frame | null = null;
let fetching = false;

function currentVideoId(): string | null {
  return location.pathname === '/watch' ? new URLSearchParams(location.search).get('v') : null;
}

const video = () => document.querySelector<HTMLVideoElement>('#movie_player video');

async function ask(request: Request): Promise<Reply> {
  try {
    return await chrome.runtime.sendMessage(request);
  } catch {
    return { ok: false, body: { error: 'SignMeUp was updated. Reload the page.' } };
  }
}

function start(id: string | null) {
  videoId = id;
  lines = [];
  lastChunk = -1;
  requested.clear();
  chunks.clear();
  timeline = [];
  if (!id) return;
  setStatus('Getting captions…');
  window.postMessage({ source: 'signmeup-content', type: 'find-captions' }, location.origin);
}

// Captions from page.ts.
window.addEventListener('message', event => {
  const data = event.data;
  if (event.source !== window || data?.source !== 'signmeup-page' || data.type !== 'captions') return;
  if (data.videoId !== videoId) return;
  if (data.error === 'no-english') return setStatus('This video has no English captions to sign.');
  if (!data.data) return setStatus('Could not get this video’s captions.');
  lines = linesFromJson3(data.data as Json3);
  if (!lines.length) return setStatus('This video’s captions are empty.');
  lastChunk = chunkOf(lines.at(-1)!.start);
  setStatus('Signing…');
  fetchAhead();
});

/** Ask the server for the chunks around and ahead of the viewer, one at a time, most urgent first. */
async function fetchAhead() {
  const v = video();
  if (fetching || !v || !lines.length || !enabled) return;
  fetching = true;
  const forVideo = videoId;
  try {
    for (const chunk of chunksToFetch(v.currentTime, requested, lastChunk)) {
      requested.add(chunk);
      const part = chunkLines(lines, chunk);
      if (!part.length) continue;
      const reply = await ask({ type: 'sign-captions', lines: part });
      if (videoId !== forVideo) return;
      if (!reply.ok) {
        requested.delete(chunk); // try again on the next round
        setStatus((reply.body as { error?: string })?.error ?? 'SignMeUp could not sign this part.');
        return;
      }
      const segments = (reply.body as { segments: Segment[] }).segments;
      await loadPoses(segments);
      if (videoId !== forVideo) return;
      chunks.set(chunk, segments);
      rebuild();
      // After a seek, start again from the new spot rather than finishing this plan.
      if (!requested.has(chunkOf(video()?.currentTime ?? 0))) break;
    }
  } finally {
    fetching = false;
  }
}

async function loadPoses(segments: Segment[]) {
  const wanted = new Set<string>();
  for (const seg of segments)
    for (const sign of seg.signs)
      if (sign.media?.type === 'video' && sign.media.pose && !poses[sign.media.pose]) wanted.add(sign.media.pose);
  await Promise.all(
    [...wanted].map(async path => {
      const reply = await ask({ type: 'pose', path });
      if (reply.ok) poses[path] = reply.body as PoseClip;
    }),
  );
}

function rebuild() {
  const segments = [...chunks.keys()].sort((a, b) => a - b).flatMap(k => chunks.get(k)!);
  timeline = buildTimeline(segments, poses);
  rest ??= restFrameOf(poses);
  setStatus('');
}

// ---- The signer box inside YouTube's player ----

const host = document.createElement('div');
host.id = 'signmeup-signer';
const shadow = host.attachShadow({ mode: 'open' });
shadow.innerHTML = `
  <style>
    :host { position: absolute; right: 12px; bottom: 64px; width: clamp(120px, 22%, 360px); aspect-ratio: 1;
            z-index: 59; pointer-events: none; }
    .box { position: relative; width: 100%; height: 100%; border-radius: 12px; overflow: hidden;
           background: #f3efe8; box-shadow: 0 4px 18px rgba(0, 0, 0, 0.35); }
    canvas { width: 100%; height: 100%; display: block; }
    .label { position: absolute; left: 50%; bottom: 8px; transform: translateX(-50%); padding: 2px 10px;
             border-radius: 999px; background: #18212f; color: #fff; font: 600 13px/1.6 system-ui, sans-serif;
             letter-spacing: 0.04em; white-space: nowrap; }
    .label:empty { display: none; }
    .status { position: absolute; inset: auto 8px 8px; padding: 6px 8px; border-radius: 8px; background: rgba(24, 33, 47, 0.85);
              color: #fff; font: 12px/1.4 system-ui, sans-serif; text-align: center; }
    .status:empty { display: none; }
  </style>
  <div class="box"><canvas width="600" height="600"></canvas><div class="label"></div><div class="status"></div></div>`;
const canvas = shadow.querySelector('canvas')!;
const ctx = canvas.getContext('2d')!;
const label = shadow.querySelector<HTMLElement>('.label')!;
const statusEl = shadow.querySelector<HTMLElement>('.status')!;

function setStatus(text: string) {
  statusEl.textContent = text;
}

function placeBox(): HTMLElement | null {
  const player = document.getElementById('movie_player');
  // Hidden during ads: they play in the same video element, so the captions' times don't apply.
  const show = enabled && !!videoId && !!player && !player.classList.contains('ad-showing');
  if (show && host.parentElement !== player) player!.append(host);
  if (!show) host.remove();
  return show ? player : null;
}

let shownLabel = '';
function tick() {
  requestAnimationFrame(tick);
  const v = video();
  if (!placeBox() || !v) return;
  const t = v.currentTime;
  const { frame, clip } = stateAt(timeline, t, rest);
  drawFigure(ctx, frame);
  if (clip?.kind === 'spell') {
    const fade = SPELL_FADE * v.playbackRate;
    const appear = Math.min((t - clip.start) / fade, (clip.start + clip.length - t) / fade, 1);
    drawSpelling(ctx, clip.label, (t - clip.start) / clip.length, appear);
  }
  const latest = latestClip(timeline, t);
  const text = latest?.label ?? '';
  if (text !== shownLabel) label.textContent = shownLabel = text;
}

// ---- Keeping up with the page ----

// YouTube changes videos without reloading the page, so check for a new one regularly, and
// keep asking for the chunks ahead of the viewer (also right after a seek).
setInterval(() => {
  const id = currentVideoId();
  if (id !== videoId) start(id);
  else fetchAhead();
}, 1000);
document.addEventListener('seeked', () => fetchAhead(), true);

chrome.storage.sync.get({ enabled: true }).then(({ enabled: on }) => {
  enabled = on !== false;
  start(currentVideoId());
  requestAnimationFrame(tick);
});
chrome.storage.onChanged.addListener(changes => {
  if (changes.enabled) {
    enabled = changes.enabled.newValue !== false;
    if (enabled) fetchAhead();
  }
});

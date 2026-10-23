// Runs in YouTube's own page (not the extension's isolated world), because only there can it
// reach the player and see the caption files the player loads. It hands the current video's
// English captions to the content script through window messages.

interface CaptionTrack {
  baseUrl: string;
  languageCode: string;
  kind?: string; // "asr" for auto-generated
}

interface Player extends HTMLElement {
  getPlayerResponse?: () => {
    videoDetails?: { videoId?: string };
    captions?: { playerCaptionsTracklistRenderer?: { captionTracks?: CaptionTrack[] } };
  };
  loadModule?: (name: string) => void;
  setOption?: (module: string, option: string, value: unknown) => void;
}

const FROM_CONTENT = 'signmeup-content';
const FROM_PAGE = 'signmeup-page';

// The video whose captions the content script is waiting for, if the direct fetch didn't work.
let waitingFor: string | null = null;

function send(message: Record<string, unknown>) {
  window.postMessage({ source: FROM_PAGE, ...message }, location.origin);
}

/** English uploaded captions if there are any (usually more accurate), else auto-generated ones. */
function englishTrack(tracks: CaptionTrack[]): CaptionTrack | undefined {
  const english = tracks.filter(t => t.languageCode === 'en' || t.languageCode.startsWith('en-'));
  return english.find(t => t.kind !== 'asr') ?? english[0];
}

function json3Url(url: string) {
  const u = new URL(url, location.origin);
  u.searchParams.set('fmt', 'json3');
  return u.toString();
}

async function findCaptions() {
  const player = document.getElementById('movie_player') as Player | null;
  const response = player?.getPlayerResponse?.();
  const videoId = response?.videoDetails?.videoId;
  if (!player || !videoId) return send({ type: 'captions', error: 'no-player' });
  const track = englishTrack(response?.captions?.playerCaptionsTracklistRenderer?.captionTracks ?? []);
  if (!track) return send({ type: 'captions', videoId, error: 'no-english' });
  try {
    const text = await (await fetch(json3Url(track.baseUrl), { credentials: 'include' })).text();
    if (text.trim()) return send({ type: 'captions', videoId, data: JSON.parse(text) });
  } catch {
    // fall through to letting the player load them
  }
  // YouTube sometimes refuses caption requests that don't come from its player. Turning
  // captions on makes the player load them itself; the hooks below catch that response.
  waitingFor = videoId;
  player.loadModule?.('captions');
  player.setOption?.('captions', 'track', { languageCode: track.languageCode });
}

/** A caption file the player loaded: pass it on if it's the one being waited for. */
function caught(url: string, body: string) {
  if (!waitingFor || !url.includes('/api/timedtext')) return;
  const u = new URL(url, location.origin);
  if (u.searchParams.get('v') !== waitingFor || !body.trim()) return;
  try {
    send({ type: 'captions', videoId: waitingFor, data: JSON.parse(body) });
    waitingFor = null;
  } catch {
    // not json3 (another format); keep waiting
  }
}

const originalFetch = window.fetch;
window.fetch = async function (...args: Parameters<typeof fetch>) {
  const response = await originalFetch.apply(this, args);
  const url = args[0] instanceof Request ? args[0].url : String(args[0]);
  if (url.includes('/api/timedtext')) response.clone().text().then(body => caught(url, body), () => {});
  return response;
};

const originalOpen = XMLHttpRequest.prototype.open;
XMLHttpRequest.prototype.open = function (this: XMLHttpRequest, method: string, url: string | URL, ...rest: unknown[]) {
  const href = String(url);
  if (href.includes('/api/timedtext')) {
    this.addEventListener('load', () => {
      if (typeof this.response === 'string') caught(href, this.response);
    });
  }
  return (originalOpen as (...a: unknown[]) => void).call(this, method, url, ...rest);
} as typeof XMLHttpRequest.prototype.open;

window.addEventListener('message', event => {
  if (event.source !== window || event.data?.source !== FROM_CONTENT) return;
  if (event.data.type === 'find-captions') findCaptions();
});

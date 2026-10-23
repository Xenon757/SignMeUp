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
  unloadModule?: (name: string) => void;
  setOption?: (module: string, option: string, value: unknown) => void;
}

const FROM_CONTENT = 'signmeup-content';
const FROM_PAGE = 'signmeup-page';

// Every caption file the player has loaded, by video: if captions were already on, the player
// won't load them again, so they have to be remembered from the start.
const loaded = new Map<string, string>();
// The video whose captions the content script is waiting for, after asking the player for them.
let waitingFor: string | null = null;

function send(message: Record<string, unknown>) {
  window.postMessage({ source: FROM_PAGE, ...message }, location.origin);
}

/** English uploaded captions if there are any (usually more accurate), else auto-generated ones. */
function englishTrack(tracks: CaptionTrack[]): CaptionTrack | undefined {
  const english = tracks.filter(t => t.languageCode === 'en' || t.languageCode.startsWith('en-'));
  return english.find(t => t.kind !== 'asr') ?? english[0];
}

function withFormat(url: string, format: string) {
  const u = new URL(url, location.origin);
  u.searchParams.set('fmt', format);
  return u.toString();
}

const isEnglish = (url: string) => {
  const lang = new URL(url, location.origin).searchParams.get('lang') ?? '';
  return lang === '' || lang === 'en' || lang.startsWith('en-');
};

async function findCaptions(videoId: string) {
  const player = document.getElementById('movie_player') as Player | null;
  const response = player?.getPlayerResponse?.();
  // Right after a page change the player can still be on the previous video: say so, and the
  // content script asks again shortly.
  if (!player || response?.videoDetails?.videoId !== videoId) return send({ type: 'captions', videoId, error: 'not-ready' });
  const remembered = loaded.get(videoId);
  if (remembered) return send({ type: 'captions', videoId, body: remembered });
  const track = englishTrack(response?.captions?.playerCaptionsTracklistRenderer?.captionTracks ?? []);
  if (!track) return send({ type: 'captions', videoId, error: 'no-english' });
  try {
    const body = await (await fetch(withFormat(track.baseUrl, 'json3'), { credentials: 'include' })).text();
    if (body.trim()) return send({ type: 'captions', videoId, body });
  } catch {
    // fall through to letting the player load them
  }
  // YouTube sometimes refuses caption requests that don't come from its player. Turning
  // captions (back) on makes the player load them itself; the hooks below catch that response.
  waitingFor = videoId;
  player.unloadModule?.('captions');
  player.loadModule?.('captions');
  player.setOption?.('captions', 'track', { languageCode: track.languageCode });
}

/** A caption file the player loaded: remember it, and pass it on if it's being waited for. */
function caught(url: string, body: string) {
  const videoId = new URL(url, location.origin).searchParams.get('v');
  if (!videoId || !body.trim() || !isEnglish(url)) return;
  loaded.set(videoId, body);
  if (videoId === waitingFor) {
    send({ type: 'captions', videoId, body });
    waitingFor = null;
  }
}

const isCaptionFile = (url: string) => url.includes('/api/timedtext');

const originalFetch = window.fetch;
window.fetch = async function (...args: Parameters<typeof fetch>) {
  const response = await originalFetch.apply(this, args);
  const url = args[0] instanceof Request ? args[0].url : String(args[0]);
  if (isCaptionFile(url)) response.clone().text().then(body => caught(url, body), () => {});
  return response;
};

const originalOpen = XMLHttpRequest.prototype.open;
XMLHttpRequest.prototype.open = function (this: XMLHttpRequest, method: string, url: string | URL, ...rest: unknown[]) {
  const href = String(url);
  if (isCaptionFile(href)) {
    this.addEventListener('load', () => {
      if (this.responseType === '' || this.responseType === 'text') caught(href, this.responseText);
    });
  }
  return (originalOpen as (...a: unknown[]) => void).call(this, method, url, ...rest);
} as typeof XMLHttpRequest.prototype.open;

window.addEventListener('message', event => {
  if (event.source !== window || event.data?.source !== FROM_CONTENT) return;
  if (event.data.type === 'find-captions' && typeof event.data.videoId === 'string') findCaptions(event.data.videoId);
});

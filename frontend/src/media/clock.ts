// A common way for the player to follow whatever is playing: an uploaded file (a <video> or
// <audio> element) or a YouTube video in YouTube's own embedded player.

export interface MediaClock {
  /** Current playback position, in seconds. */
  time(): number;
  duration(): number;
  rate(): number;
  setRate(rate: number): void;
  /** The closest playback rate this media supports, at or below `rate`. */
  snapRate(rate: number): number;
  /** Calls `ended` when playback reaches the end and `restarted` on play or seek; returns an unsubscribe. */
  listen(ended: () => void, restarted: () => void): () => void;
}

export function elementClock(el: HTMLMediaElement): MediaClock {
  return {
    time: () => el.currentTime,
    duration: () => el.duration || 0,
    rate: () => el.playbackRate,
    setRate: rate => {
      el.playbackRate = rate;
      el.defaultPlaybackRate = rate; // keeps the rate if the media is reloaded
    },
    snapRate: rate => rate,
    listen(ended, restarted) {
      el.addEventListener('ended', ended);
      el.addEventListener('play', restarted);
      el.addEventListener('seeked', restarted);
      return () => {
        el.removeEventListener('ended', ended);
        el.removeEventListener('play', restarted);
        el.removeEventListener('seeked', restarted);
      };
    },
  };
}

// The parts of YouTube's IFrame Player API that we use.
export interface YouTubePlayer {
  getCurrentTime(): number;
  getDuration(): number;
  getPlaybackRate(): number;
  setPlaybackRate(rate: number): void;
  getAvailablePlaybackRates(): number[];
  destroy(): void;
}
const YT_ENDED = 0;
const YT_PLAYING = 1;

/** A clock for a YouTube player. `onState` must be wired to the player's onStateChange event. */
export function youtubeClock(player: YouTubePlayer, onState: { current: ((state: number) => void) | null }): MediaClock {
  return {
    time: () => player.getCurrentTime() || 0,
    duration: () => player.getDuration() || 0,
    rate: () => player.getPlaybackRate() || 1,
    setRate: rate => player.setPlaybackRate(rate),
    // YouTube only offers fixed speeds (0.25, 0.5, 0.75, 1, ...).
    snapRate(rate) {
      const rates = player.getAvailablePlaybackRates?.() ?? [0.25, 0.5, 0.75, 1];
      return Math.max(...rates.filter(r => r <= rate + 1e-9), Math.min(...rates));
    },
    listen(ended, restarted) {
      onState.current = state => {
        if (state === YT_ENDED) ended();
        else if (state === YT_PLAYING) restarted();
      };
      return () => { onState.current = null; };
    },
  };
}

// Loads YouTube's IFrame Player API script once.
let apiReady: Promise<void> | null = null;
export function loadYouTubeApi(): Promise<void> {
  const w = window as unknown as { YT?: { Player?: unknown }; onYouTubeIframeAPIReady?: () => void };
  if (w.YT?.Player) return Promise.resolve();
  if (!apiReady) {
    apiReady = new Promise(resolve => {
      const previous = w.onYouTubeIframeAPIReady;
      w.onYouTubeIframeAPIReady = () => { previous?.(); resolve(); };
      const script = document.createElement('script');
      script.src = 'https://www.youtube.com/iframe_api';
      document.head.append(script);
    });
  }
  return apiReady;
}

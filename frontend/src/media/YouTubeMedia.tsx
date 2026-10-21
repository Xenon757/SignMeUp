import { useEffect, useRef } from 'react';
import type { MediaClock, YouTubePlayer } from './clock';
import { loadYouTubeApi, youtubeClock } from './clock';

interface YTConstructor {
  new (el: HTMLElement, options: unknown): YouTubePlayer;
}

/**
 * A YouTube video in YouTube's own embedded player (so the video is never copied), using the
 * privacy-enhanced youtube-nocookie.com host. Hands the player's clock to `onClock`.
 */
export function YouTubeMedia({ videoId, title, onClock }: { videoId: string; title: string; onClock: (clock: MediaClock) => void }) {
  const holder = useRef<HTMLDivElement>(null);
  const onState = useRef<((state: number) => void) | null>(null);
  const clockCallback = useRef(onClock);
  useEffect(() => { clockCallback.current = onClock; }, [onClock]);

  useEffect(() => {
    let player: YouTubePlayer | null = null;
    let cancelled = false;
    loadYouTubeApi().then(() => {
      if (cancelled || !holder.current) return;
      const YT = (window as unknown as { YT: { Player: YTConstructor } }).YT;
      const target = document.createElement('div');
      holder.current.replaceChildren(target);
      player = new YT.Player(target, {
        videoId,
        host: 'https://www.youtube-nocookie.com',
        playerVars: { rel: 0, playsinline: 1, modestbranding: 1 },
        events: {
          onReady: () => { if (!cancelled && player) clockCallback.current(youtubeClock(player, onState)); },
          onStateChange: (e: { data: number }) => onState.current?.(e.data),
        },
      });
    });
    return () => {
      cancelled = true;
      player?.destroy();
    };
  }, [videoId]);

  return <div className="youtube-frame" ref={holder} title={title} />;
}

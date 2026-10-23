// YouTube's captions -> the caption lines SignMeUp's server signs, and which chunks of them to
// ask for. Pure functions, so they can be tested without a browser.

/** One caption line, as POST /api/captions takes it. */
export interface CaptionLine {
  start: number; // seconds
  end: number;
  text: string;
  words?: { start: number; text: string }[]; // auto-generated captions time each word
}

/** YouTube's "json3" caption format: events, each with text pieces ("segs"). */
export interface Json3 {
  events?: { tStartMs?: number; dDurationMs?: number; segs?: { utf8?: string; tOffsetMs?: number }[] }[];
}

const MAX_LINE_CHARS = 1000; // the server's limit

export function linesFromJson3(data: Json3): CaptionLine[] {
  const lines: CaptionLine[] = [];
  for (const event of data.events ?? []) {
    if (!event.segs || event.tStartMs == null) continue;
    const text = event.segs.map(s => s.utf8 ?? '').join('').replace(/\s+/g, ' ').trim().slice(0, MAX_LINE_CHARS);
    if (!text) continue; // auto-captions add events that only hold a line break
    const start = event.tStartMs / 1000;
    const end = Math.max(start, (event.tStartMs + (event.dDurationMs ?? 0)) / 1000);
    const line: CaptionLine = { start, end, text };
    // Auto-generated captions give each word its own piece with an offset; uploaded ones don't.
    if (event.segs.some(s => s.tOffsetMs != null)) {
      const words = event.segs
        .map(s => ({ start: (event.tStartMs! + (s.tOffsetMs ?? 0)) / 1000, text: (s.utf8 ?? '').trim() }))
        .filter(w => w.text);
      if (words.length) line.words = words;
    }
    lines.push(line);
  }
  return lines.sort((a, b) => a.start - b.start);
}

/** Captions are signed a minute at a time, so the first signs come back in about a second. */
export const CHUNK_SECONDS = 60;
export const CHUNKS_AHEAD = 4; // keep this many minutes ahead of the viewer

export const chunkOf = (t: number) => Math.floor(Math.max(0, t) / CHUNK_SECONDS);

/** The caption lines in one chunk (by when each line starts). */
export const chunkLines = (lines: CaptionLine[], chunk: number) => lines.filter(l => chunkOf(l.start) === chunk);

/**
 * Which chunks to ask for next, most urgent first: the one being watched, then the ones after it.
 * After a seek this starts from the new spot, so the viewer never waits for the parts skipped.
 */
export function chunksToFetch(t: number, requested: Set<number>, lastChunk: number): number[] {
  const now = chunkOf(t);
  const wanted: number[] = [];
  for (let c = now; c <= Math.min(now + CHUNKS_AHEAD, lastChunk); c++) if (!requested.has(c)) wanted.push(c);
  return wanted;
}

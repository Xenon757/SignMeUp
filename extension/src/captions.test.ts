import { describe, expect, it } from 'vitest';
import { chunkLines, chunksToFetch, linesFromCaptionFile, linesFromJson3 } from './captions';

describe('linesFromJson3', () => {
  it('keeps word timings from auto-generated captions', () => {
    const lines = linesFromJson3({
      events: [
        { tStartMs: 1000, dDurationMs: 3000, segs: [{ utf8: 'hello' }, { utf8: ' there', tOffsetMs: 600 }] },
        { tStartMs: 2500, dDurationMs: 1500, segs: [{ utf8: '\n' }] },
      ],
    });
    expect(lines).toEqual([
      { start: 1, end: 4, text: 'hello there', words: [{ start: 1, text: 'hello' }, { start: 1.6, text: 'there' }] },
    ]);
  });

  it('keeps uploaded captions as whole lines', () => {
    const lines = linesFromJson3({ events: [{ tStartMs: 5000, dDurationMs: 2000, segs: [{ utf8: 'How are\nyou?' }] }] });
    expect(lines).toEqual([{ start: 5, end: 7, text: 'How are you?' }]);
  });

  it('ignores events without text or a start', () => {
    expect(linesFromJson3({ events: [{ dDurationMs: 100, segs: [{ utf8: 'x' }] }, { tStartMs: 0 }] })).toEqual([]);
    expect(linesFromJson3({})).toEqual([]);
  });
});

describe('chunks', () => {
  const lines = [0, 30, 61, 125].map(start => ({ start, end: start + 2, text: `at ${start}` }));

  it('groups lines by the minute they start in', () => {
    expect(chunkLines(lines, 0).map(l => l.start)).toEqual([0, 30]);
    expect(chunkLines(lines, 2).map(l => l.start)).toEqual([125]);
  });

  it('asks for the chunk being watched first, then a few ahead', () => {
    expect(chunksToFetch(70, new Set(), 100)).toEqual([1, 2, 3, 4, 5]);
    expect(chunksToFetch(70, new Set([1, 2]), 100)).toEqual([3, 4, 5]);
  });

  it('starts from the new spot after a seek and stops at the end', () => {
    expect(chunksToFetch(3600, new Set([0, 1, 2]), 61)).toEqual([60, 61]);
  });
});

describe('linesFromCaptionFile', () => {
  it('reads srv3 XML with word timings', () => {
    const xml = '<timedtext format="3"><body><p t="1000" d="3000" w="1"><s ac="0">hello</s><s t="600" ac="0"> there</s></p>' +
      '<p t="2500" d="1500" a="1">\n</p><p t="5000" d="2000">How&#39;s it &amp; you?</p></body></timedtext>';
    expect(linesFromCaptionFile(xml)).toEqual([
      { start: 1, end: 4, text: 'hello there', words: [{ start: 1, text: 'hello' }, { start: 1.6, text: 'there' }] },
      { start: 5, end: 7, text: "How's it & you?" },
    ]);
  });

  it('reads the older XML format', () => {
    const xml = '<transcript><text start="1.5" dur="2">it&amp;#39;s here</text></transcript>';
    expect(linesFromCaptionFile(xml)).toEqual([{ start: 1.5, end: 3.5, text: "it's here" }]);
  });

  it('reads json3 and ignores anything else', () => {
    expect(linesFromCaptionFile('{"events":[{"tStartMs":0,"dDurationMs":1000,"segs":[{"utf8":"hi"}]}]}')).toEqual([{ start: 0, end: 1, text: 'hi' }]);
    expect(linesFromCaptionFile('')).toEqual([]);
    expect(linesFromCaptionFile('not captions')).toEqual([]);
  });
});

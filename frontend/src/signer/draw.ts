// Draws the 2D signing figure on a canvas.
import type { Frame, Point } from '../types';

// MediaPipe hand points: 0 wrist, then 4 per finger from the base to the tip.
const FINGERS = [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, 16], [17, 18, 19, 20]];
const PALM = [0, 1, 5, 9, 13, 17];
// Face points are stored outline after outline, in this order and length (see asl_util/poses.py).
const FACE_OUTLINES: [string, number][] = [['oval', 36], ['lips', 20], ['leftEye', 16], ['rightEye', 16], ['leftBrow', 10], ['rightBrow', 10]];

// The figure wears solid dark clothing, like ASL interpreters do, so the hands stand out.
export const COLORS = {
  shirt: '#2b3445', sleeve: '#2b3445', forearm: '#3d4a61', skin: '#e9c9a8', faceEdge: '#d4ad86',
  line: '#1f2937', palm: '#f3d2b0', backOfHand: '#c8895a', handOutline: '#6b3f22', lips: '#9b4a4a',
};

/** A colour darkened by `amount` (0 = unchanged, 1 = black), for shading parts set back. */
function shade(hex: string, amount: number) {
  const n = parseInt(hex.slice(1), 16);
  const f = (c: number) => Math.round(c * (1 - amount));
  return `rgb(${f(n >> 16)}, ${f((n >> 8) & 255)}, ${f(n & 255)})`;
}

export function drawFigure(ctx: CanvasRenderingContext2D, frame: Frame | null) {
  const { width: W, height: H } = ctx.canvas;
  const s = W / 900;
  ctx.clearRect(0, 0, W, H);
  if (!frame?.pose) return;

  // Body space -> canvas. The view covers the signing space: from just above the head (about
  // 1.6 shoulder widths above the shoulders) to the hips (about 1.7 below).
  const unit = H / 3.4;
  const toCanvas = (p: Point): [number, number] => [W / 2 + p[0] * unit, H * 0.49 + p[1] * unit];
  const path = (points: Point[], close = false) => {
    ctx.beginPath();
    points.forEach((p, i) => (i ? ctx.lineTo(...toCanvas(p)) : ctx.moveTo(...toCanvas(p))));
    if (close) ctx.closePath();
  };
  const line = (a: Point, b: Point, width: number, color: string) => {
    ctx.lineWidth = width; ctx.strokeStyle = color; ctx.lineCap = 'round';
    path([a, b]); ctx.stroke();
  };

  // A hand as a solid shape: the palm and each finger drawn back to front by depth, so a finger
  // in front of the palm covers it. The palm is light when it faces the viewer and darker when
  // the back of the hand does (palm orientation tells many signs apart). `dim` darkens the whole
  // hand (the farther hand gets less light); with `shadow` it first casts a soft shadow.
  const drawHand = (hand: Point[] | null, isRight: boolean, dim: number, shadow: number) => {
    if (!hand) return;
    const pts = hand.map(toCanvas);
    const depth = (idx: number[]) => idx.reduce((t, i) => t + (hand[i][2] ?? 0), 0) / idx.length;
    const palmWidth = Math.hypot(pts[5][0] - pts[17][0], pts[5][1] - pts[17][1]);
    const width = Math.max(4 * s, palmWidth * 0.27);
    const outline = Math.max(1.5, width * 0.14);

    // Which side faces the viewer, from the order of the knuckles around the wrist: the
    // signer's right hand shows its palm when index->pinky turns one way, the left the other.
    const [w, i5, i17] = [pts[0], pts[5], pts[17]];
    const turn = (i5[0] - w[0]) * (i17[1] - w[1]) - (i5[1] - w[1]) * (i17[0] - w[0]);
    const fill = (isRight ? turn < 0 : turn > 0) ? COLORS.palm : COLORS.backOfHand;

    const parts = [{ idx: PALM, palm: true }, ...FINGERS.map(idx => ({ idx, palm: false }))]
      .map(part => ({ ...part, z: depth(part.idx) }))
      .sort((a, b) => b.z - a.z); // farthest first
    // Within the hand, parts farther back are a little darker (up to 18%).
    const zNear = Math.min(...parts.map(p => p.z));
    const zFar = Math.max(...parts.map(p => p.z));
    const back = (z: number) => (zFar - zNear > 1e-3 ? (z - zNear) / (zFar - zNear) : 0);
    const trace = (part: { idx: number[]; palm: boolean }) => {
      ctx.beginPath();
      part.idx.forEach((i, k) => (k ? ctx.lineTo(...pts[i]) : ctx.moveTo(...pts[i])));
      if (part.palm) ctx.closePath();
    };
    ctx.lineJoin = 'round'; ctx.lineCap = 'round';

    if (shadow) {
      // The hand's silhouette, drawn only for its blurred, offset shadow.
      ctx.save();
      ctx.shadowColor = `rgba(40, 22, 10, ${shadow})`;
      ctx.shadowBlur = 14 * s; ctx.shadowOffsetX = 5 * s; ctx.shadowOffsetY = 8 * s;
      ctx.fillStyle = ctx.strokeStyle = '#000';
      for (const part of parts) {
        trace(part);
        if (part.palm) ctx.fill();
        else { ctx.lineWidth = width + 2 * outline; ctx.stroke(); }
      }
      ctx.restore();
    }
    for (const part of parts) {
      const colour = shade(fill, dim + 0.18 * back(part.z));
      trace(part);
      if (part.palm) {
        ctx.fillStyle = colour; ctx.fill();
        ctx.lineWidth = outline; ctx.strokeStyle = COLORS.handOutline; ctx.stroke();
      } else {
        ctx.lineWidth = width + 2 * outline; ctx.strokeStyle = COLORS.handOutline; ctx.stroke();
        ctx.lineWidth = width; ctx.strokeStyle = colour; ctx.stroke();
      }
    }
  };

  const [nose, lSh, rSh, lEl, rEl, lWr, rWr, lHip, rHip] = frame.pose;
  const shoulderWidth = Math.hypot(lSh[0] - rSh[0], lSh[1] - rSh[1]) * unit;
  const neckBase: Point = [(lSh[0] + rSh[0]) / 2, (lSh[1] + rSh[1]) / 2];

  // Neck, then the shirt over its base (rounded at the shoulders), then the head over its top.
  line(neckBase, nose, shoulderWidth * 0.36, COLORS.skin);
  ctx.lineJoin = 'round';
  path([lSh, rSh, rHip, lHip], true);
  ctx.fillStyle = COLORS.shirt; ctx.fill();
  ctx.lineWidth = 24 * s; ctx.strokeStyle = COLORS.shirt; ctx.stroke();

  if (frame.face) {
    const parts: Record<string, Point[]> = {};
    let i = 0;
    for (const [name, n] of FACE_OUTLINES) { parts[name] = frame.face.slice(i, i + n); i += n; }
    ctx.fillStyle = COLORS.skin; path(parts.oval, true); ctx.fill();
    ctx.lineWidth = 3 * s; ctx.strokeStyle = COLORS.faceEdge; ctx.stroke();
    ctx.fillStyle = COLORS.line;
    for (const brow of ['leftBrow', 'rightBrow']) { path(parts[brow], true); ctx.fill(); }
    ctx.lineWidth = 3 * s; ctx.strokeStyle = COLORS.line;
    for (const eye of ['leftEye', 'rightEye']) { path(parts[eye], true); ctx.stroke(); }
    ctx.fillStyle = COLORS.lips; path(parts.lips, true); ctx.fill();
  } else {
    const [x, y] = toCanvas(nose);
    ctx.beginPath(); ctx.arc(x, y, Math.abs(toCanvas(lSh)[0] - toCanvas(rSh)[0]) * 0.32, 0, 7);
    ctx.fillStyle = COLORS.skin; ctx.fill();
  }

  // Each arm and its hand are drawn together, the farther side first, so where the hands cross
  // or touch the nearer one is on top. Depth comes from the body tracker's wrists (smaller z =
  // nearer); without it, the signer's right hand goes on top.
  const sides = [
    { sh: lSh, el: lEl, wr: lWr, hand: frame.leftHand, isRight: false, z: lWr[2] ?? 1 },
    { sh: rSh, el: rEl, wr: rWr, hand: frame.rightHand, isRight: true, z: rWr[2] ?? 0 },
  ].sort((a, b) => b.z - a.z);
  sides.forEach((side, k) => {
    // The arm ends at the tracked hand's wrist, so arm and hand stay joined. The forearm is a
    // slightly lighter shade so a bent arm reads as two parts, even folded back toward the face.
    const nearer = k === sides.length - 1;
    line(side.sh, side.el, 30 * s, COLORS.sleeve);
    line(side.el, side.hand ? side.hand[0] : side.wr, 24 * s, COLORS.forearm);
    // Depth cues: both hands cast a shadow, the nearer one more strongly, and the farther hand
    // is slightly darker, as if it gets less light.
    drawHand(side.hand, side.isRight, nearer ? 0 : 0.12, nearer ? 0.45 : 0.25);
  });
}

// Public-domain handshape images for fingerspelling (static/img/fingerspelling), loaded once.
// Each is a black outline on a transparent background; a copy recoloured to the figure's hand
// outline colour is kept so the letters match the figure's style.
const letterImages: Record<string, HTMLImageElement> = {};
const tintedLetters: Record<string, HTMLCanvasElement> = {};
function letterImage(ch: string) {
  if (!letterImages[ch]) {
    letterImages[ch] = new Image();
    letterImages[ch].src = `/static/img/fingerspelling/${ch}.svg`;
  }
  return letterImages[ch];
}
export const preloadLetters = () => [...'abcdefghijklmnopqrstuvwxyz'].forEach(letterImage);

function tintedLetter(ch: string): HTMLCanvasElement | null {
  if (tintedLetters[ch]) return tintedLetters[ch];
  const img = letterImage(ch);
  if (!img.complete || !img.naturalWidth) return null;
  const c = document.createElement('canvas');
  const scale = 240 / Math.max(img.naturalWidth, img.naturalHeight);
  c.width = Math.round(img.naturalWidth * scale);
  c.height = Math.round(img.naturalHeight * scale);
  const g = c.getContext('2d')!;
  g.drawImage(img, 0, 0, c.width, c.height);
  g.globalCompositeOperation = 'source-in'; // keep the drawing's shape, change its colour
  g.fillStyle = COLORS.handOutline;
  g.fillRect(0, 0, c.width, c.height);
  return (tintedLetters[ch] = c);
}

const ACCENT = '#2f6f5e';
const easeOut = (k: number) => 1 - (1 - k) ** 3;

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

/**
 * A fingerspelled word, drawn over the figure. The letters' handshapes sit on skin-coloured
 * cards in the figure's style, all visible at once so the word can be read, and the letter
 * being spelled is raised and outlined, moving left to right through the word. `progress`
 * (0..1) is how far through the word we are; `appear` (0..1) fades and slides the row in and
 * out, and dims the figure behind it, so it doesn't pop on and off.
 */
export function drawSpelling(ctx: CanvasRenderingContext2D, word: string, progress: number, appear: number) {
  const { width: W, height: H } = ctx.canvas;
  const letters = word.toLowerCase().replace(/[^a-z]/g, '');
  if (!letters || appear <= 0) return;
  const k = easeOut(Math.min(1, appear));
  const n = letters.length;
  const current = Math.min(n - 1, Math.floor(progress * n));

  // Soften the figure behind the letters rather than covering it.
  ctx.save();
  ctx.globalAlpha = 0.45 * k;
  ctx.fillStyle = '#fbfaf7';
  ctx.fillRect(0, 0, W, H);
  ctx.restore();

  // Cards in one row, as large as fits; portrait like most handshapes.
  const gap = W * 0.018;
  const cardW = Math.min(W * 0.22, (W * 0.92 - gap * (n - 1)) / n);
  const cardH = cardW * 1.25;
  const rowW = cardW * n + gap * (n - 1);
  const x0 = (W - rowW) / 2;
  // Over the chest, below the face; slides up as it appears.
  const y0 = Math.min(H * 0.64 - cardH / 2, H * 0.97 - cardH) + (1 - k) * H * 0.04;
  const s = W / 900;

  ctx.save();
  ctx.globalAlpha = k;
  [...letters].forEach((ch, i) => {
    const active = i === current;
    const lift = active ? cardH * 0.06 : 0;
    const grow = active ? 1.08 : 1;
    const w = cardW * grow, h = cardH * grow;
    const x = x0 + i * (cardW + gap) - (w - cardW) / 2;
    const y = y0 - lift - (h - cardH) / 2;

    ctx.save();
    ctx.shadowColor = 'rgba(40, 22, 10, 0.25)';
    ctx.shadowBlur = (active ? 16 : 8) * s;
    ctx.shadowOffsetY = (active ? 6 : 3) * s;
    roundRect(ctx, x, y, w, h, Math.min(w, h) * 0.14);
    ctx.fillStyle = active ? '#fff7ee' : COLORS.palm;
    ctx.fill();
    ctx.restore();
    roundRect(ctx, x, y, w, h, Math.min(w, h) * 0.14);
    ctx.lineWidth = (active ? 5 : 2) * s;
    ctx.strokeStyle = active ? ACCENT : 'rgba(107, 63, 34, 0.35)';
    ctx.stroke();

    // The handshape, fitted inside the card without stretching, above its letter.
    const art = tintedLetter(ch);
    const pad = w * 0.12;
    const boxW = w - 2 * pad, boxH = h * 0.7 - pad;
    if (art) {
      const fit = Math.min(boxW / art.width, boxH / art.height);
      const aw = art.width * fit, ah = art.height * fit;
      ctx.globalAlpha = k * (active ? 1 : 0.75);
      ctx.drawImage(art, x + (w - aw) / 2, y + pad + (boxH - ah) / 2, aw, ah);
      ctx.globalAlpha = k;
    }
    ctx.fillStyle = active ? ACCENT : COLORS.handOutline;
    ctx.font = `700 ${Math.round(h * 0.17)}px Poppins, system-ui, sans-serif`;
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText(ch.toUpperCase(), x + w / 2, y + h * 0.84);
  });
  ctx.restore();
}

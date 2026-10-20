// Draws the 2D signing figure from pose animations made by asl_util/poses.py.
// Shared by the prototype page and the sign comparison page.
//
// A frame is { pose, leftHand, rightHand, face }: lists of [x, y] points in "body space"
// (origin between the shoulders, 1 unit = shoulder width, y pointing down). Hand points may
// also have a depth z (smaller = nearer the viewer). Any part may be null when not tracked.
const Signer = (() => {
  // MediaPipe hand points: 0 wrist, then 4 per finger from the base to the tip.
  const FINGERS = [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, 16], [17, 18, 19, 20]];
  const PALM = [0, 1, 5, 9, 13, 17];
  // Face points are stored outline after outline, in this order and length (see asl_util/poses.py).
  const FACE_OUTLINES = [["oval", 36], ["lips", 20], ["leftEye", 16], ["rightEye", 16], ["leftBrow", 10], ["rightBrow", 10]];
  // Pose points: 0 nose, 1-2 shoulders, 3-4 elbows, 5-6 wrists, 7-8 hips.
  const COLORS = { body: '#334a6b', forearm: '#5b7bab', skin: '#e9c9a8', line: '#1f2937', torso: '#d7dee9',
                   palm: '#f3d2b0', backOfHand: '#c8895a', handOutline: '#6b3f22' };

  // A colour darkened by `amount` (0 = unchanged, 1 = black), for shading parts set back.
  function shade(hex, amount) {
    const n = parseInt(hex.slice(1), 16);
    const f = c => Math.round(c * (1 - amount));
    return `rgb(${f(n >> 16)}, ${f((n >> 8) & 255)}, ${f(n & 255)})`;
  }

  function lerp(a, b, k) {
    if (!a) return b;
    if (!b) return a;
    return a.map((p, i) => p.map((v, d) => v + (b[i][d] - v) * k));
  }

  function lerpFrame(a, b, k) {
    if (!a || !b) return a || b;
    return { pose: lerp(a.pose, b.pose, k), leftHand: lerp(a.leftHand, b.leftHand, k),
             rightHand: lerp(a.rightHand, b.rightHand, k), face: lerp(a.face, b.face, k) };
  }

  // The frame at `progress` (0..1) through a clip's frames, blended between the two nearest
  // recorded frames so motion stays smooth at any playback speed.
  function frameAt(frames, progress) {
    const at = Math.max(0, Math.min(frames.length - 1, progress * (frames.length - 1)));
    const i = Math.floor(at);
    return lerpFrame(frames[i], frames[Math.min(frames.length - 1, i + 1)], at - i);
  }

  function drawFigure(ctx, frame) {
    const canvas = ctx.canvas;
    const s = canvas.width / 900;

    // Body space -> canvas. The view covers the signing space: from just above the head
    // (about 1.6 shoulder widths above the shoulders) to the hips (about 1.7 below), so
    // signs made at the waist aren't cut off.
    const toCanvas = ([x, y]) => {
      const unit = canvas.height / 3.4;
      return [canvas.width / 2 + x * unit, canvas.height * 0.49 + y * unit];
    };
    const path = (points, close) => {
      ctx.beginPath();
      points.forEach((p, i) => { const [x, y] = toCanvas(p); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
      if (close) ctx.closePath();
    };
    const line = (a, b, width, color) => {
      ctx.lineWidth = width; ctx.strokeStyle = color; ctx.lineCap = 'round';
      path([a, b]); ctx.stroke();
    };
    const faceParts = face => {
      const parts = {};
      let i = 0;
      for (const [name, n] of FACE_OUTLINES) { parts[name] = face.slice(i, i + n); i += n; }
      return parts;
    };
    // A hand as a solid shape: the palm and each finger drawn back to front by depth, so a
    // finger in front of the palm covers it. The palm is light when it faces the viewer and
    // darker when the back of the hand does (palm orientation distinguishes many signs).
    // `dim` darkens the whole hand (the farther hand gets less light). With `shadow`,
    // the hand first casts a soft shadow onto whatever is behind it.
    const drawHand = (hand, isRight, { dim = 0, shadow = 0 } = {}) => {
      if (!hand) return;
      const pts = hand.map(toCanvas);
      const depth = idx => idx.reduce((t, i) => t + (hand[i][2] ?? 0), 0) / idx.length;
      const palmWidth = Math.hypot(pts[5][0] - pts[17][0], pts[5][1] - pts[17][1]);
      const width = Math.max(4 * s, palmWidth * 0.27);
      const outline = Math.max(1.5, width * 0.14);

      // Which side faces the viewer, from the order of the knuckles around the wrist.
      // The signer's right hand shows its palm when index->pinky turns one way, the left hand the other.
      const [w, i5, i17] = [pts[0], pts[5], pts[17]];
      const turn = (i5[0] - w[0]) * (i17[1] - w[1]) - (i5[1] - w[1]) * (i17[0] - w[0]);
      const fill = (isRight ? turn < 0 : turn > 0) ? COLORS.palm : COLORS.backOfHand;

      const parts = [{ idx: PALM, palm: true }, ...FINGERS.map(idx => ({ idx }))];
      parts.forEach(part => { part.z = depth(part.idx); });
      parts.sort((a, b) => b.z - a.z);  // farthest first
      // Within the hand, parts farther back are a little darker (up to 18%).
      const zs = parts.map(p => p.z);
      const zNear = Math.min(...zs), zFar = Math.max(...zs);
      const back = part => (zFar - zNear > 1e-3 ? (part.z - zNear) / (zFar - zNear) : 0);

      const trace = part => {
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
        ctx.fillStyle = ctx.strokeStyle = 'rgba(0, 0, 0, 1)';
        ctx.globalCompositeOperation = 'source-over';
        for (const part of parts) {
          trace(part);
          if (part.palm) ctx.fill(); else { ctx.lineWidth = width + 2 * outline; ctx.stroke(); }
        }
        ctx.restore();
      }

      for (const part of parts) {
        const colour = shade(fill, dim + 0.18 * back(part));
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

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (!frame?.pose) return;
    const [nose, lSh, rSh, lEl, rEl, lWr, rWr, lHip, rHip] = frame.pose;

    // Torso
    ctx.fillStyle = COLORS.torso;
    path([lSh, rSh, rHip, lHip], true); ctx.fill();

    // Head
    if (frame.face) {
      const f = faceParts(frame.face);
      ctx.fillStyle = COLORS.skin; path(f.oval, true); ctx.fill();
      ctx.fillStyle = COLORS.line;
      for (const part of ['leftBrow', 'rightBrow']) { path(f[part], true); ctx.fill(); }
      ctx.lineWidth = 3 * s; ctx.strokeStyle = COLORS.line;
      for (const part of ['leftEye', 'rightEye']) { path(f[part], true); ctx.stroke(); }
      ctx.fillStyle = '#9b4a4a'; path(f.lips, true); ctx.fill();
    } else {
      const [x, y] = toCanvas(nose); const r = Math.abs(toCanvas(lSh)[0] - toCanvas(rSh)[0]) * 0.32;
      ctx.beginPath(); ctx.arc(x, y, r, 0, 7); ctx.fillStyle = COLORS.skin; ctx.fill();
    }

    // Each arm and its hand are drawn together, the farther side first, so where the hands
    // cross or touch the nearer one is on top. Depth comes from the body tracker's wrists
    // (smaller z = nearer); without it, the signer's right hand goes on top.
    line(lSh, rSh, 22 * s, COLORS.body);
    const sides = [
      { sh: lSh, el: lEl, wr: lWr, hand: frame.leftHand, isRight: false, z: lWr[2] ?? 1 },
      { sh: rSh, el: rEl, wr: rWr, hand: frame.rightHand, isRight: true, z: rWr[2] ?? 0 },
    ].sort((a, b) => b.z - a.z);
    sides.forEach((side, k) => {
      // The arm ends at the tracked hand's wrist when there is one, so arm and hand stay joined.
      // The forearm is a lighter shade so a bent arm reads as two parts, even when the
      // forearm folds back over the upper arm (signs made at the face).
      const wrist = side.hand ? side.hand[0] : side.wr;
      const nearer = k === sides.length - 1;
      line(side.sh, side.el, 22 * s, COLORS.body);
      line(side.el, wrist, 18 * s, COLORS.forearm);
      // Depth cues: both hands cast a shadow on what's behind them, the nearer one more
      // strongly, and the farther hand is slightly darker, as if it gets less light.
      drawHand(side.hand, side.isRight, nearer ? { shadow: 0.45 } : { dim: 0.12, shadow: 0.25 });
    });
  }

  return { lerpFrame, frameAt, drawFigure, COLORS };
})();

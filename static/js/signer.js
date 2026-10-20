// Draws the 2D signing figure from pose animations made by asl_util/poses.py.
// Shared by the prototype page and the sign comparison page.
//
// A frame is { pose, leftHand, rightHand, face }: lists of [x, y] points in "body space"
// (origin between the shoulders, 1 unit = shoulder width, y pointing down). Any part may
// be null when it wasn't tracked.
const Signer = (() => {
  const HAND_BONES = [[0,1],[1,2],[2,3],[3,4],[0,5],[5,6],[6,7],[7,8],[5,9],[9,10],[10,11],[11,12],
                      [9,13],[13,14],[14,15],[15,16],[13,17],[17,18],[18,19],[19,20],[0,17]];
  const PALM = [0, 1, 5, 9, 13, 17];
  // Face points are stored outline after outline, in this order and length (see asl_util/poses.py).
  const FACE_OUTLINES = [["oval", 36], ["lips", 20], ["leftEye", 16], ["rightEye", 16], ["leftBrow", 10], ["rightBrow", 10]];
  // Pose points: 0 nose, 1-2 shoulders, 3-4 elbows, 5-6 wrists, 7-8 hips.
  const COLORS = { body: '#334a6b', skin: '#e9c9a8', hand: '#c98f62', line: '#1f2937', torso: '#d7dee9' };

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

  // The frame at `progress` (0..1) through a clip's frames.
  function frameAt(frames, progress) {
    return frames[Math.min(frames.length - 1, Math.floor(progress * frames.length))];
  }

  function drawFigure(ctx, frame) {
    const canvas = ctx.canvas;
    const s = canvas.width / 900;

    // Body space -> canvas: shoulders centred a little below the middle, about 3.6 shoulder widths across.
    const toCanvas = ([x, y]) => {
      const unit = canvas.width / 3.6;
      return [canvas.width / 2 + x * unit, canvas.height * 0.62 + y * unit];
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
    const drawHand = hand => {
      if (!hand) return;
      ctx.fillStyle = COLORS.skin;
      path(PALM.map(i => hand[i]), true); ctx.fill();
      for (const [a, b] of HAND_BONES) line(hand[a], hand[b], 9 * s, COLORS.hand);
      for (const p of hand) { const [x, y] = toCanvas(p); ctx.beginPath(); ctx.arc(x, y, 4.5 * s, 0, 7); ctx.fillStyle = COLORS.line; ctx.fill(); }
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

    // Arms end at the tracked hand's wrist when there is one, so arm and hand stay joined.
    const lHandWrist = frame.leftHand ? frame.leftHand[0] : lWr;
    const rHandWrist = frame.rightHand ? frame.rightHand[0] : rWr;
    for (const [sh, elb, wr] of [[lSh, lEl, lHandWrist], [rSh, rEl, rHandWrist]]) {
      line(sh, elb, 26 * s, COLORS.body);
      line(elb, wr, 22 * s, COLORS.body);
    }
    line(lSh, rSh, 26 * s, COLORS.body);

    drawHand(frame.leftHand);
    drawHand(frame.rightHand);
  }

  return { lerpFrame, frameAt, drawFigure, COLORS };
})();

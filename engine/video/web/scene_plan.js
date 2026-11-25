// Сцена «вид сверху»: карта из фигур, которые растут, меняют форму и подписываются. Река, берег, тела, скважины, площадка.
// Параметры: width_m (ширина карты, м), bar_m (линейка), ground, water — цвета; shapes по порядку снизу вверх:
// [{id, type: area|line|arrow|waves|dots, pts [[x 0..1, y 0..1]], to [[x, y]] (во что превращается), color, rock?, w, dash?, text?}].
// beat: s_<id> 0..1 — показать (линия и стрелка прорастают), m_<id> 0..1 — превратить в to; zoom, cam_x, cam_y; hl id; call [{x, y, text, dx, dy}]; head.
const catmull = (P, closed) => { // плавная линия через точки
  const out = [], n = P.length, at = i => closed ? P[(i + n) % n] : P[Math.max(0, Math.min(n - 1, i))];
  for (let i = 0; i < (closed ? n : n - 1); i++) for (let k = 0; k < 12; k++) {
    const t = k / 12, a = at(i - 1), b = at(i), c = at(i + 1), d = at(i + 2), f = j => 0.5 * ((2 * b[j]) + (-a[j] + c[j]) * t + (2 * a[j] - 5 * b[j] + 4 * c[j] - d[j]) * t * t + (-a[j] + 3 * b[j] - 3 * c[j] + d[j]) * t * t * t);
    out.push([f(0), f(1)]);
  }
  if (!closed) out.push(P[n - 1]);
  return out;
};
const Scene = {
  setup(S) {
    this.tiles = {};
    for (const q of S.P.shapes) if (q.rock && !this.tiles[q.id]) { const c = new OffscreenCanvas(900, 640); (Rock[q.rock] || Rock.sand)(c.getContext('2d'), 0, 0, 900, 640, S.color(q.color || 'lithology.sand'), 60, null); this.tiles[q.id] = c; }
    const c = new OffscreenCanvas(700, 700), x = c.getContext('2d'), r = rng(9), g = S.P.ground ? S.color(S.P.ground) : '#7c8a5a';
    x.fillStyle = mix(g, '#26301c', 0.35); x.fillRect(0, 0, 700, 700);
    for (let i = 0; i < 2600; i++) { x.fillStyle = rgba(mix(g, r() < 0.5 ? '#e8e4c8' : '#1d2414', r() * 0.5), 0.22); blob(x, r() * 700, r() * 700, 3 + r() * 12, r() * 6); x.fill(); }
    this.land = c;
  },
  draw(x, t, S) {
    const P = S.P, { W, H } = S, y0 = S.vert ? 560 : S.sq ? 290 : 240, y1 = H - (S.vert ? 380 : S.sq ? 90 : 40), z = S.track(t, 'zoom', 1), cx = S.track(t, 'cam_x', 0.5), cy = S.track(t, 'cam_y', 0.5);
    const X = u => W / 2 + (u - cx) * W * z, Y = v => (y0 + y1) / 2 + (v - cy) * (y1 - y0) * z;
    this.v = { X, Y, z, mpx: P.width_m / W / z };
    const g = x.createPattern(this.land, 'repeat'); g.setTransform(new DOMMatrix().translate(X(0), Y(0)).scale(z));
    x.fillStyle = g; x.fillRect(0, 0, W, H);
    for (const q of P.shapes) {
      const a = S.track(t, 's_' + q.id, q.on === undefined ? 0 : q.on); if (a < 0.01) continue;
      const m = S.track(t, 'm_' + q.id, 0), raw = q.pts.map((p, i) => q.to ? [lerp(p[0], q.to[i][0], m), lerp(p[1], q.to[i][1], m)] : p), col = S.color(q.color || 'measurement');
      const hl = S.shown(t, 'hl', 0.4, 0.3, q.id);
      x.save();
      if (q.type === 'area') {
        const C = catmull(raw, true); x.beginPath(); C.forEach(p => x.lineTo(X(p[0]), Y(p[1]))); x.closePath();
        x.globalAlpha = a;
        if (q.rock) { const pt = x.createPattern(this.tiles[q.id], 'repeat'); pt.setTransform(new DOMMatrix().translate(X(0), Y(0)).scale(z * 0.8)); x.fillStyle = pt; } else x.fillStyle = rgba(q.water ? mix(col, '#0b1e33', 0.25) : col, q.alpha || 1);
        x.shadowColor = 'rgba(0,0,0,.45)'; x.shadowBlur = q.water ? 0 : 22; x.fill(); x.shadowBlur = 0;
        if (q.water) { x.save(); x.clip(); x.strokeStyle = 'rgba(255,255,255,.14)'; x.lineWidth = 3; for (let k = 0; k < 34; k++) { const yy = Y(-0.2) + k * 46 * z; x.beginPath(); for (let i = -20; i <= W + 20; i += 24) x.lineTo(i, yy + Math.sin(i / 60 + k * 1.7 + t * 1.2) * 5); x.stroke(); } x.restore(); }
        x.strokeStyle = hl > 0.02 ? mix(col, '#F1C40F', hl) : 'rgba(15,20,24,.55)'; x.lineWidth = 3 + 6 * hl; x.stroke();
      } else if (q.type === 'line' || q.type === 'arrow') {
        const C = catmull(raw, false), n = Math.max(2, Math.round(C.length * smooth(a))), L = C.slice(0, n), w = (q.w || 14) * Math.sqrt(z);
        x.lineCap = 'round'; x.lineJoin = 'round';
        if (q.type === 'line' && !q.dash) { x.strokeStyle = 'rgba(12,18,24,.55)'; x.lineWidth = w + 8; x.beginPath(); L.forEach(p => x.lineTo(X(p[0]), Y(p[1]))); x.stroke(); }
        x.strokeStyle = hl > 0.02 ? mix(col, '#F1C40F', hl) : col; x.lineWidth = q.type === 'arrow' ? q.w || 10 : w;
        if (q.dash || q.type === 'arrow') { x.setLineDash([26, 18]); x.lineDashOffset = -t * 70; }
        x.beginPath(); L.forEach((p, i) => { const k = q.flare ? 1 : 1; x.lineTo(X(p[0]), Y(p[1]) * k); }); x.stroke(); x.setLineDash([]);
        if (q.flow) { x.strokeStyle = 'rgba(255,255,255,.5)'; x.lineWidth = 4; x.setLineDash([16, 34]); x.lineDashOffset = -t * 90; x.beginPath(); L.forEach(p => x.lineTo(X(p[0]), Y(p[1]))); x.stroke(); x.setLineDash([]); }
        if (q.type === 'arrow' && n > 3) { const e = L[n - 1], b = L[n - 4], an = Math.atan2(Y(e[1]) - Y(b[1]), X(e[0]) - X(b[0])); x.translate(X(e[0]), Y(e[1])); x.rotate(an); x.fillStyle = x.strokeStyle; x.beginPath(); x.moveTo(26, 0); x.lineTo(-14, -20); x.lineTo(-14, 20); x.closePath(); x.fill(); }
      } else if (q.type === 'waves') { // гребни волн идут вдоль направления от первой точки ко второй
        const [A, B] = raw, dx = X(B[0]) - X(A[0]), dy = Y(B[1]) - Y(A[1]), len = Math.hypot(dx, dy), nx = -dy / len, ny = dx / len, half = (q.w || 300) * z;
        for (let k = 0; k < 6; k++) { const f = (k / 6 + t * 0.12) % 1; x.globalAlpha = a * Math.sin(f * Math.PI) * 0.9; x.strokeStyle = '#ffffff'; x.lineWidth = 5; x.beginPath(); for (let i = -10; i <= 10; i++) { const s = i / 10 * half, bow = Math.sin(i * 0.7) * 6; x.lineTo(X(A[0]) + dx * f + nx * s + dx / len * bow, Y(A[1]) + dy * f + ny * s + dy / len * bow); } x.stroke(); }
      } else if (q.type === 'dots') { // скважины или отдельные точки
        raw.forEach((p, i) => { const k = outBack(clamp(a * raw.length - i)); if (k <= 0) return; x.fillStyle = '#0f151b'; x.beginPath(); x.arc(X(p[0]), Y(p[1]), 17 * k, 0, 7); x.fill(); x.fillStyle = col; x.beginPath(); x.arc(X(p[0]), Y(p[1]), 11 * k, 0, 7); x.fill(); });
      }
      x.restore();
    }
  },
  overlay(x, t, S) {
    const { X, Y, mpx } = this.v, { W, H } = S;
    S.beats.forEach((b, j) => {
      const list = (b.beat || {}).call || [], end = S.beats[j + 1] ? S.beats[j + 1].t_start : S.job.total + 1;
      list.forEach((c, i) => {
        const k = Math.min((t - b.t_start - 0.3 - i * 0.7) / 0.6, (end - t) / 0.25); if (k <= 0) return;
        const wl = measure(x, c.text, 46, 600) + 36, px = clamp(X(c.x), 40, W - 40), tx = px + (c.dx || 0), right = tx > W * 0.6;
        callout(x, px, Y(c.y), clamp(tx, 30 + (right ? wl : 0), W - 30 - (right ? 0 : wl)), clamp(Y(c.y) + (c.dy === undefined ? -100 : c.dy), S.vert ? 640 : 330, H - 150), c.text, k, { align: right ? 'right' : 'left' });
      });
    });
    if (S.P.bar_m) { // линейка
      const L = S.P.bar_m / mpx, yb = H - (S.vert ? 420 : 50), x0 = S.safe.side + 8;
      x.fillStyle = 'rgba(8,12,17,.78)'; rr(x, x0 - 16, yb - 66, Math.max(L, 130) + 34, 84, 12); x.fill();
      x.strokeStyle = '#fff'; x.lineWidth = 5; x.beginPath(); x.moveTo(x0, yb - 16); x.lineTo(x0, yb); x.lineTo(x0 + L, yb); x.lineTo(x0 + L, yb - 16); x.stroke();
      label(x, S.P.bar_m >= 1000 ? `${String(S.P.bar_m / 1000).replace('.', ',')} км` : `${S.P.bar_m} м`, x0 + 6, yb - 22, { size: 44, w: 700, shadow: false });
    }
    Stage.frameText(x, t, S.P.note || 'вид сверху');
  },
};

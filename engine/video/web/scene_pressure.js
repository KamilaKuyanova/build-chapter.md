// Сцена «давление вокруг скважины»: поверхность давления над пластом, вид сверху, профиль и кривая соседней скважины
// считаются из одной формулы Δp = A·E1(r²/4κt) при одном времени t. Пласт нарисован в истинном масштабе.
// Параметры: kappa, r_view, r_obs, thick, t_max, kappas. beat: lt (lg времени, с), view (main|three|fit), lens, head, az, hl.
function E1(x) {
  if (x <= 0) return 50;
  if (x <= 1) {
    let s = -0.5772156649 - Math.log(x), f = 1, p = 1;
    for (let k = 1; k < 30; k++) { f *= k; p *= x; s += ((k % 2) ? 1 : -1) * p / (k * f); }
    return s;
  }
  return (x * x + 2.334733 * x + 0.250621) / (x * x + 3.330657 * x + 1.681534) * Math.exp(-x) / x;
}
const RW = 6; // ближе к скважине поверхность не рисуем, только воронку до этой точки
const drop = (r, t, k) => t <= 0 ? 0 : E1(Math.max(r, RW) ** 2 / (4 * k * t));
function clock(s) {
  if (s < 60) return `${Math.round(s)} с`;
  if (s < 3600) return `${Math.round(s / 60)} мин`;
  const m = Math.round(s / 60);
  return `${Math.floor(m / 60)} ч ${String(m % 60).padStart(2, '0')} мин`;
}
const num = v => String(v).replace('.', ',');

const Scene = {
  setup(S) {
    this.max = drop(RW, S.P.t_max, Math.max(...S.P.kappas));
    this.main = drop(RW, S.P.t_max, S.P.kappa);
    const c = new OffscreenCanvas(700, 700), x = c.getContext('2d');
    Rock.sand(x, 0, 0, 700, 700, S.color('lithology.sand'), 4, null);
    this.sand = c;
    const r = rng(17);
    this.pts = Array.from({ length: 26 }, (_, i) => { const lt = lerp(Math.log10(300), Math.log10(S.P.t_max), i / 25); return [lt, (r() - 0.5) * 0.028]; });
    this.seeds = Array.from({ length: 220 }, () => [r() * Math.PI * 2, r(), r()]);
  },
  proj(V, X, Y, h) {
    const c = Math.cos(V.az), s = Math.sin(V.az), x = X * c - Y * s, y = X * s + Y * c, k = V.D / (V.D - y);
    return [V.cx + x * V.s * k, V.cy + (y * V.s * V.st - h * V.ct) * k, y];
  },
  // цвет величины падения: спокойный пласт — тёмно-синий, сильное падение — бирюзовый цвет давления из стайлгайда
  tone(S, v) { const p = S.color('curves.PRESSURE'); v = clamp(v); return v < 0.5 ? mix('#16324a', mix(p, '#16324a', 0.45), v * 2) : mix(mix(p, '#16324a', 0.45), mix(p, '#ffffff', 0.4), (v - 0.5) * 2); },
  block(x, S, V, tm, kap, o = {}) { // пласт, поверхность давления над ним и скважины
    const R = S.P.r_view, hs = V.hs, lift = V.lift, th = S.P.thick * V.s, N = 72, rings = [0];
    for (let i = 0; i <= 26; i++) rings.push(RW * Math.pow(R / RW, i / 26));
    const P = (r, a, h) => this.proj(V, r * Math.cos(a), r * Math.sin(a), h);
    // боковая кромка пласта: толщина в том же масштабе, что и ширина
    x.beginPath();
    for (let i = 0; i <= N; i++) { const [X, Y] = P(R, i / N * Math.PI * 2, 0); x.lineTo(X, Y + th * V.ct); }
    x.closePath();
    x.fillStyle = mix(S.color('lithology.sand'), '#3b2c0e', 0.45); x.shadowColor = 'rgba(0,0,0,.6)'; x.shadowBlur = 50; x.shadowOffsetY = 26; x.fill();
    x.shadowBlur = 0; x.shadowOffsetY = 0;
    x.beginPath();
    for (let i = 0; i <= N; i++) { const [X, Y] = P(R, i / N * Math.PI * 2, 0); x.lineTo(X, Y); }
    x.closePath();
    x.save();
    x.clip();
    const [bx, by] = [V.cx, V.cy], w = R * V.s * 1.5;
    x.drawImage(this.sand, bx - w, by - w * V.st, 2 * w, 2 * w * V.st);
    for (let i = rings.length - 1; i > 0; i--) { // тот же расчёт, вид сверху: цветом на кровле пласта
      const v = drop(rings[i], tm, kap) / this.main;
      x.beginPath();
      for (let j = 0; j <= N; j++) { const [X, Y] = P(rings[i], j / N * Math.PI * 2, 0); x.lineTo(X, Y); }
      x.closePath();
      for (let j = 0; j <= N; j++) { const [X, Y] = P(rings[i - 1], j / N * Math.PI * 2, 0); if (j) x.lineTo(X, Y); else x.moveTo(X, Y); }
      x.closePath();
      x.fillStyle = rgba(this.tone(S, 0.15 + v * 1.5), 0.80);
      x.fill('evenodd');
    }
    if (!o.small) { // жидкость идёт к скважине, где давление ниже
      const front = Math.sqrt(4 * kap * tm) * 1.15;
      for (const [a, ph, sp] of this.seeds) {
        const r = R * (1 - ((ph + V.t * (0.03 + sp * 0.03)) % 1));
        const al = clamp((front - r) / (front * 0.5 + 1)) * clamp(r / 30) * 0.85;
        if (al < 0.03) continue;
        const [X, Y] = P(r, a, 0), [X2, Y2] = P(r + 13, a, 0);
        x.strokeStyle = `rgba(255,255,255,${al})`; x.lineWidth = 3; x.beginPath(); x.moveTo(X2, Y2); x.lineTo(X, Y); x.stroke();
      }
    }
    x.restore();
    const W1 = this.proj(V, 0, 0, 0), W2 = this.proj(V, S.P.r_obs, 0, 0);
    const zAt = r => lift - drop(r, tm, kap) / this.main * hs;
    // поверхность давления
    const quads = [];
    for (let i = 1; i < rings.length - 1; i++) for (let j = 0; j < N; j++) {
      const a0 = j / N * Math.PI * 2, a1 = (j + 1) / N * Math.PI * 2, r0 = rings[i], r1 = rings[i + 1];
      const q = [P(r0, a0, zAt(r0)), P(r1, a0, zAt(r1)), P(r1, a1, zAt(r1)), P(r0, a1, zAt(r0))];
      quads.push([q, (q[0][2] + q[2][2]) / 2, drop((r0 + r1) / 2, tm, kap) / this.main, a0]);
    }
    quads.sort((a, b) => a[1] - b[1]);
    const well = (w, r, name) => {
      const top = this.proj(V, r, 0, lift + 150)[1], g = x.createLinearGradient(w[0] - 9, 0, w[0] + 9, 0);
      g.addColorStop(0, '#3a424b'); g.addColorStop(0.35, '#f1f5f8'); g.addColorStop(1, '#30373f');
      x.fillStyle = g; x.fillRect(w[0] - 8, top, 16, w[1] - top);
      x.fillStyle = '#0f151b'; x.beginPath(); x.ellipse(w[0], w[1], 15, 8, 0, 0, 7); x.fill();
      return top;
    };
    const t2 = well(W2, S.P.r_obs), t1 = well(W1, 0);
    for (const [q, , v, a0] of quads) {
      const light = 0.5 + 0.5 * Math.cos(a0 + V.az - 0.9);
      x.fillStyle = rgba(mix(this.tone(S, 0.12 + v * 1.5), '#ffffff', 0.10 * light), 0.74);
      x.beginPath();
      for (const p of q) x.lineTo(p[0], p[1]);
      x.closePath(); x.fill();
    }
    x.lineWidth = 1.5; // сетка поверхности
    for (let i = 2; i < rings.length; i += 2) { x.strokeStyle = 'rgba(230,250,255,.26)'; x.beginPath(); for (let j = 0; j <= N; j++) { const p = P(rings[i], j / N * Math.PI * 2, zAt(rings[i])); x.lineTo(p[0], p[1]); } x.stroke(); }
    for (let j = 0; j < N; j += 6) { x.strokeStyle = 'rgba(230,250,255,.18)'; x.beginPath(); for (let i = 1; i < rings.length; i++) { const p = P(rings[i], j / N * Math.PI * 2, zAt(rings[i])); x.lineTo(p[0], p[1]); } x.stroke(); }
    const dot = (r, col) => { const p = this.proj(V, r, 0, zAt(r)); x.fillStyle = '#fff'; x.beginPath(); x.arc(p[0], p[1], o.small ? 9 : 14, 0, 7); x.fill(); x.fillStyle = col; x.beginPath(); x.arc(p[0], p[1], o.small ? 6 : 9, 0, 7); x.fill(); return p; };
    const p0 = this.proj(V, S.P.r_obs, 0, lift); // откуда опускается точка соседней скважины
    const p2 = dot(S.P.r_obs, S.color('measurement'));
    x.setLineDash([6, 6]); x.strokeStyle = S.color('measurement'); x.lineWidth = 3; x.beginPath(); x.moveTo(p0[0], p0[1]); x.lineTo(p2[0], p2[1]); x.stroke(); x.setLineDash([]);
    return { W1, W2, t1, t2, p2 };
  },
  draw(x, t, S) {
    const { W, H } = S;
    const g = x.createLinearGradient(0, 0, 0, H);
    g.addColorStop(0, '#0c141c'); g.addColorStop(0.55, '#15222e'); g.addColorStop(1, '#0a1016');
    x.fillStyle = g; x.fillRect(0, 0, W, H);
    const lt = S.track(t, 'lt', 1), tm = Math.pow(10, lt), three = S.shown(t, 'view', 0.7, 0.5, 'three'), fit = S.shown(t, 'view', 0.7, 0.5, 'fit');
    const az = S.track(t, 'az', 0.35) + Math.sin(t * 0.09) * 0.06;
    this.tm = tm;
    if (three < 0.99 && fit < 0.99) {
      x.save();
      x.globalAlpha = 1 - Math.max(three, fit);
      const V = S.sq ? { t, az, cx: 480, cy: 640, s: 0.86, st: 0.42, ct: 0.9, D: 1500, hs: 235, lift: 180 } : { t, az, cx: 660, cy: 700, s: 1.32, st: 0.42, ct: 0.9, D: 1700, hs: 330, lift: 250 };
      const B = this.block(x, S, V, tm, S.P.kappa);
      this.B = B;
      callout(x, B.W1[0], B.t1 + 14, B.W1[0] - 60, Math.max(S.sq ? 345 : 0, B.t1 - 48), 'работает', S.track(t, 'names', 0), { align: 'right' });
      callout(x, B.W2[0], B.t2 + 14, B.W2[0] + 40, Math.max(S.sq ? 345 : 0, B.t2 - 48), 'соседняя', S.track(t, 'names', 0), { color: mix(S.color('measurement'), '#ffffff', 0.2) });
      const k = S.track(t, 'ruler', 0);
      if (k > 0.02) {
        const dy = 64; x.globalAlpha *= k; x.strokeStyle = '#fff'; x.lineWidth = 4;
        const A = [B.W1[0], B.W1[1] + dy], C = [B.W2[0], B.W2[1] + dy];
        x.beginPath(); x.moveTo(A[0], A[1] - 16); x.lineTo(A[0], A[1] + 10); x.moveTo(A[0], A[1]); x.lineTo(C[0], C[1]); x.moveTo(C[0], C[1] - 16); x.lineTo(C[0], C[1] + 10); x.stroke();
        label(x, `${S.P.r_obs} м`, (A[0] + C[0]) / 2, Math.max(A[1], C[1]) + 56, { size: 48, w: 700, align: 'center' });
      }
      x.restore();
      this.charts(x, t, S, tm, 1 - Math.max(three, fit));
    }
    if (three > 0.01) this.three(x, t, S, tm, az, three);
    if (fit > 0.01) this.fit(x, t, S, fit);
  },
  axis(x, X, Y, w, h, title, sub) {
    x.fillStyle = 'rgba(8,13,18,.80)'; rr(x, X, Y, w, h, 22); x.fill();
    x.strokeStyle = 'rgba(255,255,255,.14)'; x.lineWidth = 2; x.stroke();
    label(x, title, X + 28, Y + 60, { size: 44, w: 700 });
    if (sub) label(x, sub, X + w - 28, Y + h - 22, { size: 44, w: 500, color: '#AEB9C4', align: 'right' });
  },
  charts(x, t, S, tm, A) {
    const K = S.P.kappa, X = S.sq ? 24 : 1268, w = S.sq ? 446 : 600, col = S.color('curves.PRESSURE'), mk = S.color('measurement'), hl = S.at(t).q.hl;
    const a1 = A * S.track(t, 'c1', 0), a2 = A * S.track(t, 'c2', 0);
    if (a1 > 0.02) {
      x.save(); x.globalAlpha = a1 * (hl && hl !== 'c1' ? 0.5 : 1);
      const Y = S.sq ? 722 : 250, h = S.sq ? 252 : 370;
      this.axis(x, X, Y, w, h, S.sq ? 'вдоль пласта' : 'давление вдоль пласта', `${S.P.r_view} м`);
      const px = r => X + 28 + r / S.P.r_view * (w - 56), py = r => Y + 100 + clamp(drop(r, tm, K) / this.main) * (h - 180);
      x.beginPath(); x.moveTo(px(0), Y + h - 72);
      for (let r = 0; r <= S.P.r_view; r += 4) x.lineTo(px(r), py(r));
      x.lineTo(px(S.P.r_view), Y + h - 72); x.closePath();
      const g = x.createLinearGradient(0, Y + 90, 0, Y + h); g.addColorStop(0, rgba(col, 0.55)); g.addColorStop(1, rgba(col, 0.04)); x.fillStyle = g; x.fill();
      x.beginPath(); for (let r = 0; r <= S.P.r_view; r += 4) x.lineTo(px(r), py(r)); x.strokeStyle = col; x.lineWidth = 7; x.stroke();
      const r0 = S.P.r_obs; x.setLineDash([8, 8]); x.strokeStyle = mk; x.lineWidth = 3; x.beginPath(); x.moveTo(px(r0), Y + 92); x.lineTo(px(r0), Y + h - 72); x.stroke(); x.setLineDash([]);
      x.fillStyle = mk; x.beginPath(); x.arc(px(r0), py(r0), 13, 0, 7); x.fill();
      x.restore();
    }
    if (a2 > 0.02) {
      x.save(); x.globalAlpha = a2 * (hl && hl !== 'c2' ? 0.5 : 1);
      this.timeChart(x, S, S.sq ? 490 : X, S.sq ? 722 : 650, w, S.sq ? 252 : 370, [[K, mk, tm]], 'соседняя скважина');
      x.restore();
    }
  },
  timeChart(x, S, X, Y, w, h, list, title, o = {}) { // давление в соседней скважине от времени, шкала времени логарифмическая
    const l0 = Math.log10(60), l1 = Math.log10(S.P.t_max), top = o.top || 1, big = o.big;
    this.axis(x, X, Y, w, h, title);
    const px = l => X + 34 + (l - l0) / (l1 - l0) * (w - 90), py = v => Y + (big ? 120 : 104) + clamp(v / top) * (h - (big ? 240 : 200));
    for (const [s, n] of [[60, '1 мин'], [3600, '1 ч'], [S.P.t_max, clock(S.P.t_max).replace(' 00 мин', '')]]) {
      const l = Math.log10(s); x.strokeStyle = 'rgba(255,255,255,.16)'; x.lineWidth = 2; x.beginPath(); x.moveTo(px(l), Y + 88); x.lineTo(px(l), Y + h - 70); x.stroke();
      label(x, n, clamp(px(l), X + 40, X + w - 20), Y + h - 24, { size: 44, w: 500, color: '#AEB9C4', align: s === 60 ? 'left' : s === S.P.t_max ? 'right' : 'center' });
    }
    for (const [kap, col, upto, width] of list) {
      const le = Math.min(Math.log10(Math.max(upto, 60)), l1);
      x.beginPath();
      for (let l = l0; l <= le + 1e-6; l += 0.02) x.lineTo(px(l), py(drop(S.P.r_obs, Math.pow(10, l), kap)));
      x.strokeStyle = col; x.lineWidth = width || 7; x.lineJoin = 'round'; x.stroke();
      if (!o.nodot) { x.fillStyle = '#fff'; x.beginPath(); x.arc(px(le), py(drop(S.P.r_obs, Math.pow(10, le), kap)), 13, 0, 7); x.fill(); x.fillStyle = col; x.beginPath(); x.arc(px(le), py(drop(S.P.r_obs, Math.pow(10, le), kap)), 9, 0, 7); x.fill(); }
    }
    return { px, py };
  },
  three(x, t, S, tm, az, A) { // одно и то же время, разная пьезопроводность
    x.save();
    x.globalAlpha = A;
    const n = S.P.kappas.length;
    S.P.kappas.forEach((k, i) => {
      const cx = S.W * (i + 0.5) / n, V = { t, az, cx, cy: 660, s: S.sq ? 0.35 : 0.68, st: 0.42, ct: 0.9, D: 1500, hs: S.sq ? 150 : 190, lift: S.sq ? 210 : 250 };
      this.block(x, S, V, tm, k, { small: true });
      chip(x, num(k), cx, 872, i === 1 ? '#ECEFF4' : mix(S.color('curves.PRESSURE'), '#ffffff', 0.3), 1, { size: 64 });
    });
    label(x, 'пьезопроводность, м²/с', S.W / 2, S.sq ? 968 : 1010, { size: 48, w: 600, align: 'center', color: '#D5DCE3' });
    x.restore();
  },
  fit(x, t, S, A) { // обратная задача: по замерам подбирают коэффициент
    x.save();
    x.globalAlpha = A;
    const b0 = S.beats.find(b => (b.beat || {}).view === 'fit'), s = t - b0.t_start, X = S.sq ? 24 : 120, Y = S.sq ? 300 : 250, w = S.W - 2 * X, h = S.sq ? 680 : 720;
    const path = S.P.fit_path || [5, 0.2, 2, 0.6, 1.3, 1], T = 13, q = clamp((s - 1.2) / T) * (path.length - 1), i = Math.min(path.length - 2, Math.floor(q));
    const kap = Math.exp(lerp(Math.log(path[i]), Math.log(path[i + 1]), smooth(q - i)));
    const done = smooth((s - 1.2 - T) / 0.6), C = mix(S.color('uncertainty'), S.color('curves.PRESSURE'), done);
    const unc = S.shown(t, 'unc', 0.8, 0.4);
    const m = this.timeChart(x, S, X, Y, w, h, s > 1.2 ? [[kap, C, S.P.t_max, 9]] : [], S.sq ? 'давление от времени' : 'соседняя скважина: давление от времени', { big: true, nodot: true });
    if (unc > 0.02) { // неопределённость: полупрозрачная полоса, а не одна линия
      const l0 = Math.log10(60), l1 = Math.log10(S.P.t_max);
      x.beginPath();
      for (let l = l0; l <= l1; l += 0.02) x.lineTo(m.px(l), m.py(drop(S.P.r_obs, Math.pow(10, l), S.P.kappa * (1 + 0.7 * unc))));
      for (let l = l1; l >= l0; l -= 0.02) x.lineTo(m.px(l), m.py(drop(S.P.r_obs, Math.pow(10, l), S.P.kappa / (1 + 0.7 * unc))));
      x.closePath(); x.fillStyle = rgba(S.color('uncertainty'), 0.42 * unc); x.fill();
    }
    if (s > 1.2) { // расхождение кривой с замерами: чем ближе подбор, тем короче полоса
      const err = Math.sqrt(this.pts.reduce((q, [l, e]) => q + (drop(S.P.r_obs, Math.pow(10, l), kap) - drop(S.P.r_obs, Math.pow(10, l), S.P.kappa) - e) ** 2, 0) / this.pts.length);
      label(x, 'расхождение', X + 70, Y + 470, { size: 46, w: 600, color: '#D5DCE3' });
      x.fillStyle = 'rgba(255,255,255,.12)'; rr(x, X + 70, Y + 495, 460, 36, 18); x.fill();
      x.fillStyle = mix('#E74C3C', S.color('curves.PRESSURE'), done); rr(x, X + 70, Y + 495, Math.max(36, 460 * clamp(err / 0.35)), 36, 18); x.fill();
    }
    this.pts.forEach(([l, e], j) => {
      const a = smooth((s - j * 0.04) / 0.3); if (a <= 0) return;
      const r = 14 * outBack(a); x.fillStyle = S.color('measurement'); x.beginPath(); x.arc(m.px(l), m.py(clamp(drop(S.P.r_obs, Math.pow(10, l), S.P.kappa) + e)), r, 0, 7); x.fill();
      x.strokeStyle = '#10151B'; x.lineWidth = 3; x.stroke();
    });
    callout(x, m.px(this.pts[15][0]), m.py(drop(S.P.r_obs, Math.pow(10, this.pts[15][0]), S.P.kappa)), X + (S.sq ? 260 : 560), Y + 330, 'замеры', smooth((s - 0.8) / 0.6) * (1 - done), { color: mix(S.color('measurement'), '#ffffff', 0.2) });
    if (s > 1.2) chip(x, num(kap.toFixed(1)) + ' м²/с', X + w - (S.sq ? 150 : 250), Y + 70, done > 0.5 ? mix(S.color('curves.PRESSURE'), '#ffffff', 0.3) : '#B9C3CC', 1, { size: 60 });
    x.restore();
  },
  overlaySq(x, t, S) { // петля курса: часы под заголовком, лупа справа
    Stage.frameText(x, t, S.P.note);
    const A = S.track(t, 'clock', 0) * (1 - S.shown(t, 'view', 0.5, 0.3, 'fit'));
    if (A > 0.02) { const s = clock(this.tm), w = measure(x, s, 60, 700) + 48; x.save(); x.globalAlpha = A; x.fillStyle = 'rgba(8,13,18,.88)'; rr(x, 24, S.H - 92, w, 80, 18); x.fill(); label(x, s, 48, S.H - 32, { size: 60, w: 700, shadow: false }); x.restore(); }
    S.beats.forEach((b, j) => {
      const q = (b.beat || {}).lens; if (!q || !this.B) return;
      const end = S.beats[j + 1] ? S.beats[j + 1].t_start : S.job.total + 1, k = Math.min((t - b.t_start - (q.delay || 0.3)) / 0.5, (end - t) / 0.25); if (k <= 0) return;
      const f = this.B.W1;
      lens(x, 250, 800, 150, (f[0] + this.B.W2[0]) / 2, (f[1] + this.B.W2[1]) / 2, k, (c, r) => Pores.grains(c, r, mix(S.color('lithology.sand'), '#a8843a', 0.25), S.color('fluids.oil'), rgba(S.color('fluids.water'), 0.95), 33, 4000 - t * 60), {});
      [].concat(q.cap || []).forEach((c, i) => label(x, c, 430, 810 + i * 54, { size: 44, w: 600, a: smooth((k - 0.5) / 0.5) }));
    });
  },
  overlay(x, t, S) {
    if (S.sq) return this.overlaySq(x, t, S);
    const N = S.at(t), { W, H } = S, g = x.createLinearGradient(0, 0, 0, 260);
    g.addColorStop(0, 'rgba(6,10,14,.9)'); g.addColorStop(1, 'rgba(6,10,14,0)');
    x.fillStyle = g; x.fillRect(0, 0, W, 260);
    if (N.q.head) headline(x, S, N.q.head, N.since / 0.9 + (N.i === 0 ? 0.75 : 0), { Y: 112, size: 84, a: smooth(N.left / 0.18), maxW: W - 160 });
    badge(x, S, S.P.label || 'симуляция', S.P.note, 36);
    if (S.P.source) label(x, S.P.source, W - 80, 81, { size: 44, w: 500, color: '#D5DCE3', align: 'right' });
    const fit = S.shown(t, 'view', 0.5, 0.3, 'fit'), A = S.track(t, 'clock', 0) * (1 - fit);
    if (A > 0.02) { // часы модели
      const s = clock(this.tm), X = S.safe.side, Y = H - 150, w = Math.max(390, measure(x, s, 76, 700) + 140);
      x.save(); x.globalAlpha = A;
      x.fillStyle = 'rgba(8,13,18,.85)'; rr(x, X, Y, w, 104, 22); x.fill();
      x.strokeStyle = '#ECEFF4'; x.lineWidth = 6; x.beginPath(); x.arc(X + 56, Y + 52, 32, 0, 7); x.stroke();
      const a = this.tm / 3600 * Math.PI * 2 - Math.PI / 2, ah = this.tm / 43200 * Math.PI * 2 - Math.PI / 2;
      for (const [ang, l] of [[a, 24], [ah, 15]]) { x.beginPath(); x.moveTo(X + 56, Y + 52); x.lineTo(X + 56 + Math.cos(ang) * l, Y + 52 + Math.sin(ang) * l); x.stroke(); }
      label(x, s, X + 112, Y + 78, { size: 76, w: 700, shadow: false });
      x.restore();
    }
    S.beats.forEach((b, j) => {
      const q = (b.beat || {}).lens;
      if (!q) return;
      const end = S.beats[j + 1] ? S.beats[j + 1].t_start : S.job.total + 1, k = Math.min((t - b.t_start - (q.delay || 0.3)) / 0.5, (end - t) / 0.25);
      if (k <= 0 || !this.B) return;
      const f = this.B.W1, flow = -(t * 60);
      lens(x, q.x, q.y, q.r, (f[0] + this.B.W2[0]) / 2, (f[1] + this.B.W2[1]) / 2, k, (c, r) => Pores.grains(c, r, mix(S.color('lithology.sand'), '#a8843a', 0.25), S.color('fluids.oil'), rgba(S.color('fluids.water'), 0.95), 33, flow + 4000), { cap: q.cap });
    });
    const b = N.b;
    if (b.prediction && t > b.t_end) {
      const pr = clamp((t - b.t_end) / Math.max(0.1, N.left + t - b.t_end)), cx = 1568, cy = 620;
      x.lineWidth = 14; x.strokeStyle = 'rgba(255,255,255,.2)'; x.beginPath(); x.arc(cx, cy, 90, 0, 7); x.stroke();
      x.strokeStyle = '#F1C40F'; x.beginPath(); x.arc(cx, cy, 90, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * (1 - pr)); x.stroke();
      label(x, '?', cx, cy + 40, { size: 110, w: 700, align: 'center' });
    }
    // варианты ответа и итоговая карта
    const opt = S.shown(t, 'options', 0.4, 0.3);
    if (opt > 0.02) (S.P.options || []).forEach((s, i) => chip(x, s, 1568, 420 + i * 130 + (b.prediction && t > b.t_end ? 0 : 0), '#ECEFF4', smooth((N.since - 1.5 - i * 0.5) / 0.4) * opt * (b.prediction && t > b.t_end ? 0 : 1), { size: 64 }));
    const rec = S.shown(t, 'recap', 0.5, 0.3);
    if (rec > 0.02) {
      const L = S.P.recap, w = 1000, X = (W - w) / 2, b0 = S.beats.find(q => (q.beat || {}).recap), since = t - b0.t_start;
      x.save(); x.globalAlpha = rec;
      x.fillStyle = 'rgba(6,10,14,.6)'; x.fillRect(0, 250, W, H);
      L.forEach((s, i) => {
        const k = smooth((since - 0.3 - i * 0.5) / 0.5), y = 380 + i * 170;
        x.save(); x.globalAlpha *= k; x.translate((1 - k) * 60, 0);
        x.fillStyle = 'rgba(17,24,31,.95)'; rr(x, X, y, w, 130, 26); x.fill();
        x.fillStyle = S.color('curves.PRESSURE'); x.beginPath(); x.arc(X + 70, y + 65, 38, 0, 7); x.fill();
        label(x, String(i + 1), X + 70, y + 84, { size: 54, w: 700, color: '#10151B', align: 'center', shadow: false });
        label(x, s, X + 140, y + 84, { size: 56, w: 700, shadow: false });
        x.restore();
      });
      x.restore();
    }
  },
};

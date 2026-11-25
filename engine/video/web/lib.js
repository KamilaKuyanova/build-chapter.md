// Средства рисования для сцен роликов: камера, породы, выноски, ключевые слова, лупа. Предметного здесь нет.
// Цвета — из стайлгайда организаторов, подписи не мельче 44 px при ширине 1080, безопасная зона 9:16 соблюдается.
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const lerp = (a, b, k) => a + (b - a) * k;
const smooth = k => { k = clamp(k); return k * k * (3 - 2 * k); };
const outBack = k => { k = clamp(k); const c = 1.4; return 1 + (c + 1) * Math.pow(k - 1, 3) + c * Math.pow(k - 1, 2); };
function rng(seed) {
  let s = seed >>> 0 || 1;
  return () => {
    s = (s + 0x6D2B79F5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
function noise1(seed) {
  const r = rng(seed), v = Array.from({ length: 256 }, r);
  return x => { const i = Math.floor(x), f = x - i; return lerp(v[i & 255], v[(i + 1) & 255], f * f * (3 - 2 * f)) * 2 - 1; };
}
const hex = h => { h = h.replace('#', ''); return [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16)); };
const rgba = (c, a = 1) => { const [r, g, b] = hex(c); return `rgba(${r},${g},${b},${a})`; };
const mix = (a, b, k) => { const A = hex(a), B = hex(b); return '#' + A.map((x, i) => Math.round(lerp(x, B[i], k)).toString(16).padStart(2, '0')).join(''); };
const F = (size, w = 600) => `${w} ${size}px Bahnschrift, "Segoe UI", sans-serif`;

const Stage = {
  start(job) {
    this.job = job; this.W = job.W; this.H = job.H; this.vert = job.H > job.W * 1.4;
    this.sq = !this.vert && job.W < 1300; // почти квадрат для петель курса: при экране 390 px подпись 44 читается как 16 px
    const c = document.getElementById('c');
    c.width = job.W; c.height = job.H;
    this.cv = c;
    this.ctx = c.getContext('2d', { alpha: false });
    this.SG = job.style; this.beats = job.beats; this.P = job.params;
    const z = this.SG.safe_zone;
    this.safe = this.vert ? { top: z.top, bottom: z.bottom, side: z.side } : { top: 60, bottom: 60, side: this.sq ? 36 : 80 };
    this.grain = makeGrain(512);
    if (Scene.setup) Scene.setup(this);
  },
  color(path) {
    let v = this.SG;
    for (const k of path.split('.')) v = v[k];
    return v.color || v;
  },
  // текущая фраза и доля её хода
  at(t) {
    const B = this.beats;
    let i = 0;
    for (let k = 0; k < B.length; k++) if (t >= B[k].t_start) i = k;
    const b = B[i], next = B[i + 1] ? B[i + 1].t_start : this.job.total;
    return { i, b, q: b.beat || {}, k: clamp((t - b.t_start) / Math.max(0.01, b.t_end - b.t_start)), since: t - b.t_start, left: next - t };
  },
  // плавное значение ключа по фразам: beat[key] = число (переезд за ease секунд) или [от, до] (за время фразы)
  track(t, key, def) {
    let v = def;
    for (const b of this.beats) {
      const q = (b.beat || {})[key];
      if (q === undefined) continue;
      if (t < b.t_start) break;
      v = Array.isArray(q) ? lerp(q[0], q[1], smooth((t - b.t_start) / Math.max(0.01, b.t_end - b.t_start)))
        : lerp(v, q, smooth((t - b.t_start) / (b.beat.ease || 1.3)));
    }
    return v;
  },
  // непрозрачность предмета, который показан во фразах с beat[key]: плавно входит и уходит
  shown(t, key, inn = 0.45, out = 0.35, val) {
    const B = this.beats;
    let a = 0;
    B.forEach((b, i) => {
      const q = (b.beat || {})[key];
      if (q === undefined || (val !== undefined && q !== val)) return;
      const end = B[i + 1] ? B[i + 1].t_start : this.job.total + 9;
      const same = o => o && (o.beat || {})[key] !== undefined && (val === undefined ? key !== 'lens' : o.beat[key] === val);
      const nextSame = same(B[i + 1]);
      const prevSame = same(B[i - 1]);
      if (t < b.t_start || t > end + (nextSame ? 0 : out)) return;
      const up = prevSame ? 1 : smooth((t - b.t_start) / inn);
      const dn = nextSame ? 1 : 1 - smooth((t - end) / out);
      a = Math.max(a, Math.min(up, dn));
    });
    return a;
  },
  shot(t, q) {
    const x = this.ctx;
    x.setTransform(1, 0, 0, 1, 0, 0);
    x.globalAlpha = 1;
    Scene.draw(x, t, this);
    this.grade(x);
    if (Scene.overlay) Scene.overlay(x, t, this);
    return this.cv.toDataURL('image/jpeg', q).slice(23);
  },
  // общий верхний слой кадра: заголовок, метка, источник, отсчёт паузы на предсказание
  frameText(x, t, note) {
    const S = this, N = S.at(t), { W, H } = S, tall = S.sq && note && measure(x, S.P.label || 'схема', 44, 700) + 58 + measure(x, note, 44, 500) > W - 2 * S.safe.side, h = S.vert ? 640 : S.sq ? 310 : 250;
    const g = x.createLinearGradient(0, 0, 0, h);
    g.addColorStop(0, 'rgba(6,10,14,.94)'); g.addColorStop(0.66, 'rgba(6,10,14,.80)'); g.addColorStop(1, 'rgba(6,10,14,0)');
    x.fillStyle = g; x.fillRect(0, 0, W, h);
    if (N.q.head) headline(x, S, N.q.head, N.since / 0.9 + (N.i === 0 ? 0.75 : 0), { size: S.sq ? 66 : N.q.head_size || (S.vert ? 88 : 84), Y: S.vert ? undefined : S.sq ? (tall ? 138 : 88) : 112, a: smooth(N.left / 0.18) });
    badge(x, S, S.P.label || 'схема', tall ? null : note, S.vert ? S.safe.top - 44 : S.sq ? 20 : 36);
    if (tall) label(x, note, S.safe.side, 130, { size: 44, w: 500, color: '#D5DCE3' });
    if (S.P.source) {
      const w = measure(x, S.P.source, 44, 500) + 28, X = S.vert ? S.safe.side - 14 : S.sq ? W - w - 14 : W - 80 - w, Y = S.vert ? H - 352 : S.sq ? H - 74 : 34;
      x.fillStyle = 'rgba(8,12,17,.78)'; rr(x, X, Y, w, 64, 12); x.fill();
      label(x, S.P.source, X + 14, Y + 47, { size: 44, w: 500, color: '#D5DCE3', shadow: false });
    }
    if (N.b.prediction && t > N.b.t_end) {
      const pr = clamp((t - N.b.t_end) / Math.max(0.1, N.left + t - N.b.t_end)), cx = W / 2, cy = S.vert ? 1230 : 640;
      x.fillStyle = 'rgba(6,10,14,.6)'; x.beginPath(); x.arc(cx, cy, 120, 0, 7); x.fill();
      x.lineWidth = 12; x.strokeStyle = 'rgba(255,255,255,.2)'; x.beginPath(); x.arc(cx, cy, 80, 0, 7); x.stroke();
      x.strokeStyle = '#F1C40F'; x.beginPath(); x.arc(cx, cy, 80, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * (1 - pr)); x.stroke();
      label(x, '?', cx, cy + 34, { size: 98, w: 700, align: 'center' });
    }
    const rec = S.shown(t, 'recap', 0.5, 0.3);
    if (rec > 0.02) {
      const L = S.P.recap || [], w = S.vert ? W - 2 * S.safe.side : 1000, X = (W - w) / 2, since = t - S.beats.find(q => (q.beat || {}).recap).t_start, y0 = S.vert ? 680 : 340;
      x.save(); x.globalAlpha = rec; x.fillStyle = 'rgba(6,10,14,.62)'; x.fillRect(0, h * 0.8, W, H);
      L.forEach((s, i) => {
        const k = smooth((since - 0.3 - i * 0.5) / 0.5), y = y0 + i * 170;
        x.save(); x.globalAlpha *= k; x.translate((1 - k) * 60, 0);
        x.fillStyle = 'rgba(17,24,31,.95)'; rr(x, X, y, w, 130, 26); x.fill();
        x.fillStyle = '#F1C40F'; x.beginPath(); x.arc(X + 70, y + 65, 38, 0, 7); x.fill();
        label(x, String(i + 1), X + 70, y + 84, { size: 54, w: 700, color: '#10151B', align: 'center', shadow: false });
        label(x, s, X + 140, y + 82, { size: 50, w: 700, shadow: false });
        x.restore();
      });
      x.restore();
    }
  },
  grade(x) { // виньетка и зерно, чтобы картинка не была плоской
    const { W, H } = this;
    const g = x.createRadialGradient(W / 2, H * 0.48, Math.min(W, H) * 0.45, W / 2, H * 0.5, Math.hypot(W, H) * 0.6);
    g.addColorStop(0, 'rgba(0,0,0,0)');
    g.addColorStop(1, 'rgba(4,8,12,.6)');
    x.fillStyle = g;
    x.fillRect(0, 0, W, H);
    x.save();
    x.globalAlpha = 0.06;
    x.globalCompositeOperation = 'overlay';
    x.fillStyle = x.createPattern(this.grain, 'repeat');
    x.fillRect(0, 0, W, H);
    x.restore();
  },
};
function makeGrain(n) {
  const c = new OffscreenCanvas(n, n), x = c.getContext('2d'), d = x.createImageData(n, n), r = rng(7);
  for (let i = 0; i < d.data.length; i += 4) { const v = r() * 255; d.data[i] = d.data[i + 1] = d.data[i + 2] = v; d.data[i + 3] = 255; }
  x.putImageData(d, 0, 0);
  return c;
}

function rr(x, X, Y, w, h, r) { x.beginPath(); x.roundRect(X, Y, w, h, r); }
function label(x, s, X, Y, o = {}) {
  const { size = 46, w = 600, color = '#ECEFF4', align = 'left', base = 'alphabetic', a = 1, rot = 0, shadow = true } = o;
  x.save();
  x.globalAlpha *= a;
  x.translate(X, Y);
  if (rot) x.rotate(rot);
  x.font = F(size, w); x.textAlign = align; x.textBaseline = base;
  if (shadow) { x.shadowColor = 'rgba(0,0,0,.6)'; x.shadowBlur = size * 0.25; x.shadowOffsetY = 2; }
  x.fillStyle = color;
  x.fillText(s, 0, 0);
  x.restore();
}
function measure(x, s, size, w = 600) { x.save(); x.font = F(size, w); const m = x.measureText(s).width; x.restore(); return m; }

// Крупные ключевые слова: «слово *акцент* слово»; акцент на цветной плашке, строки въезжают снизу.
function headline(x, S, text, k, o = {}) {
  const { X = S.safe.side, Y = S.safe.top + 40, size = 92, accent = '#F1C40F', maxW = S.W - 2 * S.safe.side, align = 'left', a = 1 } = o;
  const words = [];
  let on = false;
  for (const w of text.split(' ')) {
    let s = w;
    if (s.startsWith('*')) { on = true; s = s.slice(1); }
    const last = /\*[.,!?]*$/.test(s);
    if (last) s = s.replace('*', '');
    words.push([s, on]);
    if (last) on = false;
  }
  const sp = size * 0.26, lines = [[]];
  let width = 0;
  for (const [s, acc] of words) {
    const w = measure(x, s, size, 700);
    if (width && width + w > maxW) { lines.push([]); width = 0; }
    lines[lines.length - 1].push([s, acc, w]);
    width += w + sp;
  }
  lines.forEach((ln, i) => {
    const p = smooth((k - i * 0.12) / 0.35);
    if (p <= 0) return;
    const total = ln.reduce((s, c) => s + c[2] + sp, -sp);
    let cx = align === 'center' ? X - total / 2 : X;
    const y = Y + size + i * size * 1.18 + (1 - p) * 40;
    x.save();
    x.globalAlpha *= p * a;
    for (let j = 0; j < ln.length;) {
      if (!ln[j][1]) { label(x, ln[j][0], cx, y, { size, w: 700, color: '#FFFFFF' }); cx += ln[j][2] + sp; j++; continue; }
      let e = j, ww = -sp;
      while (e < ln.length && ln[e][1]) { ww += ln[e][2] + sp; e++; }
      const gp = smooth((k - 0.25 - i * 0.12) / 0.3);
      x.fillStyle = accent;
      rr(x, cx - 14, y - size * 0.85, (ww + 28) * gp, size * 1.1, 10);
      x.fill();
      for (let m = j; m < e; m++) { label(x, ln[m][0], cx, y, { size, w: 700, color: gp > 0.5 ? '#10151B' : '#FFFFFF', shadow: gp <= 0.5 }); cx += ln[m][2] + sp; }
      j = e;
    }
    x.restore();
  });
  return lines.length * size * 1.18;
}
// Метка происхождения кадра и пометка о масштабе
function badge(x, S, text, note, Y) {
  const size = 44, X = S.safe.side, y = Y === undefined ? S.safe.top - 40 : Y;
  const w = measure(x, text, size, 700) + 36;
  x.save();
  x.fillStyle = S.SG.provenance[text];
  rr(x, X, y, w, 60, 12);
  x.fill();
  label(x, text, X + 18, y + 45, { size, w: 700, color: '#fff', shadow: false });
  if (note) label(x, note, X + w + 22, y + 45, { size, w: 500, color: '#D5DCE3' });
  x.restore();
}
// Выноска: точка на предмете, линия, подпись на тёмной плашке
function callout(x, fx, fy, tx, ty, text, k, o = {}) {
  const { size = 46, color = '#ECEFF4', bg = 'rgba(12,17,23,.86)', align = 'left' } = o;
  k = clamp(k);
  if (k <= 0) return;
  const p = smooth(k / 0.5), q = smooth((k - 0.35) / 0.5), w = measure(x, text, size, 600) + 36, h = size + 26;
  const bx = align === 'right' ? tx - w : align === 'center' ? tx - w / 2 : tx;
  const ex = clamp(fx, bx, bx + w), ey = Math.abs(fy - ty) < h / 2 ? ty : fy < ty ? ty - h / 2 : ty + h / 2;
  x.save();
  x.strokeStyle = color; x.lineWidth = 3;
  x.beginPath(); x.moveTo(fx, fy); x.lineTo(lerp(fx, ex, p), lerp(fy, ey, p)); x.stroke();
  x.fillStyle = color;
  x.beginPath(); x.arc(fx, fy, 8, 0, 7); x.fill();
  x.globalAlpha *= q;
  x.fillStyle = bg;
  rr(x, bx, ty - h / 2, w, h, 12); x.fill();
  x.strokeStyle = color; x.lineWidth = 2; x.stroke();
  label(x, text, bx + 18, ty + size * 0.35, { size, color, shadow: false });
  x.restore();
}
function chip(x, s, X, Y, col, k = 1, o = {}) {
  const size = o.size || 44, w = measure(x, s, size, 700) + 28;
  k = outBack(k);
  if (k <= 0) return;
  x.save();
  x.translate(X, Y); x.scale(k, k);
  x.fillStyle = col;
  rr(x, -w / 2, -size * 0.66, w, size * 1.3, 12); x.fill();
  label(x, s, 0, size * 0.34, { size, w: 700, color: o.ink || '#10151B', align: 'center', shadow: false });
  x.restore();
}
// Лупа: круглый крупный план с выноской к точке
function lens(x, cx, cy, r, fx, fy, k, draw, o = {}) {
  k = clamp(k);
  if (k <= 0) return;
  const R = Math.max(1, r * outBack(k)), a = Math.atan2(cy - fy, cx - fx);
  x.save();
  x.strokeStyle = 'rgba(255,255,255,.8)'; x.lineWidth = 3;
  x.setLineDash([10, 8]);
  x.beginPath(); x.moveTo(fx, fy); x.lineTo(cx - Math.cos(a) * R, cy - Math.sin(a) * R); x.stroke();
  x.setLineDash([]);
  x.beginPath(); x.arc(fx, fy, 20, 0, 7); x.stroke();
  x.shadowColor = 'rgba(0,0,0,.6)'; x.shadowBlur = 40;
  x.beginPath(); x.arc(cx, cy, R, 0, 7); x.fillStyle = '#000'; x.fill();
  x.shadowBlur = 0;
  x.save();
  x.beginPath(); x.arc(cx, cy, R, 0, 7); x.clip();
  x.translate(cx, cy); x.scale(R / r, R / r);
  draw(x, r);
  const g = x.createRadialGradient(0, -r * 0.2, r * 0.3, 0, 0, r);
  g.addColorStop(0, 'rgba(255,255,255,.05)'); g.addColorStop(1, 'rgba(0,0,0,.45)');
  x.fillStyle = g; x.fillRect(-r, -r, 2 * r, 2 * r);
  x.restore();
  x.strokeStyle = '#F4F6F8'; x.lineWidth = 8;
  x.beginPath(); x.arc(cx, cy, R, 0, 7); x.stroke();
  if (o.cap && k > 0.6) {
    x.globalAlpha *= smooth((k - 0.6) / 0.4);
    const size = 44, L = [].concat(o.cap), w = Math.max(...L.map(s => measure(x, s, size, 600))) + 36, h = 52 * L.length + 18;
    x.fillStyle = 'rgba(12,17,23,.92)';
    rr(x, cx - w / 2, cy + R - 30, w, h, 14); x.fill();
    L.forEach((s, i) => label(x, s, cx, cy + R + 16 + i * 52, { size, align: 'center', shadow: false }));
  }
  x.restore();
}

// ---- Породы. Узор строится один раз в отдельный холст, дальше только сдвигается камерой.
const Rock = {
  basement(x, X, Y, w, h, base, seed) {
    const r = rng(seed);
    x.fillStyle = mix(base, '#3a3438', 0.6); x.fillRect(X, Y, w, h);
    for (let i = 0; i < w * h / 240; i++) { x.fillStyle = rgba(['#d8c5c0', '#2b262a', '#8d7a78'][Math.floor(r() * 3)], 0.16 + r() * 0.2); const s = 2 + r() * 7; blob(x, X + r() * w, Y + r() * h, s, r() * 6); x.fill(); }
  },
  salt(x, X, Y, w, h, base, seed) {
    const r = rng(seed);
    x.fillStyle = mix(base, '#7f8f9c', 0.3); x.fillRect(X, Y, w, h);
    x.lineWidth = 2;
    for (let i = 0; i < w * h / 1500; i++) { const s = 10 + r() * 26, a = X + r() * w, b = Y + r() * h; x.strokeStyle = rgba('#ffffff', 0.2 + r() * 0.25); x.strokeRect(a, b, s, s); x.fillStyle = rgba('#ffffff', 0.06); x.fillRect(a, b, s, s); }
  },
  reef(x, X, Y, w, h, base, seed) {
    const r = rng(seed);
    x.fillStyle = mix(base, '#6b4525', 0.4); x.fillRect(X, Y, w, h);
    for (let i = 0; i < w * h / 900; i++) { const s = 6 + r() * 20; x.fillStyle = rgba(mix(base, r() < 0.6 ? '#fff1dd' : '#7a4a22', r() * 0.6), 0.55); blob(x, X + r() * w, Y + r() * h, s, r() * 6); x.fill(); x.strokeStyle = 'rgba(70,40,18,.35)'; x.lineWidth = 2; x.stroke(); }
  },
  clay(x, X, Y, w, h, base, seed) {
    const r = rng(seed);
    x.fillStyle = mix(base, '#1d2a1a', 0.25); x.fillRect(X, Y, w, h);
    for (let y = Y, k = 0; y < Y + h; y += 3 + r() * 6, k++) {
      const n = noise1(seed + k);
      x.strokeStyle = r() < 0.5 ? rgba(mix(base, '#0e150c', 0.55), 0.5) : rgba(mix(base, '#d9e8c8', 0.35), 0.28);
      x.lineWidth = 1 + r() * 3;
      x.beginPath();
      for (let i = 0; i <= w; i += 16) x.lineTo(X + i, y + n(i / 140) * 5);
      x.stroke();
    }
    for (let i = 0; i < w * h / 2600; i++) { x.fillStyle = rgba('#0e150c', 0.25 + r() * 0.25); x.fillRect(X + r() * w, Y + r() * h, 10 + r() * 34, 2 + r() * 2); }
  },
  sand(x, X, Y, w, h, base, seed, fluid) {
    const r = rng(seed);
    x.fillStyle = mix(base, '#5a4522', 0.3); x.fillRect(X, Y, w, h);
    if (fluid) { x.fillStyle = rgba(fluid, 0.5); x.fillRect(X, Y, w, h); }
    for (let i = 0; i < w * h / 40; i++) {
      const s = 1.4 + r() * 3.4;
      x.fillStyle = rgba(mix(base, r() < 0.5 ? '#fff3cf' : '#8a6a2c', r() * 0.6), 0.72);
      x.beginPath(); x.ellipse(X + r() * w, Y + r() * h, s, s * (0.6 + r() * 0.4), r() * 3, 0, 7); x.fill();
    }
    const n = noise1(seed);
    x.lineWidth = 2;
    for (let k = 0; k < h / 46; k++) {
      const y0 = Y + r() * h, x0 = X + r() * w * 0.8;
      x.strokeStyle = rgba('#5a4522', 0.28);
      x.beginPath();
      for (let i = 0; i < 260; i += 10) x.lineTo(x0 + i, y0 + i * 0.12 + n(i / 70) * 3);
      x.stroke();
    }
  },
  limestone(x, X, Y, w, h, base, seed) {
    const r = rng(seed), bh = 62;
    x.fillStyle = mix(base, '#31485a', 0.55); x.fillRect(X, Y, w, h);
    for (let y = Y, row = 0; y < Y + h; y += bh, row++) {
      for (let px = X - (row % 2) * 80 - r() * 40; px < X + w;) {
        const bw = 130 + r() * 70;
        x.fillStyle = mix(mix(base, '#50667a', 0.35), r() < 0.5 ? '#dfeaf2' : '#456076', r() * 0.3);
        x.fillRect(px + 2, y + 2, bw - 4, bh - 4);
        px += bw;
      }
    }
    for (let i = 0; i < w * h / 420; i++) { x.fillStyle = rgba(r() < 0.5 ? '#eef5fa' : '#33495a', 0.1 + r() * 0.15); const s = 1 + r() * 4; x.fillRect(X + r() * w, Y + r() * h, s, s); }
    x.strokeStyle = rgba('#243645', 0.35); x.lineWidth = 2;
    for (let k = 0; k < h / 130; k++) {
      let cx = X + r() * w, cy = Y + r() * h;
      x.beginPath(); x.moveTo(cx, cy);
      for (let j = 0; j < 6; j++) { cx += 20 + r() * 26; cy += (r() - 0.5) * 44; x.lineTo(cx, cy); }
      x.stroke();
    }
  },
};
function blob(x, cx, cy, s, a) {
  x.beginPath();
  for (let i = 0; i <= 24; i++) {
    const t = i / 24 * Math.PI * 2, k = s * (1 + 0.09 * Math.sin(3 * t + a) + 0.06 * Math.sin(5 * t + a * 2));
    x.lineTo(cx + Math.cos(t) * k, cy + Math.sin(t) * k * 0.92);
  }
  x.closePath();
}
// Крупный план пор: зёрна, плёнка на зёрнах и заполнение между ними; без пор — сомкнутые кристаллы.
const Pores = {
  grains(x, r, base, fill, film, seed, flow = 0, o = {}) { // o.grow — цемент на зёрнах 0..1, o.vug — каверны 0..1
    const q = rng(seed), G = [];
    for (let gy = -3; gy <= 3; gy++) for (let gx = -3; gx <= 3; gx++) G.push([gx * r * 0.46 + (gy & 1) * r * 0.23 + (q() - 0.5) * r * 0.1, gy * r * 0.42 + (q() - 0.5) * r * 0.1, r * (0.2 + q() * 0.05), q() * 6]);
    x.fillStyle = fill; x.fillRect(-r, -r, 2 * r, 2 * r);
    if (flow) {
      const p = rng(seed + 3);
      for (let i = 0; i < 70; i++) {
        const px = ((p() * 2 * r + flow * (0.6 + p() * 0.5)) % (2 * r)) - r, py = (p() * 2 - 1) * r;
        x.fillStyle = 'rgba(255,255,255,.4)'; x.beginPath(); x.arc(px, py, 3.5, 0, 7); x.fill();
      }
    }
    for (const [gx, gy, s, a] of G) {
      if (film) { x.fillStyle = film; blob(x, gx, gy, s * (o.grow ? 1 + 0.42 * o.grow : 1.12), a); x.fill(); }
      const g = x.createRadialGradient(gx - s * 0.35, gy - s * 0.4, s * 0.1, gx, gy, s * 1.1);
      g.addColorStop(0, mix(base, '#ffffff', 0.45)); g.addColorStop(0.6, base); g.addColorStop(1, mix(base, '#4b3512', 0.55));
      x.fillStyle = g; blob(x, gx, gy, s, a); x.fill();
    }
    if (o.vug) for (const [vx, vy, vs] of [[-0.3, -0.15, 0.36], [0.38, 0.3, 0.44], [0.1, -0.6, 0.26], [-0.55, 0.5, 0.22]]) { x.fillStyle = fill; blob(x, vx * r, vy * r, vs * r * o.vug, vs * 9); x.fill(); x.strokeStyle = 'rgba(20,24,28,.5)'; x.lineWidth = 4; x.stroke(); }
  },
  crystals(x, r, base, seed) {
    const q = rng(seed), n = 6, st = 2.6 * r / n, pt = [];
    for (let j = 0; j <= n; j++) { pt.push([]); for (let i = 0; i <= n; i++) pt[j].push([-1.3 * r + i * st + (q() - 0.5) * st * 0.55, -1.3 * r + j * st + (q() - 0.5) * st * 0.55]); }
    for (let j = 0; j < n; j++) for (let i = 0; i < n; i++) {
      const c = [pt[j][i], pt[j][i + 1], pt[j + 1][i + 1], pt[j + 1][i]];
      const g = x.createLinearGradient(c[0][0], c[0][1], c[2][0], c[2][1]);
      g.addColorStop(0, mix(base, '#ffffff', 0.25 + q() * 0.35)); g.addColorStop(1, mix(base, '#2f4557', 0.15 + q() * 0.3));
      x.fillStyle = g;
      x.beginPath(); for (const p of c) x.lineTo(p[0], p[1]); x.closePath(); x.fill();
      x.strokeStyle = 'rgba(25,40,52,.55)'; x.lineWidth = 3; x.stroke();
    }
  },
};

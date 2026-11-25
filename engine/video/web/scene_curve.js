// Сцена «формула работает»: полоса пласта сверху и график снизу считаются одной формулой при одном значении параметра p.
// Параметры: x [от, до], y [от, до], xlog, xname, yname, p {kind: time|num, name, unit}, curves [{expr, color, name, dash}], ghosts [p],
// strip {expr 0..1, left: gallery|well, name}, front — формула границы по p, zero — закрасить ниже нуля, marks [{x, text}], source, assumptions.
// beat: p число или [от, до] (или lp — десятичный логарифм), c0, c1, c2 0..1, ghosts 0..1, strip 0..1, marks 0..1, front 0..1, zero 0..1, recap, head.
const erf = x => { const s = Math.sign(x), a = Math.abs(x), t = 1 / (1 + 0.5 * a); return s * (1 - t * Math.exp(-a * a - 1.26551223 + t * (1.00002368 + t * (0.37409196 + t * (0.09678418 + t * (-0.18628806 + t * (0.27886807 + t * (-1.13520398 + t * (1.48851587 + t * (-0.82215223 + t * 0.17087277)))))))))); };
function E1(x) {
  if (x <= 0) return 50;
  if (x <= 1) { let s = -0.5772156649 - Math.log(x), f = 1, p = 1; for (let k = 1; k < 30; k++) { f *= k; p *= x; s += ((k % 2) ? 1 : -1) * p / (k * f); } return s; }
  return (x * x + 2.334733 * x + 0.250621) / (x * x + 3.330657 * x + 1.681534) * Math.exp(-x) / x;
}
const MATH = { exp: Math.exp, log: Math.log, log10: Math.log10, sqrt: Math.sqrt, pow: Math.pow, min: Math.min, max: Math.max, abs: Math.abs, sin: Math.sin, cos: Math.cos, erf, E1, pi: Math.PI };
function compile(expr) { // в формуле разрешены только числа, x, p и функции из списка
  for (const w of expr.match(/[A-Za-z_]\w*/g) || []) if (!(w in MATH) && w !== 'x' && w !== 'p') throw new Error('в формуле нельзя: ' + w);
  if (/[^\w\s.+\-*/(),<>?:=]/.test(expr)) throw new Error('лишний знак в формуле: ' + expr);
  return new Function('x', 'p', ...Object.keys(MATH), 'return ' + expr).bind(null);
}
const call = (f, x, p) => f(x, p, ...Object.values(MATH));
const splitTwo = s => { const w = s.split(' '), n = Math.ceil(w.length / 2); return [w.slice(0, n).join(' '), w.slice(n).join(' ')]; };
const ptext = (P, v) => P.p.kind === 'time' ? (v < 600 ? `${Math.round(v)} с` : v < 3600 ? `${Math.round(v / 60)} мин` : v < 172800 ? `${String(Math.round(v / 360) / 10).replace('.', ',')} ч` : `${Math.round(v / 86400)} сут`) : `${String(+v.toPrecision(3)).replace('.', ',')} ${P.p.unit || ''}`;
const Scene = {
  setup(S) {
    const P = S.P;
    this.f = P.curves.map(c => compile(c.expr));
    this.strip = P.strip ? compile(P.strip.expr) : null;
    this.front = P.front ? compile(P.front) : null;
    const c = new OffscreenCanvas(1900, 260), x = c.getContext('2d');
    Rock.sand(x, 0, 0, 1900, 260, S.color('lithology.sand'), 4, null);
    this.sand = c;
    const r = rng(6);
    this.seeds = Array.from({ length: 130 }, () => [r(), r(), r()]);
  },
  draw(x, t, S) {
    const P = S.P, { W, H } = S, g = x.createLinearGradient(0, 0, 0, H);
    g.addColorStop(0, '#0c141c'); g.addColorStop(0.5, '#15222e'); g.addColorStop(1, '#0a1016');
    x.fillStyle = g; x.fillRect(0, 0, W, H);
    const start = k => { const b = S.beats.find(q => (q.beat || {})[k] !== undefined); return b ? [].concat(b.beat[k])[0] : null; };
    const l0 = start('lp'), p = l0 === null ? S.track(t, 'p', start('p') === null ? 1 : start('p')) : Math.pow(10, S.track(t, 'lp', l0));
    const hasStrip = this.strip && S.track(t, 'strip', 1) > 0.02, box = S.sq ? { X: 20, Y: hasStrip ? 510 : 320, w: W - 40, h: hasStrip ? H - 600 : H - 410 } : { X: 90, Y: hasStrip ? 500 : 250, w: W - 180, h: hasStrip ? H - 560 : H - 310 };
    const fx = P.xlog ? Math.log10 : v => v, x0 = fx(P.x[0]), x1 = fx(P.x[1]), xn = S.sq && measure(x, P.xname, 44, 500) > box.w - 130 ? splitTwo(P.xname) : [P.xname], GX = box.X + (S.sq ? 84 : 60), GW = box.w - (S.sq ? 130 : 110), GY = box.Y + 84, GH = box.h - 215 - (xn.length - 1) * 50;
    const px = v => GX + (fx(v) - x0) / (x1 - x0) * GW, py = v => GY + (1 - (v - P.y[0]) / (P.y[1] - P.y[0])) * GH, inv = q => { const l = lerp(x0, x1, q); return P.xlog ? Math.pow(10, l) : l; };
    if (hasStrip) { // полоса пласта над графиком: точка пласта стоит ровно над своей точкой кривой
      const a = S.track(t, 'strip', 1), Y = S.sq ? 320 : 262, h = S.sq ? 160 : 170, col = S.color('curves.PRESSURE'), N = 120;
      x.save(); x.globalAlpha = a;
      x.save(); rr(x, GX, Y, GW, h, 10); x.clip(); x.drawImage(this.sand, GX, Y, GW, h);
      for (let i = 0; i < N; i++) { const v = clamp(call(this.strip, inv((i + 0.5) / N), p)); x.fillStyle = rgba(v < 0.5 ? mix('#16324a', mix(col, '#16324a', 0.45), v * 2) : mix(mix(col, '#16324a', 0.45), mix(col, '#ffffff', 0.4), v * 2 - 1), 0.78); x.fillRect(GX + GW * i / N, Y, GW / N + 1, h); }
      for (const [u, v, w] of this.seeds) { // жидкость движется туда, где давление ниже; быстрее там, где перепад круче
        const q = 1 - ((u + t * (0.02 + 0.03 * w)) % 1), d = Math.abs(call(this.strip, inv(Math.min(1, q + 0.01)), p) - call(this.strip, inv(Math.max(0.0001, q - 0.01)), p)) * 14, al = clamp(d) * 0.9;
        if (al < 0.04) continue;
        x.strokeStyle = `rgba(255,255,255,${al})`; x.lineWidth = 3; x.beginPath(); x.moveTo(GX + q * GW, Y + 14 + v * (h - 28)); x.lineTo(GX + q * GW + 10 + 22 * al, Y + 14 + v * (h - 28)); x.stroke();
      }
      x.restore();
      const m = x.createLinearGradient(GX - 26, 0, GX, 0); m.addColorStop(0, '#2c333b'); m.addColorStop(0.4, '#f1f5f8'); m.addColorStop(1, '#2c333b');
      if (P.strip.wall !== false) { x.fillStyle = m; x.fillRect(GX - 26, Y - 20, 26, h + 40); }
      if (P.strip.name) label(x, P.strip.name, GX + GW - 16, Y + h - 18, { size: 44, w: 700, align: 'right' });
      if (this.front && S.track(t, 'front', 0) > 0.02) { const X = px(clamp(call(this.front, 0, p), P.x[0], P.x[1])); x.globalAlpha = a * S.track(t, 'front', 0); x.strokeStyle = '#F1C40F'; x.lineWidth = 6; x.setLineDash([16, 10]); x.beginPath(); x.moveTo(X, Y - 10); x.lineTo(X, GY + GH); x.stroke(); x.setLineDash([]); }
      x.restore();
    }
    x.fillStyle = 'rgba(8,13,18,.80)'; rr(x, box.X, box.Y, box.w, box.h, 22); x.fill();
    x.strokeStyle = 'rgba(255,255,255,.14)'; x.lineWidth = 2; x.stroke();
    label(x, P.yname, GX, box.Y + 58, { size: 44, w: 600, color: '#D5DCE3' });
    xn.forEach((s, i) => label(x, s, GX + GW, box.Y + box.h - 22 - (xn.length - 1 - i) * 50, { size: 44, w: 500, color: '#AEB9C4', align: 'right' }));
    for (const v of P.yticks || []) { x.strokeStyle = 'rgba(255,255,255,.12)'; x.lineWidth = 2; x.beginPath(); x.moveTo(GX, py(v)); x.lineTo(GX + GW, py(v)); x.stroke(); label(x, String(v).replace('.', ',').replace('-', '−'), GX - 14, py(v) + 15, { size: 44, color: '#AEB9C4', align: 'right' }); }
    let lastX = -1e9;
    for (const v of P.xticks || []) if (px(v) - lastX > measure(x, String(v), 44, 600) + 34 && (lastX = px(v)) > -1) label(x, String(v).replace('.', ','), px(v), GY + GH + 50, { size: 44, color: '#AEB9C4', align: 'center', a: 0.9 });
    if (P.y[0] < 0) { const z = S.track(t, 'zero', 0); if (z > 0.02) { x.fillStyle = `rgba(231,76,60,${0.28 * z})`; x.fillRect(GX, py(0), GW, GY + GH - py(0)); } x.strokeStyle = 'rgba(255,255,255,.5)'; x.lineWidth = 3; x.beginPath(); x.moveTo(GX, py(0)); x.lineTo(GX + GW, py(0)); x.stroke(); }
    x.save(); rr(x, GX, GY - 6, GW + 4, GH + 12, 2); x.clip();
    const line = (f, pv, col, w, dash, upto = 1) => { x.beginPath(); for (let i = 0; i <= 240; i++) { const q = i / 240; if (q > upto) break; const xv = inv(q), v = call(f, xv, pv); if (Number.isFinite(v)) x.lineTo(px(xv), py(v)); } x.strokeStyle = col; x.lineWidth = w; x.lineJoin = 'round'; x.setLineDash(dash ? [18, 12] : []); x.stroke(); x.setLineDash([]); };
    const gk = S.track(t, 'ghosts', 0);
    if (gk > 0.02) (P.ghosts || []).forEach(g2 => { if (g2 < p * 0.97 || P.ghosts_all) { x.globalAlpha = 0.5 * gk; line(this.f[0], g2, '#95A5A6', 5); } });
    x.globalAlpha = 1;
    P.curves.forEach((c, i) => {
      const a = S.track(t, 'c' + i, i === 0 ? 1 : 0); if (a < 0.02) return;
      const col = S.color(c.color || 'curves.PRESSURE'), up = P.draw_to_p ? clamp((fx(p) - x0) / (x1 - x0)) : 1;
      x.save(); x.globalAlpha = a; x.shadowColor = col; x.shadowBlur = c.dash ? 0 : 14;
      line(this.f[i], p, col, 8, c.dash, up); x.restore();
      if (P.draw_to_p) { const xv = Math.max(P.x[0], Math.min(P.x[1], p)), v = call(this.f[i], xv, p); x.fillStyle = '#fff'; x.beginPath(); x.arc(px(xv), py(v), 15, 0, 7); x.fill(); x.fillStyle = col; x.beginPath(); x.arc(px(xv), py(v), 10, 0, 7); x.fill(); }
    });
    x.restore();
    P.curves.forEach((c, i) => { const a = S.track(t, 'c' + i, i === 0 ? 1 : 0); if (c.name && a > 0.02) label(x, c.name, GX + GW - 10, GY + GH - 30 - (P.curves.length - 1 - i) * 56, { size: 44, w: 700, color: mix(S.color(c.color || 'curves.PRESSURE'), '#ffffff', 0.25), align: 'right', a }); });
    const mk = S.track(t, 'marks', 0);
    if (mk > 0.02) (P.marks || []).forEach(m => { const v = call(this.f[m.curve || 0], m.x, p); callout(x, px(m.x), py(v), clamp(px(m.x) + (m.dx === undefined ? 60 : m.dx) * (S.sq ? 0.6 : 1), 40, W - 60 - measure(x, m.text, 46, 600)), py(v) + (m.dy === undefined ? -90 : m.dy), m.text, mk, { color: '#F5E29A' }); });
    if (!P.p.hide) { const s = `${P.p.name ? P.p.name + ' ' : ''}${ptext(P, p)}`; chip(x, s, S.sq ? W - 112 : W / 2, box.Y + 46, '#ECEFF4', 1, { size: 52 }); }
  },
  overlay(x, t, S) { Stage.frameText(x, t, S.P.note || 'расчёт по формуле главы'); },
};

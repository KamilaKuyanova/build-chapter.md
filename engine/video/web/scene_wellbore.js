// Сцена «скважина при бурении»: ствол, колонны, раствор, шлам, приток газа, поглощение и давления по глубине.
// Все давления — из одной модели: раствор ρ·g·h, при притоке газа в закрытой скважине пачка сохраняет давление и поднимает его везде.
// Параметры: depth, layers, casings, mud (г/см³), pore [[м, МПа]], frac [[м, МПа]], p_max, gas_from (м).
// beat: cam, span, bit, pump 0..1, drill 0..1, mud, gas (глубина верха пачки), gas_on 0..1, closed 0..1, loss 0..1, loss_at, pit 0..1, graph 0..1, show [pore, frac, mud], head, call, lens.
// Единицы книги: grad — давление на единицу глубины при плотности 1 (9.81e-3 для м, МПа и г/см³; 0.052 для ft, psi и ppg); friction — добавка трения на забое при циркуляции.
const interp = (A, d) => { if (d <= A[0][0]) return A[0][1]; for (let i = 1; i < A.length; i++) if (d <= A[i][0]) return lerp(A[i - 1][1], A[i][1], (d - A[i - 1][0]) / (A[i][0] - A[i - 1][0])); return A[A.length - 1][1]; };
const Scene = {
  setup(S) {
    this.tiles = S.P.layers.map((L, i) => {
      const c = new OffscreenCanvas(1000, 620), x = c.getContext('2d');
      Rock[L.rock](x, 0, 0, 1000, 620, S.color(L.color), 50 + i, L.fluid ? S.color(L.fluid) : null);
      return c;
    });
    const r = rng(5);
    this.flow = Array.from({ length: 150 }, () => [r(), r(), r()]);
    this.hn = noise1(8);
  },
  layout(S) { return S.sq ? { bx: 430, R: 70, gx: 590, gw: S.W - 590 - 20 } : S.vert ? { bx: 250, R: 92, gx: 575, gw: S.W - 575 - S.safe.side } : { bx: 620, R: 105, gx: 1180, gw: S.W - 1180 - 80 }; },
  state(S, t) {
    const P = S.P, G = P.grad || 9.81e-3, s = { cam: S.track(t, 'cam', P.depth / 2), span: S.track(t, 'span', P.depth * 1.15), bit: S.track(t, 'bit', P.depth), pump: S.track(t, 'pump', 0), drill: S.track(t, 'drill', 0),
      mud: S.track(t, 'mud', P.mud), gas: S.track(t, 'gas', P.gas_from || P.depth), gasOn: S.track(t, 'gas_on', 0), closed: S.track(t, 'closed', 0), loss: S.track(t, 'loss', 0), pit: S.track(t, 'pit', 0.5), graph: S.track(t, 'graph', 1) };
    s.y = d => S.H / 2 + (d - s.cam) / s.span * S.H;
    s.dAt = y => s.cam + (y - S.H / 2) / S.H * s.span;
    const from = P.gas_from || P.depth, den = P.in_density;
    s.pres = (A, d) => den ? interp(A, d) * G * d : interp(A, d); // пределы могут быть даны плотностью
    s.show = (p, d) => den ? p / (G * Math.max(d, P.depth * 0.02)) : p;
    const pk = s.pres(P.pore, from);
    // давление в стволе: столб раствора, при циркуляции больше; газ в закрытой скважине несёт пластовое давление вверх
    s.p = d => {
      const stat = s.mud * G * d * (P.friction ? 1 : 1 + 0.04 * s.pump) + (P.friction || 0) * s.pump * d / P.depth;
      if (s.gasOn < 0.01) return stat;
      const open = d > s.gas ? stat - s.mud * G * Math.min(P.depth * 0.05, d - s.gas) * 0.6 * s.gasOn : stat;
      const shut = Math.max(0, pk + s.mud * G * (d - s.gas));
      return lerp(stat, lerp(open, shut, s.closed), s.gasOn);
    };
    return s;
  },
  draw(x, t, S) {
    const P = S.P, { W, H } = S, A = this.layout(S), s = this.state(S, t);
    this.s = s; this.A = A;
    x.fillStyle = '#0b1015'; x.fillRect(0, 0, W, H);
    const y0 = s.y(0);
    if (y0 > 0) this.surface(x, t, S, A, s, y0);
    P.layers.forEach((L, i) => {
      const a = s.y(L.top), b = i === P.layers.length - 1 ? H + 50 : s.y(L.bot);
      if (b < 0 || a > H) return;
      const pat = x.createPattern(this.tiles[i], 'repeat');
      pat.setTransform(new DOMMatrix().translate(0, a));
      x.fillStyle = pat; x.fillRect(0, a, W, b - a);
      const g = x.createLinearGradient(0, a, 0, a + 40); g.addColorStop(0, 'rgba(0,0,0,.45)'); g.addColorStop(1, 'rgba(0,0,0,0)'); x.fillStyle = g; x.fillRect(0, a, W, 40);
    });
    this.hole(x, t, S, A, s);
    if (s.graph > 0.02) this.graph(x, t, S, A, s);
    this.names(x, t, S, A, s);
  },
  surface(x, t, S, A, s, y0) {
    const g = x.createLinearGradient(0, y0 - 900, 0, y0); g.addColorStop(0, '#16283a'); g.addColorStop(0.7, '#3d5a70'); g.addColorStop(1, '#d99a62');
    x.fillStyle = g; x.fillRect(0, 0, S.W, y0);
    const cx = A.bx, hT = 330; // вышка: решётчатая, стоит только при бурении
    x.strokeStyle = '#10161c'; x.lineWidth = 7;
    for (const q of [-1, 1]) { x.beginPath(); x.moveTo(cx + q * 95, y0); x.lineTo(cx + q * 26, y0 - hT); x.stroke(); }
    x.lineWidth = 4;
    for (let i = 0; i < 7; i++) { const a = i / 7, b = (i + 1) / 7, w = k => lerp(95, 26, k); x.beginPath(); x.moveTo(cx - w(a), y0 - hT * a); x.lineTo(cx + w(b), y0 - hT * b); x.moveTo(cx + w(a), y0 - hT * a); x.lineTo(cx - w(b), y0 - hT * b); x.moveTo(cx - w(b), y0 - hT * b); x.lineTo(cx + w(b), y0 - hT * b); x.stroke(); }
    x.fillStyle = '#10161c'; x.fillRect(cx - 30, y0 - hT - 18, 60, 20);
    // превентор на устье
    x.fillStyle = s.closed > 0.5 ? '#E74C3C' : '#AEB9C4'; rr(x, cx - A.R * 0.75, y0 - 52, A.R * 1.5, 46, 10); x.fill();
  },
  hole(x, t, S, A, s) {
    const P = S.P, { H } = S, R = A.R, cx = A.bx, yb = s.y(s.bit), yt = Math.max(-40, s.y(0)), mud = S.color('fluids.mud'), m2 = mix(mud, '#000000', clamp((s.mud / (P.water || 1) - 1) * 0.35));
    const rad = d => { let r = R; for (const c of P.casings || []) if (d < c.shoe) r = Math.max(r * 0 + R * (c.r || 1.12), r); return r + (this.cased(P, d) ? 0 : this.hn(d / s.span * 60) * 5); };
    const step = 6, pts = []; // контур ствола
    for (let y = yt; y <= Math.min(yb, H + 40); y += step) pts.push([rad(s.dAt(y)), y]);
    for (const L of P.layers) if (L.perm && s.loss > 0.02 && L.id === S.P.loss_layer) { // поглощение: трещины и уход раствора
      const yc = s.y((L.top + L.bot) / 2), r = rng(91);
      for (const q of [-1, 1]) for (let i = 0; i < 4; i++) { let X = cx + q * R, Y = yc + (i - 1.5) * 34; x.strokeStyle = mix(m2, '#cbb894', 0.25); x.lineWidth = 11 - i; x.beginPath(); x.moveTo(X, Y); for (let k = 0; k < 7 * s.loss; k++) { X += q * (22 + r() * 18); Y += (r() - 0.5) * 36; x.lineTo(X, Y); } x.stroke(); }
    }
    x.save();
    x.beginPath();
    pts.forEach(p => x.lineTo(cx - p[0], p[1]));
    pts.slice().reverse().forEach(p => x.lineTo(cx + p[0], p[1]));
    x.closePath();
    const g = x.createLinearGradient(cx - R, 0, cx + R, 0); g.addColorStop(0, mix(m2, '#000000', 0.5)); g.addColorStop(0.35, mix(m2, '#e6d6b8', 0.16)); g.addColorStop(1, mix(m2, '#000000', 0.55));
    x.shadowColor = 'rgba(0,0,0,.75)'; x.shadowBlur = 30; x.fillStyle = g; x.fill(); x.shadowBlur = 0;
    x.clip();
    const top = Math.max(yt, 0), bot = Math.min(yb, H), span = Math.max(1, bot - top), pr = R * 0.34;
    if (s.pump > 0.02) for (const [a, b, c] of this.flow) { // вниз по трубам, вверх по затрубью
      const v = (t * (0.16 + c * 0.06) * s.pump + a) % 1;
      x.fillStyle = `rgba(245,230,200,${0.22 + 0.2 * b})`;
      if (c < 0.3) { x.beginPath(); x.arc(cx + (b - 0.5) * pr, top + v * span, 4, 0, 7); x.fill(); }
      else { const q = b < 0.5 ? -1 : 1; x.beginPath(); x.arc(cx + q * lerp(pr + 14, R - 8, (b * 2) % 1), bot - v * span, 4.5, 0, 7); x.fill(); }
    }
    if (s.drill > 0.02) { const L = this.layerAt(P, s.bit), col = S.color(L.color), r = rng(12); for (let i = 0; i < 70 * s.drill; i++) { const v = (t * (0.11 + r() * 0.05) * Math.max(0.2, s.pump) + r()) % 1, q = r() < 0.5 ? -1 : 1; x.fillStyle = mix(col, '#ffffff', r() * 0.3); const X = cx + q * lerp(pr + 16, R - 10, r()), Y = bot - v * span, a = 5 + r() * 8; x.beginPath(); x.moveTo(X - a, Y); x.lineTo(X, Y - a * 0.7); x.lineTo(X + a, Y + a * 0.2); x.lineTo(X, Y + a * 0.8); x.closePath(); x.fill(); } }
    if (s.gasOn > 0.02) { // газовая пачка: в открытой скважине растёт к устью, в закрытой почти не меняется
      const p0 = s.pres(P.pore, P.gas_from || P.depth), pNow = Math.max(p0 * 0.012, s.p(s.gas)), k = lerp(Math.min(6, p0 / pNow), 1, s.closed), len = clamp(P.depth * 0.035 * k / s.span * H, 60, 900), yTop = s.y(s.gas), r = rng(33);
      const n = Math.round(60 * s.gasOn * Math.min(2.4, k));
      for (let i = 0; i < n; i++) { const a = 5 + r() * 9 * Math.cbrt(k), q = r() < 0.5 ? -1 : 1, Y = yTop + r() * len + Math.sin(t * 3 + i) * 5, X = cx + q * lerp(pr + 12, R - 6, r()) + Math.sin(t * 2 + i * 2) * 4; if (Y > bot) continue; x.fillStyle = rgba(S.color('fluids.gas'), 0.85); x.beginPath(); x.arc(X, Y, a, 0, 7); x.fill(); x.fillStyle = 'rgba(255,255,255,.55)'; x.beginPath(); x.arc(X - a * 0.3, Y - a * 0.3, a * 0.28, 0, 7); x.fill(); }
    }
    // бурильная колонна и долото
    const steel = (w) => { const q = x.createLinearGradient(cx - w, 0, cx + w, 0); q.addColorStop(0, '#2a3138'); q.addColorStop(0.3, '#dfe6ec'); q.addColorStop(0.65, '#8d98a3'); q.addColorStop(1, '#20262c'); return q; };
    if (S.P.string !== false) {
      x.fillStyle = steel(pr); x.fillRect(cx - pr, yt, pr * 2, yb - yt - 60);
      x.fillStyle = mix(m2, '#e6d6b8', 0.1); x.fillRect(cx - pr * 0.42, yt, pr * 0.84, yb - yt - 60);
      x.fillStyle = 'rgba(0,0,0,.35)'; for (let y = yb - 60; y > yt; y -= 170) x.fillRect(cx - pr * 1.08, y - 16, pr * 2.16, 12);
      x.fillStyle = steel(pr * 1.5); rr(x, cx - pr * 1.5, yb - 200, pr * 3, 130, 10); x.fill();
      const rot = t * 7 * Math.max(s.drill, 0.0);
      x.fillStyle = steel(R * 0.92); x.beginPath(); x.moveTo(cx - pr * 1.4, yb - 74); x.lineTo(cx + pr * 1.4, yb - 74); x.lineTo(cx + R * 0.94, yb - 26); x.lineTo(cx - R * 0.94, yb - 26); x.closePath(); x.fill();
      for (let i = 0; i < 7; i++) { const u = ((i + rot) % 7) / 7, X = cx - R * 0.9 + u * R * 1.8; x.fillStyle = u < 0.5 ? '#9aa5b0' : '#5d6771'; x.beginPath(); x.moveTo(X, yb - 28); x.lineTo(X + R * 0.24, yb - 28); x.lineTo(X + R * 0.12, yb - 2); x.closePath(); x.fill(); }
    }
    x.restore();
    for (const c of P.casings || []) { // обсадные колонны с цементом и башмаком
      const ys = s.y(c.shoe), r = R * (c.r || 1.12);
      for (const q of [-1, 1]) {
        x.fillStyle = 'rgba(150,158,166,.85)'; x.fillRect(q < 0 ? cx - r - 34 : cx + r + 12, yt, 22, ys - yt);
        x.fillStyle = 'rgba(40,46,52,.5)'; for (let y = yt; y < ys; y += 16) x.fillRect(q < 0 ? cx - r - 34 : cx + r + 12, y, 22, 3);
        const g2 = x.createLinearGradient(cx + q * r, 0, cx + q * (r + 12), 0); g2.addColorStop(0, '#3a424b'); g2.addColorStop(0.5, '#e8eef3'); g2.addColorStop(1, '#4b555f');
        x.fillStyle = g2; x.fillRect(q < 0 ? cx - r - 12 : cx + r, yt, 12, ys - yt);
        x.fillStyle = '#c9d2da'; x.beginPath(); x.moveTo(cx + q * r, ys); x.lineTo(cx + q * (r + 40), ys); x.lineTo(cx + q * r, ys - 46); x.closePath(); x.fill();
      }
    }
  },
  cased(P, d) { return (P.casings || []).some(c => d < c.shoe); },
  layerAt(P, d) { return P.layers.find(l => d >= l.top && d < l.bot) || P.layers[P.layers.length - 1]; },
  graph(x, t, S, A, s) { // давление по глубине на той же шкале глубин, что и ствол
    const P = S.P, { H } = S, X = A.gx, w = A.gw, pm = P.p_min || 0, px = p => X + 16 + clamp((p - pm) / (P.p_max - pm)) * (w - 32), yt = Math.max(0, s.y(0)), yb = H;
    x.save();
    x.globalAlpha = s.graph;
    x.fillStyle = 'rgba(8,13,18,.86)'; x.fillRect(X, yt, w, yb - yt);
    x.strokeStyle = 'rgba(255,255,255,.12)'; x.lineWidth = 2;
    for (let i = 1; i < 4; i++) { x.beginPath(); x.moveTo(X + w * i / 4, yt); x.lineTo(X + w * i / 4, yb); x.stroke(); }
    const line = (f, col, dash, lw, d1) => { x.beginPath(); for (let y = yt; y <= Math.min(yb, s.y(d1)); y += 5) { const d = s.dAt(y); x.lineTo(px(s.show(f(d), d)), y); }; x.strokeStyle = col; x.lineWidth = lw; x.setLineDash(dash); x.lineJoin = 'round'; x.stroke(); x.setLineDash([]); };
    const a = k => S.track(t, 'show_' + k, 0), water = S.color('fluids.water'), red = '#E74C3C', mudc = S.color('curves.PRESSURE');
    const bad = []; // где раствор ниже пластового или выше предела прочности
    x.save(); x.globalAlpha *= a('pore'); line(d => s.pres(P.pore, d), water, [], 7, P.depth); x.restore();
    if (P.frac) { x.save(); x.globalAlpha *= a('frac'); line(d => s.pres(P.frac, d), red, [16, 10], 7, P.depth); x.restore(); }
    x.save(); x.globalAlpha *= a('mud'); x.shadowColor = mudc; x.shadowBlur = 16; line(s.p, mudc, [], 10, s.bit);
    const pb = s.p(s.bit); x.fillStyle = '#fff'; x.beginPath(); x.arc(px(s.show(pb, s.bit)), s.y(s.bit), 15, 0, 7); x.fill(); x.restore();
    void bad;
    const key = [['pore', 'пластовое', water], ['mud', 'раствор', mudc]].concat(P.frac ? [['frac', 'разрыв породы', red]] : []);
    let ky = S.sq ? 300 : S.vert ? 700 : 280;
    for (const [k, n, col] of key) { const al = a(k); if (al < 0.02) continue; const kw = measure(x, n, 44, 700); x.save(); x.globalAlpha = al * s.graph; x.fillStyle = 'rgba(8,13,18,.88)'; rr(x, X + w - 28 - kw, ky - 44, kw + 24, 56, 8); x.fill(); x.restore(); label(x, n, X + w - 16, ky, { size: 44, w: 700, color: mix(col, '#ffffff', 0.25), align: 'right', a: al * s.graph }); ky += 56; }
    x.restore();
  },
  names(x, t, S, A, s) {
    const on = S.track(t, 'labels', 1);
    if (on < 0.02) return;
    S.P.layers.forEach(L => {
      if (!L.name) return;
      const a = Math.max(s.y(L.top), S.vert ? 600 : 260), b = Math.min(s.y(L.bot), S.H - 400), need = L.name.length * 52 + 10;
      if (b - a < need) return;
      const w = Math.max(...L.name.map(n => measure(x, n, 44, 700))) + 30, X = S.vert ? A.bx + A.R + 46 : Math.max(16, A.bx - A.R - 70 - w), y = (a + b) / 2;
      x.save(); x.globalAlpha = on; x.fillStyle = 'rgba(10,15,20,.8)'; rr(x, X, y - need / 2, w, need, 12); x.fill();
      x.fillStyle = S.color(L.color); rr(x, X, y - need / 2, 8, need, 4); x.fill();
      L.name.forEach((n, i) => label(x, n, X + 20, y - need / 2 + 44 + i * 52, { size: 44, w: 700, shadow: false })); x.restore();
    });
  },
  overlay(x, t, S) {
    const s = this.s, A = this.A, { H } = S;
    const ratio = A.R * 2 / ((S.P.hole_d || (S.P.grad ? 0.7 : 0.2)) * H / s.span), n = ratio >= 100 ? Math.round(ratio / 50) * 50 : Math.max(2, Math.round(ratio));
    const pit = S.shown(t, 'pit', 0.4, 0.4);
    if (pit > 0.02) { // приёмная ёмкость: объём раствора
      const w = S.sq ? 230 : S.vert ? 300 : 320, h = S.sq ? 150 : 210, X = S.sq ? 44 : S.vert ? S.W - S.safe.side - w : 90, Y = S.sq ? 830 : S.vert ? 1230 : 640, lv = clamp(s.pit);
      x.save(); x.globalAlpha = pit; x.fillStyle = 'rgba(8,13,18,.92)'; rr(x, X - 18, Y - 70, w + 36, h + 96, 22); x.fill();
      label(x, 'ёмкость', X + w / 2, Y - 18, { size: 44, w: 700, align: 'center', shadow: false });
      x.fillStyle = S.color('fluids.mud'); const yy = Y + h * (1 - lv); x.beginPath(); x.moveTo(X, Y + h); for (let i = 0; i <= w; i += 10) x.lineTo(X + i, yy + Math.sin(i / 30 + t * 4) * 4); x.lineTo(X + w, Y + h); x.closePath(); x.fill();
      x.strokeStyle = '#ECEFF4'; x.lineWidth = 6; x.beginPath(); x.moveTo(X, Y); x.lineTo(X, Y + h); x.lineTo(X + w, Y + h); x.lineTo(X + w, Y); x.stroke();
      x.setLineDash([12, 10]); x.strokeStyle = '#F1C40F'; x.lineWidth = 4; x.beginPath(); x.moveTo(X, Y + h / 2); x.lineTo(X + w, Y + h / 2); x.stroke(); x.restore();
    }
    S.beats.forEach((b, j) => {
      const list = (b.beat || {}).call;
      if (!list) return;
      const end = S.beats[j + 1] ? S.beats[j + 1].t_start : S.job.total + 1;
      list.forEach((c, i) => { const k = Math.min((t - b.t_start - 0.3 - i * 0.6) / 0.6, (end - t) / 0.25); if (k > 0) callout(x, A.bx + (c.dx === undefined ? A.R * 0.7 : c.dx), s.y(c.d), S.vert ? A.bx + A.R + 46 : A.bx + A.R + 90, s.y(c.d) + (c.dy || -90), c.text, k, {}); });
    });
    Stage.frameText(x, t, S.P.note || `ствол шире ≈ в ${n} раз`);
  },
};

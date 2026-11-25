// Сцена «прибор в скважине»: одна глубина d управляет прибором, кривыми и выносками.
// Параметры: layers [{top, bot, rock, color, fluid?, name[], values{кривая: 0..1}, hole}], curves [{key, name, color}], depth, note.
// beat: d, cam (центр кадра по глубине), span (сколько единиц глубины в кадре), tracks 0..1, head, hl, band, chips, lens, emit, compare.
const U = 40, NOM = 46; // точек мира на единицу глубины; радиус ствола
const Scene = {
  setup(S) {
    const P = S.P, K = 1.4, W = 1500;
    this.K = K; this.w2 = W / 2;
    const c = new OffscreenCanvas(W * K, (P.depth + 60) * U * K), x = c.getContext('2d');
    x.scale(K, K);
    x.translate(W / 2, 30 * U);
    P.layers.forEach((L, i) => {
      const top = i === 0 ? -30 : L.top, bot = i === P.layers.length - 1 ? P.depth + 30 : L.bot;
      const n = noise1(11 + i), flat = L.flat_top;
      x.save();
      x.beginPath();
      for (let X = -W / 2; X <= W / 2; X += 14) x.lineTo(X, top * U + (flat || i === 0 ? 0 : n(X / 160) * 9));
      x.lineTo(W / 2, bot * U + 40); x.lineTo(-W / 2, bot * U + 40); x.closePath();
      x.clip();
      Rock[L.rock](x, -W / 2, top * U - 20, W, (bot - top) * U + 60, S.color(L.color), 100 + i, L.fluid ? S.color(L.fluid) : null);
      const g = x.createLinearGradient(0, top * U, 0, top * U + 90);
      g.addColorStop(0, 'rgba(0,0,0,.35)'); g.addColorStop(1, 'rgba(0,0,0,0)');
      if (!flat) { x.fillStyle = g; x.fillRect(-W / 2, top * U - 20, W, 130); }
      x.restore();
    });
    this.tex = c;
    this.holeN = noise1(5);
    this.curveN = noise1(9);
  },
  layer(S, d) { return S.P.layers.find(l => d >= l.top && d < l.bot) || S.P.layers[S.P.layers.length - 1]; },
  wall(S, d) { // радиус ствола: каверна в глине, номинал в плотной породе, глинистая корка в коллекторе снаружи не видна
    let r = 0, w = 0;
    for (const [dd, k] of [[-0.7, 1], [0, 2], [0.7, 1]]) {
      const L = this.layer(S, d + dd);
      r += k * (L.hole === 'wide' ? NOM + 15 + this.holeN(d * 1.1) * 8 : NOM + this.holeN(d * 2) * 1.2);
      w += k;
    }
    return r / w;
  },
  value(S, key, d) {
    const A = S.P.layers;
    let v = A[0].values[key];
    for (let i = 1; i < A.length; i++) v += (A[i].values[key] - A[i - 1].values[key]) / (1 + Math.exp(-(d - A[i].top) / 0.45));
    return clamp(v + this.curveN(d * 1.7 + key.length * 31) * 0.018, 0.02, 0.985);
  },
  view(S, t) {
    const span = S.track(t, 'span', 40), cam = S.track(t, 'cam', 80);
    const z = S.H / (span * U), bx = S.track(t, 'bx', 215);
    return { z, bx, cam, y: d => S.H / 2 + (d - cam) * U * z, X: wx => bx + wx * z, depth: y => cam + (y - S.H / 2) / (U * z) };
  },
  draw(x, t, S) {
    const V = this.view(S, t), { W, H } = S, z = V.z, d = S.track(t, 'd', S.P.depth);
    this.V = V; this.d = d;
    x.fillStyle = '#0b1015'; x.fillRect(0, 0, W, H);
    const K = this.K, w2 = this.w2;
    const sx = (-V.bx / z + w2) * K, sy = (V.depth(0) + 30) * U * K;
    x.imageSmoothingQuality = 'high';
    x.drawImage(this.tex, sx, sy, W / z * K, H / z * K, 0, 0, W, H);
    this.band(x, t, S, V);
    this.hole(x, t, S, V);
    this.tool(x, t, S, V, d);
    this.emit(x, t, S, V, d);
    this.tracks(x, t, S, V, d);
    this.names(x, t, S, V, d);
  },
  band(x, t, S, V) {
    S.P.layers.forEach(L => {
      const a = S.shown(t, 'band', 0.4, 0.4, L.id);
      if (a <= 0) return;
      x.save();
      x.globalAlpha = a;
      const y0 = V.y(L.top), y1 = V.y(L.bot), g = x.createLinearGradient(0, 0, S.W * 0.55, 0);
      g.addColorStop(0, 'rgba(255,236,170,.20)'); g.addColorStop(1, 'rgba(255,236,170,0)');
      x.fillStyle = g; x.fillRect(0, y0, S.W * 0.55, y1 - y0);
      x.strokeStyle = '#F1C40F'; x.lineWidth = 5;
      x.setLineDash([22, 14]); x.lineDashOffset = -t * 30;
      for (const y of [y0, y1]) { x.beginPath(); x.moveTo(0, y); x.lineTo(S.W, y); x.stroke(); }
      x.restore();
    });
  },
  hole(x, t, S, V) {
    const z = V.z, d0 = V.depth(-60), d1 = V.depth(S.H + 60), st = Math.max(0.12, (d1 - d0) / 260);
    for (const L of S.P.layers) { // фильтрат раствора вошёл в проницаемый пласт
      if (!L.invaded || L.bot < d0 || L.top > d1) continue;
      const r = V.bx + NOM * z;
      for (const s of [-1, 1]) {
        const a = V.bx + s * NOM * z, b = V.bx + s * (NOM + 95) * z, g = x.createLinearGradient(a, 0, b, 0);
        g.addColorStop(0, rgba(S.color('fluids.filtrate'), 0.5)); g.addColorStop(1, rgba(S.color('fluids.filtrate'), 0));
        x.fillStyle = g; x.fillRect(Math.min(a, b), V.y(L.top), Math.abs(b - a), (L.bot - L.top) * U * z);
      }
    }
    x.save();
    x.beginPath();
    for (let d = d0; d <= d1; d += st) x.lineTo(V.bx - this.wall(S, d) * z, V.y(d));
    for (let d = d1; d >= d0; d -= st) x.lineTo(V.bx + this.wall(S, d + 50) * z, V.y(d));
    x.closePath();
    const R = (NOM + 22) * z, g = x.createLinearGradient(V.bx - R, 0, V.bx + R, 0), m = S.color('fluids.mud');
    g.addColorStop(0, mix(m, '#000000', 0.62)); g.addColorStop(0.42, mix(m, '#d8c8ae', 0.12)); g.addColorStop(0.6, mix(m, '#000000', 0.05)); g.addColorStop(1, mix(m, '#000000', 0.66));
    x.shadowColor = 'rgba(0,0,0,.8)'; x.shadowBlur = 34 * z;
    x.fillStyle = g; x.fill();
    x.shadowBlur = 0;
    x.strokeStyle = 'rgba(15,12,8,.75)'; x.lineWidth = 4 * z; x.stroke();
    x.clip();
    const q = rng(3); // взвесь в растворе
    for (let i = 0; i < 260; i++) {
      const dd = d0 + ((q() * 60 + 600 - (t * (0.25 + q() * 0.3))) % 60) / 60 * (d1 - d0);
      x.fillStyle = `rgba(230,215,185,${0.05 + q() * 0.14})`;
      x.beginPath(); x.arc(V.bx + (q() * 2 - 1) * (NOM + 10) * z, V.y(dd), (1 + q() * 2.4) * z, 0, 7); x.fill();
    }
    for (const L of S.P.layers) { // глинистая корка: диаметр меньше номинального
      if (!L.cake || L.bot < d0 || L.top > d1) continue;
      for (const s of [-1, 1]) {
        x.fillStyle = mix(m, '#cdb48c', 0.55);
        x.beginPath();
        const a = Math.max(L.top, d0), b = Math.min(L.bot, d1);
        for (let d = a; d <= b; d += st) x.lineTo(V.bx + s * (NOM - 8 - this.holeN(d * 1.6 + s) * 2) * z, V.y(d));
        x.lineTo(V.bx + s * (NOM + 6) * z, V.y(b)); x.lineTo(V.bx + s * (NOM + 6) * z, V.y(a)); x.closePath(); x.fill();
      }
    }
    x.restore();
  },
  tool(x, t, S, V, d) {
    const z = V.z, cx = V.bx + Math.sin(t * 0.7) * 1.2 * z, y = V.y(d), r = 23 * z, half = 190 * z;
    x.save();
    x.strokeStyle = '#0d0f12'; x.lineWidth = 9 * z;
    x.beginPath(); x.moveTo(cx, -50); x.lineTo(cx, y - half); x.stroke();
    x.strokeStyle = '#8d97a3'; x.lineWidth = 3 * z;
    x.beginPath(); x.moveTo(cx - 1.5 * z, -50); x.lineTo(cx - 1.5 * z, y - half); x.stroke();
    const metal = () => { const g = x.createLinearGradient(cx - r, 0, cx + r, 0); g.addColorStop(0, '#2c333b'); g.addColorStop(0.28, '#cfd7df'); g.addColorStop(0.42, '#f4f7fa'); g.addColorStop(0.7, '#79848f'); g.addColorStop(1, '#23292f'); return g; };
    x.strokeStyle = '#9aa5b0'; x.lineWidth = 5 * z; // рессоры центратора
    for (const s of [-1, 1]) for (const yy of [-0.62, 0.62]) { x.beginPath(); x.moveTo(cx + s * r * 0.8, y + (yy - 0.2) * half); x.quadraticCurveTo(cx + s * (NOM + 6) * z, y + yy * half, cx + s * r * 0.8, y + (yy + 0.2) * half); x.stroke(); }
    x.shadowColor = 'rgba(0,0,0,.6)'; x.shadowBlur = 18 * z;
    x.fillStyle = metal();
    rr(x, cx - r, y - half, 2 * r, 2 * half, r * 0.8); x.fill();
    x.shadowBlur = 0;
    for (const [a, b] of [[-0.98, -0.8], [0.86, 0.99]]) { x.fillStyle = 'rgba(20,24,28,.55)'; x.fillRect(cx - r, y + a * half, 2 * r, (b - a) * half); }
    S.P.curves.forEach((c, i) => { // датчики: по одному на кривую, цвет тот же, что у кривой
      const col = S.color(c.color), yy = y + (-0.42 + i * 0.42) * half;
      const g = x.createLinearGradient(cx - r, 0, cx + r, 0);
      g.addColorStop(0, mix(col, '#000000', 0.6)); g.addColorStop(0.38, mix(col, '#ffffff', 0.45)); g.addColorStop(1, mix(col, '#000000', 0.6));
      x.fillStyle = g; x.fillRect(cx - r, yy - 24 * z, 2 * r, 48 * z);
      x.strokeStyle = 'rgba(0,0,0,.6)'; x.lineWidth = 2 * z; x.strokeRect(cx - r, yy - 24 * z, 2 * r, 48 * z);
    });
    x.restore();
  },
  sensorY(S, V, d, i) { return V.y(d) + (-0.42 + i * 0.42) * 190 * V.z; },
  emit(x, t, S, V, d) { // как работает датчик: гамма идёт ИЗ породы в прибор, остальные методы — туда и обратно
    const z = V.z;
    S.P.curves.forEach((c, i) => {
      const a = S.shown(t, 'emit', 0.4, 0.4, c.key);
      if (a <= 0) return;
      const y = this.sensorY(S, V, d, i), col = S.color(c.color), v = this.value(S, c.key, d);
      x.save();
      x.globalAlpha = a;
      x.strokeStyle = col; x.lineWidth = 4;
      const n = c.physics === 'natural' ? Math.round(3 + v * 9) : 5;
      for (let k = 0; k < n; k++) for (const s of [-1, 1]) {
        const q = rng(k * 7 + (s > 0 ? 3 : 0) + 1), ph = (t * 0.8 + (c.physics === 'natural' ? q() : k / n)) % 1, ang = (q() - 0.5) * 2;
        if (c.physics === 'natural') {
          const r0 = lerp(150, 30, ph) * z, X = V.bx + s * Math.cos(ang) * r0, Y = y + Math.sin(ang) * r0;
          x.globalAlpha = a * Math.sin(ph * Math.PI);
          x.beginPath(); x.arc(X, Y, 7, 0, 7); x.fillStyle = col; x.fill();
          x.beginPath(); x.moveTo(X, Y); x.lineTo(X + s * Math.cos(ang) * 26, Y + Math.sin(ang) * 26); x.stroke();
        } else {
          x.globalAlpha = a * (1 - ph) * 0.8;
          x.beginPath(); x.arc(V.bx, y, (30 + ph * 110) * z, s > 0 ? -0.6 : Math.PI - 0.6, s > 0 ? 0.6 : Math.PI + 0.6); x.stroke();
        }
      }
      x.restore();
    });
  },
  trackBox(S, i) { const x0 = S.P.track_x || 548, n = S.P.curves.length, gap = 18, w = (S.W - S.safe.side - x0 - gap * (n - 1)) / n; return [x0 + i * (w + gap), w]; },
  tracks(x, t, S, V, d) {
    const A = S.track(t, 'tracks', 1);
    if (A <= 0.01) return;
    const hl = S.at(t).q.hl, dStart = S.P.start, H = S.H;
    x.save();
    x.globalAlpha = A;
    S.P.curves.forEach((c, i) => {
      const [X, w] = this.trackBox(S, i), col = S.color(c.color), on = !hl || hl.includes(c.key);
      x.save();
      x.fillStyle = 'rgba(10,15,20,.82)'; x.fillRect(X, 0, w, H);
      x.strokeStyle = on && hl ? col : 'rgba(255,255,255,.18)'; x.lineWidth = on && hl ? 5 : 2; x.strokeRect(X, -10, w, H + 20);
      x.strokeStyle = 'rgba(255,255,255,.10)'; x.lineWidth = 2;
      for (const g of [0.25, 0.5, 0.75]) { x.beginPath(); x.moveTo(X + w * g, 0); x.lineTo(X + w * g, H); x.stroke(); }
      x.globalAlpha = on ? 1 : 0.38;
      const px = v => X + 12 + v * (w - 24), yb = Math.min(H + 20, V.y(dStart)), ya = Math.max(-20, V.y(d));
      if (yb > ya) {
        const path = () => { for (let y = ya; y <= yb; y += 3) x.lineTo(px(this.value(S, c.key, V.depth(y))), y); };
        x.beginPath(); x.moveTo(X + 2, ya); path(); x.lineTo(X + 2, yb); x.closePath();
        const g = x.createLinearGradient(X, 0, X + w, 0);
        g.addColorStop(0, rgba(col, 0.05)); g.addColorStop(1, rgba(col, 0.5));
        x.fillStyle = g; x.fill();
        x.beginPath(); path();
        x.strokeStyle = col; x.lineWidth = on && hl ? 9 : 7; x.lineJoin = 'round';
        x.shadowColor = col; x.shadowBlur = on ? 14 : 0; x.stroke(); x.shadowBlur = 0;
      }
      const yt = V.y(d), v = this.value(S, c.key, d);
      x.setLineDash([6, 8]); x.strokeStyle = 'rgba(255,255,255,.35)'; x.lineWidth = 2;
      x.beginPath(); x.moveTo(i ? X - 18 : V.bx + 30 * V.z, yt); x.lineTo(px(v), yt); x.stroke(); x.setLineDash([]);
      x.fillStyle = '#fff'; x.beginPath(); x.arc(px(v), yt, 15, 0, 7); x.fill();
      x.fillStyle = col; x.beginPath(); x.arc(px(v), yt, 10, 0, 7); x.fill();
      x.restore();
    });
    x.restore();
  },
  names(x, t, S, V, d) { // имя породы появляется, когда прибор до неё дошёл
    const A = S.track(t, 'labels', 1);
    const under = S.shown(t, "lens", 0.6, 0.3), cmp = 1 - S.shown(t, "compare"), cur = this.layer(S, d);
    S.P.layers.forEach(L => {
      const open = L.hidden ? S.track(t, L.hidden, 0) : 1, name = open > 0.5 ? L.name : ['?'];
      const a = A * cmp * smooth((L.bot - 1 - d) / 2.5) * (L.hidden ? Math.max(0.15, Math.abs(open * 2 - 1)) : 1) * (L === cur ? 1 - under : 1);
      if (a <= 0.01) return;
      const y0 = Math.max(V.y(L.top), S.vert ? 560 : 120), y1 = Math.min(V.y(L.bot), S.H - 375), need = name.length * 52 + 10;
      if (y1 - y0 < need) return;
      const y = clamp(V.y((L.top + L.bot) / 2), y0 + need / 2, y1 - need / 2), w = Math.max(...name.map(s => measure(x, s, 44, 700))) + 30, X = S.P.name_x || 318;
      x.save();
      x.globalAlpha = a;
      x.fillStyle = 'rgba(10,15,20,.80)'; rr(x, X, y - need / 2, w, need, 12); x.fill();
      x.fillStyle = S.color(L.color); rr(x, X, y - need / 2, 8, need, 4); x.fill();
      name.forEach((s, i) => label(x, s, X + 20, y - need / 2 + 44 + i * 52, { size: 44, w: 700, shadow: false }));
      x.restore();
    });
  },
  overlay(x, t, S) {
    const { W, H } = S, V = this.V, d = this.d, N = S.at(t);
    let g = x.createLinearGradient(0, 0, 0, 640);
    g.addColorStop(0, 'rgba(6,10,14,.94)'); g.addColorStop(0.66, 'rgba(6,10,14,.80)'); g.addColorStop(1, 'rgba(6,10,14,0)');
    x.fillStyle = g; x.fillRect(0, 0, W, 640);
    // названия кривых стоят под заголовком и не уезжают с камерой
    const A = S.track(t, 'tracks', 1) * (1 - S.shown(t, 'compare'));
    S.P.curves.forEach((c, i) => {
      const [X, w] = this.trackBox(S, i), col = S.color(c.color);
      label(x, c.name, X + w / 2 + 16, Math.min(1080, V.y(d) - 120), { size: 44, w: 700, color: mix(col, '#ffffff', 0.15), rot: -Math.PI / 2, a: A * smooth((V.y(d) - 860) / 160) });
    });
    // величины словами прямо у точки кривой
    S.P.curves.forEach((c, i) => {
      S.beats.forEach((b, j) => {
        const s = ((b.beat || {}).chips || {})[c.key];
        if (!s || t < b.t_start) return;
        const end = S.beats[j + 1] ? S.beats[j + 1].t_start : S.job.total + 1, del = ((b.beat.chip_at || {})[c.key] || 0) * (b.t_end - b.t_start);
        if (t > end) return;
        const [X, w] = this.trackBox(S, i);
        chip(x, s, X + w / 2, V.y(d) - 62, mix(S.color(c.color), '#ffffff', 0.12), Math.min((t - b.t_start - del) / 0.35, (end - t) / 0.2));
      });
    });
    // лупа
    S.beats.forEach((b, j) => {
      const q = (b.beat || {}).lens;
      if (!q) return;
      const end = S.beats[j + 1] ? S.beats[j + 1].t_start : S.job.total + 1, t0 = b.t_start + (q.delay || 0.3);
      const k = Math.min((t - t0) / 0.5, (end - t) / 0.25);
      if (k <= 0) return;
      lens(x, q.x, q.y, q.r, V.bx + (NOM + 34) * V.z, V.y(d) - 60, k, (c, r) => this.pore(c, r, q.kind, S, t), { cap: q.cap });
    });
    this.compare(x, t, S);
    // вопрос-предсказание: отсчёт паузы
    const pr = N.b.prediction ? clamp((t - N.b.t_end) / Math.max(0.1, N.left + t - N.b.t_end)) : 0;
    if (N.b.prediction && t > N.b.t_end) {
      x.save();
      x.lineWidth = 12; x.strokeStyle = 'rgba(255,255,255,.2)'; x.beginPath(); x.arc(W / 2, 1230, 74, 0, 7); x.stroke();
      x.strokeStyle = '#F1C40F'; x.beginPath(); x.arc(W / 2, 1230, 74, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * (1 - pr)); x.stroke();
      label(x, '?', W / 2, 1262, { size: 96, w: 700, align: 'center' });
      x.restore();
    }
    // ключевые слова
    if (N.q.head) headline(x, S, N.q.head, N.since / 0.9 + (N.i === 0 ? 0.75 : 0), { size: N.q.head_size || 88, a: smooth(N.left / 0.18) });
    badge(x, S, S.P.label || 'схема', S.P.note, S.safe.top - 44);
    if (S.P.source) {
      const w = measure(x, S.P.source, 44, 500) + 28;
      x.fillStyle = 'rgba(8,12,17,.78)'; rr(x, S.safe.side - 14, H - 352, w, 64, 12); x.fill();
      label(x, S.P.source, S.safe.side, H - 305, { size: 44, w: 500, color: '#D5DCE3', shadow: false });
    }
  },
  pore(c, r, kind, S, t) {
    const sand = mix(S.color('lithology.sand'), '#a8843a', 0.25);
    if (kind === 'crystals') Pores.crystals(c, r, mix(S.color('lithology.limestone'), '#6f8798', 0.3), 21);
    else Pores.grains(c, r, sand, S.color(kind === 'oil' ? 'fluids.oil' : 'fluids.water'), kind === 'oil' ? rgba(S.color('fluids.water'), 0.95) : null, 33);
  },
  compare(x, t, S) { // итог: две породы, те же показания; 1 — левая, 2 — обе, 3 — разброс, 4 — остался один столбец
    const a = S.shown(t, 'compare', 0.6, 0.3);
    if (a <= 0) return;
    const C = S.P.compare, { W } = S, gap = 30, w = (W - 2 * S.safe.side - gap) / 2, Y = 590;
    const from = n => { const b = S.beats.find(q => ((q.beat || {}).compare || 0) >= n); return b ? t - b.t_start : -9; };
    const spread = smooth(from(3) / 0.8) * (1 - smooth(from(4) / 0.5)), solo = smooth(from(4) / 0.7), step = S.P.curves.length > 3 ? 92 : 118;
    x.save();
    x.globalAlpha = a;
    x.fillStyle = 'rgba(6,10,14,.66)'; x.fillRect(0, 0, W, S.H);
    C.forEach((it, j) => {
      const L = S.P.layers.find(l => l.id === it.layer), X = S.safe.side + j * (w + gap), since = from(j + 1), k = smooth(since / 0.5);
      if (k <= 0) return;
      x.save();
      x.globalAlpha = a * k;
      x.translate(0, (1 - k) * 60);
      x.fillStyle = 'rgba(17,24,31,.96)'; rr(x, X, Y, w, 900, 28); x.fill();
      x.strokeStyle = S.color(L.color); x.lineWidth = 5; x.stroke();
      const cx = X + w / 2, r = 150;
      x.save(); x.beginPath(); x.arc(cx, Y + 190, r, 0, 7); x.clip(); x.translate(cx, Y + 190); this.pore(x, r, it.pore, S, t); x.restore();
      x.strokeStyle = '#F4F6F8'; x.lineWidth = 6; x.beginPath(); x.arc(cx, Y + 190, r, 0, 7); x.stroke();
      x.save(); x.globalAlpha *= 1 - solo; it.name.forEach((s, i) => label(x, s, cx, Y + 400 + i * 54, { size: 48, w: 700, align: 'center' })); x.restore();
      if (solo > 0.02) label(x, '?', cx, Y + 450, { size: 120, w: 700, align: 'center', color: '#F1C40F', a: solo });
      S.P.curves.forEach((c, i) => {
        const yy = Y + 570 + i * step, v = L.values[c.key], p = smooth((since - 0.5 - i * 0.5) / 0.7), col = S.color(c.color), bw = w - 60;
        x.save();
        x.globalAlpha *= i ? 1 - solo * 0.88 : 1;
        x.fillStyle = 'rgba(255,255,255,.12)'; rr(x, X + 30, yy + 16, bw, 34, 17); x.fill();
        x.fillStyle = col; rr(x, X + 30, yy + 16, Math.max(34, bw * v * p), 34, 17); x.fill();
        if (spread > 0.02) { // переходные породы: значения размываются
          const c0 = X + 30 + bw * v, d = bw * 0.2 * spread, x0 = Math.max(X + 30, c0 - d), x1 = Math.min(X + 30 + bw, c0 + d), g = x.createLinearGradient(x0, 0, x1, 0);
          g.addColorStop(0, rgba('#95A5A6', 0)); g.addColorStop(0.5, rgba('#ECEFF4', 0.95)); g.addColorStop(1, rgba('#95A5A6', 0));
          x.fillStyle = g; rr(x, x0, yy + 10, x1 - x0, 46, 12); x.fill();
        }
        x.restore();
      });
      x.restore();
    });
    S.P.curves.forEach((c, i) => {
      const yy = Y + 570 + i * step, n = measure(x, c.name, 44, 700) + 30;
      x.save();
      x.globalAlpha = a * smooth((from(1) - 0.5 - i * 0.5) / 0.4) * (i ? 1 - solo * 0.88 : 1);
      const cx = from(2) > 0 ? lerp(S.safe.side + w / 2, W / 2, smooth(from(2) / 0.5)) : S.safe.side + w / 2;
      x.fillStyle = 'rgba(17,24,31,.96)'; rr(x, cx - n / 2, yy - 44, n, 56, 12); x.fill();
      label(x, c.name, cx, yy, { size: 44, w: 700, color: mix(S.color(c.color), '#ffffff', 0.25), align: 'center', shadow: false });
      x.restore();
    });
    x.restore();
  },
};

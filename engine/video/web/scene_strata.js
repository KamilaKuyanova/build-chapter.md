// Сцена «разрез во времени»: слои накапливаются, дно опускается, море приходит и уходит, размыв срезает верх.
// Одно состояние st (номер стадии с долей) даёт все границы: порядок слоёв сохраняется по построению.
// Параметры: width_m, z [низ, верх] м, base [[x 0..1, z]], stages [{title, sea, sub, add {id, rock, color, name, thick}|fill, cut}], fluids, wells.
// beat: st, cam_x 0..1, zoom, true 0..1 (истинный масштаб), sea 0..1, fluid 0..1, wells 0..1, call [{x, layer|z, text}], hl слой, lens, head.
const prof = (A, u) => { if (!Array.isArray(A)) return A || 0; if (u <= A[0][0]) return A[0][1]; for (let i = 1; i < A.length; i++) if (u <= A[i][0]) return lerp(A[i - 1][1], A[i][1], smooth((u - A[i - 1][0]) / (A[i][0] - A[i - 1][0]))); return A[A.length - 1][1]; };
const NX = 240;
const Scene = {
  setup(S) {
    this.tiles = {};
    const all = [{ id: 'base', rock: S.P.base_rock || 'basement', color: S.P.base_color || 'uncertainty' }].concat(S.P.stages.filter(s => s.add).map(s => s.add));
    all.forEach((L, i) => {
      const c = new OffscreenCanvas(1100, 640), x = c.getContext('2d');
      (Rock[L.rock] || Rock.clay)(x, 0, 0, 1100, 640, S.color(L.color), 70 + i, null);
      this.tiles[L.id] = c;
    });
  },
  model(S, st) { // границы снизу вверх на сетке x
    const P = S.P, us = Array.from({ length: NX + 1 }, (_, i) => i / NX);
    let bounds = [us.map(u => prof(P.base, u))], ids = ['base'], sea = P.sea0 === undefined ? null : P.sea0;
    P.stages.forEach((g, i) => {
      const k = smooth(clamp(st - i));
      if (st <= i) return;
      if (g.sub) bounds = bounds.map(b => b.map((z, j) => z - prof(g.sub, us[j]) * k));
      const top = bounds[bounds.length - 1];
      if (g.sea !== undefined) sea = lerp(sea === null ? g.sea : sea, g.sea, k);
      if (g.cut) { const c = us.map((u, j) => lerp(top[j], Math.min(top[j], prof(g.cut, u)), k)); bounds = bounds.map(b => b.map((z, j) => Math.min(z, c[j]))); }
      if (g.add) {
        const a = g.add, cur = bounds[bounds.length - 1];
        bounds.push(cur.map((z, j) => a.fill !== undefined ? z + Math.max(0, a.fill - z) * k : z + prof(a.thick, us[j]) * k));
        ids.push(a.id);
      }
    });
    return { us, bounds, ids, sea };
  },
  draw(x, t, S) {
    const P = S.P, { W, H } = S, st = S.track(t, 'st', 0), M = this.model(S, st);
    const zoom = S.track(t, 'zoom', 1) * (S.sq ? S.P.sq_zoom || 1.3 : 1), cx = S.track(t, 'cam_x', 0.5), tr = S.track(t, 'true', 0);
    const area = S.vert ? { y0: 620, y1: H - 400 } : S.sq ? { y0: 330, y1: H - 120 } : { y0: 230, y1: H - 70 };
    const kx = W / P.width_m * zoom, ky0 = (area.y1 - area.y0) / (P.z[1] - P.z[0]) * Math.sqrt(zoom), ky = Math.exp(lerp(Math.log(ky0), Math.log(kx), tr));
    const zc = lerp(S.track(t, 'cam_z', (P.z[0] + P.z[1]) / 2), M.bounds[M.bounds.length - 1][NX >> 1], tr), yc = (area.y0 + area.y1) / 2;
    const X = u => W / 2 + (u - cx) * P.width_m * kx, Y = z => yc - (z - zc) * ky;
    this.v = { X, Y, M, ve: ky / kx, st };
    const g = x.createLinearGradient(0, 0, 0, H); g.addColorStop(0, '#13202c'); g.addColorStop(0.5, '#4d6b80'); g.addColorStop(1, '#c9d4da'); x.fillStyle = g; x.fillRect(0, 0, W, H);
    const top = M.bounds[M.bounds.length - 1];
    if (M.sea !== null && S.track(t, 'sea', 1) > 0.02) {
      const ys = Y(M.sea), w = S.color('fluids.water');
      x.save(); x.globalAlpha = S.track(t, 'sea', 1);
      const q = x.createLinearGradient(0, ys, 0, ys + 420); q.addColorStop(0, rgba(mix(w, '#ffffff', 0.35), 0.85)); q.addColorStop(1, rgba(mix(w, '#0b1e33', 0.6), 0.95));
      x.fillStyle = q; x.beginPath(); x.moveTo(-10, ys); for (let i = -10; i <= W + 10; i += 12) x.lineTo(i, ys + Math.sin(i / 46 + t * 1.8) * 3.5); x.lineTo(W + 10, H); x.lineTo(-10, H); x.closePath(); x.fill();
      x.strokeStyle = 'rgba(255,255,255,.75)'; x.lineWidth = 3; x.beginPath(); for (let i = -10; i <= W + 10; i += 12) x.lineTo(i, ys + Math.sin(i / 46 + t * 1.8) * 3.5); x.stroke();
      const r = rng(2); // частицы осадка оседают, пока идёт накопление
      const i = Math.min(P.stages.length - 1, Math.floor(st)), dep = P.stages[i] && P.stages[i].add && st % 1 > 0.02;
      if (dep) for (let k = 0; k < 160; k++) { const u = r(), j = Math.round(u * NX), yb = Y(top[j]), v = (t * (0.15 + r() * 0.2) + r()) % 1, yy = ys + v * (yb - ys); if (yb < ys) continue; x.fillStyle = rgba(S.color(P.stages[i].add.color), 0.9); x.beginPath(); x.arc(X(u), yy, 3 + r() * 2.5, 0, 7); x.fill(); }
      x.restore();
    }
    for (let i = 0; i < M.bounds.length; i++) { // слой между границей i-1 и i; подошва разреза уходит за кадр
      const up = M.bounds[i], lo = i ? M.bounds[i - 1] : null, L = M.ids[i];
      x.beginPath();
      M.us.forEach((u, j) => x.lineTo(X(u), Y(up[j])));
      x.lineTo(W + 60, Y(up[NX]));
      if (lo) { x.lineTo(W + 60, Y(lo[NX])); for (let j = NX; j >= 0; j--) x.lineTo(X(M.us[j]), Y(lo[j])); x.lineTo(-60, Y(lo[0])); } else { x.lineTo(W + 60, H + 60); x.lineTo(-60, H + 60); }
      x.lineTo(-60, Y(up[0])); x.closePath();
      const pat = x.createPattern(this.tiles[L], 'repeat'); pat.setTransform(new DOMMatrix().translate(X(0), Y(up[NX >> 1])));
      x.fillStyle = pat; x.fill();
      x.strokeStyle = 'rgba(12,16,20,.6)'; x.lineWidth = 3; x.stroke();
      const hl = S.shown(t, 'hl', 0.4, 0.3, L);
      if (hl > 0.01) { x.save(); x.globalAlpha = hl; x.fillStyle = 'rgba(241,196,15,.20)'; x.fill(); x.strokeStyle = '#F1C40F'; x.lineWidth = 7; x.stroke(); x.restore(); }
    }
    (P.zones || []).forEach((Z, n) => { // зоны внутри слоя: часть ширины и часть толщины
      const a = S.track(t, 'z_' + Z.id, 0), i = M.ids.indexOf(Z.layer); if (a < 0.02 || i < 1) return;
      const up = M.bounds[i], lo = M.bounds[i - 1], q = (j, k) => lerp(lo[j], up[j], k), pts = [];
      M.us.forEach((u, j) => { if (u >= Z.from && u <= Z.to) pts.push(j); });
      x.save(); x.globalAlpha = a; x.beginPath();
      pts.forEach(j => x.lineTo(X(M.us[j]), Y(q(j, Z.top === undefined ? 1 : Z.top))));
      pts.slice().reverse().forEach(j => x.lineTo(X(M.us[j]), Y(q(j, Z.bot || 0)))); x.closePath();
      if (Z.kind !== 'cracks') { x.fillStyle = rgba(S.color(Z.color || 'measurement'), Z.alpha || 0.55); x.fill(); }
      x.save(); x.clip();
      const r = rng(40 + n);
      if (Z.kind === 'cracks') for (let k = 0; k < 46; k++) { const j = pts[Math.floor(r() * pts.length)]; let cx = X(M.us[j]), cy = Y(q(j, r())); x.strokeStyle = 'rgba(255,255,255,.85)'; x.lineWidth = 3; x.beginPath(); x.moveTo(cx, cy); for (let s2 = 0; s2 < 5; s2++) { cx += (r() - 0.5) * 26; cy += 16 + r() * 18; x.lineTo(cx, cy); } x.stroke(); }
      if (Z.kind === 'vugs') for (let k = 0; k < 70; k++) { const j = pts[Math.floor(r() * pts.length)], s2 = 5 + r() * 16; x.fillStyle = 'rgba(12,16,20,.78)'; blob(x, X(M.us[j]), Y(q(j, r())), s2 * a, r() * 6); x.fill(); }
      x.restore();
      if (Z.kind !== 'cracks') { x.strokeStyle = S.color(Z.color || 'measurement'); x.lineWidth = 4; x.stroke(); }
      x.restore();
    });
    (P.arrows || []).forEach(A => { const a = S.track(t, 'a_' + A.id, 0); if (a < 0.02) return; x.save(); x.globalAlpha = a; x.strokeStyle = S.color(A.color || 'measurement'); x.lineWidth = 9; x.setLineDash([26, 18]); x.lineDashOffset = -t * 70; x.beginPath(); A.pts.forEach(q => x.lineTo(X(q[0]), Y(q[1]))); x.stroke(); x.setLineDash([]); const n = A.pts.length, e = A.pts[n - 1], s2 = A.pts[n - 2], an = Math.atan2(Y(e[1]) - Y(s2[1]), X(e[0]) - X(s2[0])); x.translate(X(e[0]), Y(e[1])); x.rotate(an); x.fillStyle = x.strokeStyle; x.beginPath(); x.moveTo(26, 0); x.lineTo(-14, -20); x.lineTo(-14, 20); x.closePath(); x.fill(); x.restore(); });
    (P.fluids || []).forEach(f => {
      const fk = S.track(t, f.id ? 'f_' + f.id : 'fluid', 0); if (fk < 0.02) return;
 // заполнение коллектора под покрышкой: газ над нефтью, нефть над водой, контакты горизонтальны
      const i = M.ids.indexOf(f.layer); if (i < 1) return;
      const up = M.bounds[i], lo = M.bounds[i - 1], peak = Math.max(...M.us.map((u, j) => u >= f.from && u <= f.to ? up[j] : -1e9)), cz = lerp(peak, f.contact, fk), zc2 = 0, tilt = f.tilt || 0, at = u => cz + (u - (f.from + f.to) / 2) * tilt;
      x.save(); x.beginPath();
      M.us.forEach((u, j) => { if (u >= f.from && u <= f.to) x.lineTo(X(u), Y(Math.max(up[j], at(u)))); });
      for (let j = NX; j >= 0; j--) if (M.us[j] >= f.from && M.us[j] <= f.to) x.lineTo(X(M.us[j]), Y(Math.max(at(M.us[j]), lo[j])));
      x.closePath(); x.fillStyle = rgba(S.color(f.color), 0.66); x.fill(); x.restore();
    });
    (P.wells || []).forEach(w => { const wk = S.track(t, w.id ? 'w_' + w.id : 'wells', 0); if (wk < 0.02) return; const z0 = prof(top.map((z, j) => [M.us[j], z]), w.x), y0 = Y(z0), y1 = lerp(y0, Y(w.to), wk); x.fillStyle = '#10151b'; x.fillRect(X(w.x) - 9, y0 - 70, 18, y1 - y0 + 70); x.fillStyle = '#dfe6ec'; x.fillRect(X(w.x) - 4, y0 - 70, 8, y1 - y0 + 70); });
  },
  overlay(x, t, S) {
    const { X, Y, M, ve } = this.v;
    S.beats.forEach((b, j) => {
      const list = (b.beat || {}).call || [];
      const end = S.beats[j + 1] ? S.beats[j + 1].t_start : S.job.total + 1;
      list.forEach((c, i) => {
        const k = Math.min((t - b.t_start - 0.3 - i * 0.7) / 0.6, (end - t) / 0.25); if (k <= 0) return;
        let z = c.z;
        const n = M.ids.indexOf(c.layer), q = Math.round(c.x * NX);
        if (c.layer) { if (n < 0) return; z = n ? (M.bounds[n][q] + M.bounds[n - 1][q]) / 2 : M.bounds[0][q] - 20; }
        const px = clamp(X(c.x), 60, S.W - 60), wl = measure(x, c.text, 46, 600) + 36, right = px + (c.dx || 0) * (S.sq ? 0.6 : 1) > S.W * 0.6, tx = clamp(px + (c.dx || 0) * (S.sq ? 0.6 : 1), S.safe.side + 10 + (right ? wl : 0), S.W - S.safe.side - 10 - (right ? 0 : wl));
        callout(x, px, Y(z), tx, Math.max(S.sq ? 340 : 0, Y(z) + (c.dy || -120)), c.text, k, { align: right ? 'right' : 'left' });
      });
      const l = (b.beat || {}).lens;
      if (l) { const k = Math.min((t - b.t_start - (l.delay || 0.5)) / 0.5, (end - t) / 0.25), n = M.ids.indexOf(l.layer), q = Math.round(l.at * NX); if (S.sq) { l.r = Math.min(l.r, 175); l.x = Math.min(l.x, S.W - l.r - 26); l.y = 800 - l.r * 0.4; } if (k > 0 && n >= 0) lens(x, l.x, l.y, l.r, X(l.at), Y((M.bounds[n][q] + M.bounds[Math.max(0, n - 1)][q]) / 2), k, (c, r) => l.kind === 'crystals' ? Pores.crystals(c, r, S.color(l.color || 'lithology.limestone'), 21) : Pores.grains(c, r, S.color(l.color || 'lithology.sand'), S.color(l.fluid || 'fluids.water'), l.film ? S.color('fluids.water') : l.cement ? mix(S.color(l.color || 'lithology.sand'), '#f3efe6', 0.55) : null, 33, 0, { grow: l.cement ? lerp(l.cement[0], l.cement[1], smooth((t - b.t_start - 1) / Math.max(1, b.t_end - b.t_start - 1))) : 0, vug: l.vug ? lerp(l.vug[0], l.vug[1], smooth((t - b.t_start - 1) / Math.max(1, b.t_end - b.t_start - 1))) : 0 }), { cap: l.cap }); }
    });
    const n = ve < 1.15 ? 1 : ve < 10 ? Math.round(ve * 2) / 2 : Math.round(ve / 5) * 5;
    Stage.frameText(x, t, n === 1 ? 'истинный масштаб' : `высота увеличена × ${String(n).replace('.', ',')}`);
  },
};

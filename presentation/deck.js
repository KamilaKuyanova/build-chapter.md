// Слайды: переходы, 3D-состояние каждого слайда, подписи слоёв, заметки докладчика.
const M = p => { const d = (window.MEDIA || {})[p]; if (!d) return p; if (p.endsWith('jpg')) return 'data:image/jpeg;base64,' + d; const b = atob(d), a = new Uint8Array(b.length); for (let i = 0; i < b.length; i++) a[i] = b.charCodeAt(i); return URL.createObjectURL(new Blob([a], { type: 'video/mp4' })); };
// версия для ссылки: ролики по ТЗ не публикуем, вместо них кадры
if (window.STILLS) { const v = document.getElementById('short'), im = new Image(); im.id = 'short'; im.alt = 'Кадр ролика'; im.src = 'media/short.jpg'; v.replaceWith(im); im.setAttribute('src', 'media/short.jpg'); }
if (window.MEDIA) document.querySelectorAll('img,#short').forEach(e => e.src = M(e.getAttribute('src')));
const F = window.FACTS, $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
const get = path => path.split('.').reduce((o, k) => o && o[k], F);
$$('[data-f]').forEach(e => e.textContent = get(e.dataset.f));
$('#team').textContent = F.team ? 'Команда ' + F.team : '';
// ---------- наполнение из фактов
$$('.wipe').forEach(e => { e.innerHTML = e.textContent.trim().split(/\s+/).map((w, i) => `<span class="w" style="transition-delay:${(0.45 + i * 0.085).toFixed(2)}s">${w}</span>`).join(' '); });
$$('.num').forEach(e => { const v = String(isNaN(e.dataset.n) ? get(e.dataset.n) : e.dataset.n); e.innerHTML = [...v].map(d => `<span data-d="${d}">${'0123456789'.split('').map(x => `<em>${x}</em>`).join('')}</span>`).join('') + (e.dataset.suf ? `<span><em>${e.dataset.suf}</em></span>` : ''); });
$('#ticks').innerHTML = ['Цитата знак в знак', 'Страница книги', 'Числа из своей единицы', 'Оговорки и условия', 'Направление и отрицание', 'Термин объяснён до первого использования', 'Покрытие каждой единицы'].map((s, i) => `<div class="tick" style="--d:${i}"><span>${s}</span><svg viewBox="0 0 26 26"><path d="M4 14l6 6L22 6"/></svg></div>`).join('');
$('#bars').innerHTML = F.train.map((c, i) => `<div class="rv" style="--d:${i + 2}"><div style="display:flex;justify-content:space-between;font-size:21px"><span>${c.title.split(',')[0]}</span><span>${c.covered}/${c.units}</span></div><div class="bar"><i style="--k:${c.covered / c.units};--d:${i}"></i></div></div>`).join('');
const url = {}, loop = i => window.STILLS ? `<img alt="" src="${url[i] = url[i] || M(`media/loop_${String(i).padStart(2, '0')}.jpg`)}">` : `<video muted loop playsinline preload="metadata" src="${url[i] = url[i] || M(`media/loop_${String(i).padStart(2, '0')}.mp4`)}"></video>`, half = [0, 1, 2, 3, 4, 5];
$('#r1').innerHTML = [...half, ...half].map(loop).join(''); $('#r2').innerHTML = [...half, ...half].map(i => loop(i + 6)).join('');
const sv = F.demo || F.videos.find(v => v.format === 'short'), lv = F.videos.find(v => v.format !== 'short'), ru = (x, n = 1) => x.toFixed(n).replace('.', ',');
$('#pred').textContent = sv ? sv.prediction : '';
if (sv && sv.check) $('#pass').innerHTML = [['Ошибок распознавания', `${ru(sv.check.asr_wer * 100)} %`, 'порог 10 %'], ['Синхрон голоса и кадра', `${ru(sv.check.sync_max_s, 2)} с`, 'по меткам слов'], ['Громкость', `−${ru(Math.abs(sv.check.lufs))} LUFS`, 'цель −16'], ['Темп', `${Math.round(sv.check.wpm)} слов/мин`, 'норма 110–150']].map((r, i) => `<div class="rv" style="--d:${i * 1.4 + 2};border-top:1.5px dashed rgba(6,8,12,.28);padding:16px 0 20px"><div class="lab" style="color:var(--mut)">${r[0]}</div><div style="font-size:50px;letter-spacing:-.035em;line-height:1.15">${r[1]}</div><div style="font-size:19px;color:var(--mut)">${r[2]}</div></div>`).join('') + (lv ? `<p class="rv" style="--d:9;font-size:20px;color:var(--mut)">Второй ролик, разбор 16:9: ${Math.floor(lv.sec / 60)} мин ${Math.round(lv.sec % 60)} с</p>` : '');
{ // 40 целей: найденные, пропущенные, нетронутые
  const C = F.control, order = Array.from({ length: C.targets }, (_, i) => i).sort((a, b) => ((a * 17 + 5) % 40) - ((b * 17 + 5) % 40)), kind = {};
  order.forEach((k, i) => kind[k] = i < C.found ? 'e' : i < C.errors ? 'm' : 'g');
  $('#dots').innerHTML = order.map((_, i) => `<i class="${kind[i]}" style="--d:${(i % 8) * 5 + Math.floor(i / 8)}"></i>`).join('');
}
{ // репетиция на контрольной главе, минуты из PLAYBOOK.md
  const R = [['Слой и проверка', 0, 6], ['Задания', 6, 1], ['Сценарии анимаций', 7, 3], ['Рендер анимаций', 10, 5, 1], ['Сценарий ролика', 10, 2], ['Рендер шортса', 12, 3, 1], ['Курс и проверки', 15, 1]], all = 16;
  $('#tl').innerHTML = R.map((r, i) => `<div class="rv" style="--d:${i * .7}"><span>${r[0]}</span><s><i class="${r[3] ? 'bgd' : ''}" style="--a:${r[1] / all};--b:${r[2] / all};--d:${i}"></i></s><b>${r[2]} мин</b></div>`).join('');
}
if (F.test.length) $('#test').innerHTML = F.test.slice(0, 4).map((c, i) => `<div class="card rv" style="left:${40 + i * 385}px;top:400px;width:365px;height:400px;--d:${i * 2 + 1}"><span class="tag">${c.lang === 'en' ? 'EN' : 'RU'}${c.domain !== 'geology' ? ' · ' + c.domain : ''}</span><div style="font-size:26px;line-height:1.2;height:66px;overflow:hidden">${c.title}</div><div style="font-size:70px;letter-spacing:-.04em;margin-top:22px">${c.covered}/${c.units}</div><p style="font-size:21px;opacity:.8">единиц покрыто<br>${c.nodes} узлов · ${c.claims} утверждений<br>${c.tasks} заданий · ${c.loops} анимаций</p></div>`).join('');
else $('[data-if=test]').remove();
// петли за краем экрана стоят: так стена не грузит видеокарту
const eye = new IntersectionObserver(es => es.forEach(e => { e.target.dataset.in = e.isIntersecting ? 1 : ''; if (e.isIntersecting && slides[cur] && slides[cur].contains(e.target)) e.target.play().catch(() => {}); else e.target.pause(); }));
// ---------- 3D-состояние слайдов: поверх общих значений
const base = { x: 0, y: 0, z: -7.2, rx: .42, ry: -.6, rz: 0, scale: 1, fold: 1, explode: 0, light: 0, contour: 1, deep: 0, wire: 0, wipe: 1.1, show: 1, lines: 0, well: 0, dust: 1, fluid: 1, spin: 1, hot: -1, depth: 1.6, clip: null };
const LOOK = {
  'Старт': { x: 1.70, y: .12, scale: .80, rx: .42, rz: -.06, fold: 0 },
  'Проблема': { x: 2.22, y: -.02, scale: .55, rx: .55, ry: -.5, fold: 0, clip: [1040, 150, 520, 660], contour: .8 },
  'Конвейер': { x: -.02, y: .05, z: -10, scale: .88, rx: .34, ry: -.62, explode: 1, lines: .9, spin: .25, contour: .5, deep: .5 },
  'Проверка': { show: 0, light: 1, contour: .25, dust: 0, x: 3 },
  'Итог': { show: 0, clip: [540, 180, 520, 630], contour: .75, x: 0, scale: .6 },
  'Курс': { show: 0, contour: .9, x: -2 },
  'Анимации': { show: 0, contour: .25, deep: 1 },
  'Ролик': { show: 0, light: 1, contour: .25, dust: 0 },
  'Закладки': { show: 0, contour: .35, deep: .55 },
  'Перенос': { x: 1.72, y: .55, scale: .72, depth: 1.36, rx: .36, ry: -.5, well: 1, light: 1, contour: .25, dust: 0, spin: .5, fluid: 1 },
  'Тест': { show: 0, contour: .7 },
  'Честно': { show: 0, light: 1, contour: .3, dust: 0 },
  'Финал': { x: 1.68, y: .06, scale: .78, rx: .36, ry: -.6, wire: 1, wipe: 0, contour: 0, deep: 1, dust: .4, spin: .7 },
};
const NOTES = {  // на 6 минут: слайды около 3 минут, живой курс 2 минуты, ролик 30 секунд
  'Старт': '15 с. Мы — Aura entertainment. Наш конвейер превращает главу книги в проверенный курс для новичка. Стопка страниц на экране становится слоями породы — так и работает конвейер.',
  'Проблема': '25 с. ИИ пересказывает главу за минуту, но портит смысл: «может» становится «всегда», пропадает условие, «выше» превращается в «ниже». Новичок этого не заметит, а точность в задании — порог.',
  'Конвейер': '30 с. Под капотом: глава режется на кусочки со страницами. Модель делает учебный слой — шаги, у каждого утверждения цитата и страница. Из слоя собираются задания, анимации, ролики и курс. Курс никогда не строится из книги напрямую.',
  'Проверка': '25 с. Программа сама сверяет цитату с книгой знак в знак, страницу и числа и ловит смысловые подмены. Нажимаю: модель написала «всегда», проверка поймала. Ещё раз: в курс попадает «может».',
  'Тест': '30 с. Утром дали главы, которых конвейер не видел: три двойника, два из них на английском, и главу по бурению. Вот покрытие, узлы, задания — всё собрал замороженный конвейер. Модуль проверки сдали отдельно.',
  'Курс': '90 с. Переключаюсь на живой курс тестовой главы: путь по частям, один шаг — суть, «стр. N» у абзаца, задание с кнопкой «Где это в шаге?». На телефоне то же самое.',
  'Ролик': '30 с. Ролик по теме, которую объявили утром. Клавиша M — звук, 15–20 секунд. У ролика паспорт: каждая фраза ссылается на утверждение слоя, распознавание речи, синхрон, громкость.',
  'Финал': '15 с. Факт правим в одном месте — дальше пересборка. Переходим к ней: python presentation/rebuild_demo.py.',
  'Итог': 'Все единицы трёх глав либо в узлах, либо в списке с причиной.',
  'Анимации': 'Кадры рисует код по параметрам сцены, генеративного видео нет.',
  'Закладки': 'На контрольном пакете модуль нашёл 19 ошибок из 21 и не тронул верное.',
  'Перенос': 'Репетиция на контрольной главе — 15–20 минут, английский текст о бурении — пакет домена за 2 минуты.',
  'Честно': 'Места для сверки со сканами отмечены, шесть рисунков неточные, модель работает через Claude Code.',
};
// ---------- навигация
// на защите 6 минут: лишние слайды прячем, полная версия — index.html?full
const FULL = /full/.test(location.search);
if (!FULL) $$('[data-extra]').forEach(s => s.remove());
const slides = $$('.slide'), nav = $('#nav');
let cur = -1, timers = [];
const groups = FULL ? ['Проблема', 'Конвейер', 'Курс', 'Ролик', 'Закладки', 'Перенос', 'Финал'] : ['Проблема', 'Конвейер', 'Тест', 'Курс', 'Ролик', 'Финал'];
nav.innerHTML = groups.map(g => `<a data-g="${g}">${g}</a>`).join('');
nav.onclick = e => { e.stopPropagation(); const g = e.target.dataset.g; if (g) go(slides.findIndex(s => s.dataset.nav === g)); };
const later = (ms, f) => timers.push(setTimeout(f, ms));
let clip = [0, 0, 0, 0], clipT = [0, 0, 0, 0], sc = 1, ox = 0, oy = 0;
function fit() { sc = Math.min(innerWidth / 1600, innerHeight / 900); ox = (innerWidth - 1600 * sc) / 2; oy = (innerHeight - 900 * sc) / 2; $('#stage').style.transform = `translate(-50%,-50%) scale(${sc})`; $('#stage').style.left = innerWidth / 2 + 'px'; $('#stage').style.top = innerHeight / 2 + 'px'; $('#stage').style.transformOrigin = '50% 50%'; const o = $('#ov'); o.width = innerWidth; o.height = innerHeight; if (cur >= 0) aim(slides[cur].dataset.nav); }
function aim(name) {
  const L = { ...base, ...LOOK[name] }, c = L.clip; delete L.clip; Object.assign(GLX.T, L);
  clipT = c ? [oy + c[1] * sc, innerWidth - ox - (c[0] + c[2]) * sc, innerHeight - oy - (c[1] + c[3]) * sc, ox + c[0] * sc] : [0, 0, 0, 0];
}
function go(n) {
  n = Math.max(0, Math.min(slides.length - 1, n)); if (n === cur) return;
  timers.forEach(clearTimeout); timers = [];
  const s = slides[n], name = s.dataset.nav, prev = cur; cur = n;
  slides.forEach((x, i) => x.classList.toggle('on', i === n)); s.dataset.s = 0;
  document.body.classList.toggle('l', s.classList.contains('lt'));
  $('#pg').textContent = `${String(n + 1).padStart(2, '0')} / ${String(slides.length).padStart(2, '0')}`; $('#crit').textContent = s.dataset.crit ? 'Критерий: ' + s.dataset.crit : '';
  const owner = { 'Старт': '', 'Проверка': 'Конвейер', 'Итог': 'Конвейер', 'Анимации': 'Курс', 'Тест': FULL ? 'Перенос' : 'Тест', 'Честно': 'Финал' }[name]; nav.querySelectorAll('a').forEach(a => a.classList.toggle('cur', a.dataset.g === (owner === undefined ? name : owner)));
  aim(name);
  $$('.num span[data-d]').forEach(x => x.style.transform = ''); s.querySelectorAll('.num span[data-d]').forEach((x, i) => later(500 + i * 110, () => x.style.transform = `translateY(-${x.dataset.d * 1.06}em)`));
  $$('video').forEach(v => { if (s.contains(v) && (v.id || v.dataset.in)) { v.currentTime = v.id ? 0 : v.currentTime; v.play().catch(() => {}); } else v.pause(); });
  if (name === 'Старт') { const beat = k => later(k ? 7000 : 2200, () => { GLX.T.fold = GLX.T.fold > .5 ? 0 : 1; beat(k + 1); }); beat(0); }
  if (name === 'Конвейер') { $$('.lay').forEach(l => l.classList.remove('vis', 'hot')); [0, 1, 2, 3, 4, 5].forEach(i => later(900 + i * 1250, () => { GLX.T.hot = i; $$('.lay').forEach(l => { const k = +l.dataset.l; l.classList.toggle('hot', k === i); if (k <= i) l.classList.add('vis'); }); })); later(9000, () => { GLX.T.hot = -1; $$('.lay').forEach(l => l.classList.add('hot')); }); }
  if (name === 'Финал') { const cmd = 'python presentation/rebuild_demo.py'; $('#type').textContent = ''; GLX.S.wipe = 0; [...cmd].forEach((ch, i) => later(1400 + i * 55, () => $('#type').textContent += ch)); later(500, () => GLX.T.wipe = 1.1); }
  $('#notes').innerHTML = `<small>${name}</small><br>${NOTES[name] || ''}`;
  try { history.replaceState(null, '', '#' + (n + 1)); } catch (e) { /* во встроенном окне нельзя */ }
}
const next = () => { const s = slides[cur], k = +(s.dataset.steps || 0); if (+s.dataset.s < k) s.dataset.s = +s.dataset.s + 1; else go(cur + 1); };
const back = () => { const s = slides[cur]; if (+s.dataset.s > 0) s.dataset.s = +s.dataset.s - 1; else go(cur - 1); };
addEventListener('keydown', e => {
  if (['ArrowRight', 'PageDown', ' ', 'Enter', 'ArrowDown'].includes(e.key)) { e.preventDefault(); next(); }
  else if (['ArrowLeft', 'PageUp', 'ArrowUp', 'Backspace'].includes(e.key)) { e.preventDefault(); back(); }
  else if (e.key === 'Home') go(0); else if (e.key === 'End') go(slides.length - 1);
  else if ('fFаА'.includes(e.key)) document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen();
  else if ('nNтТ'.includes(e.key)) $('#notes').classList.toggle('on');
  else if ('mMьЬ'.includes(e.key)) { const v = $('#short'); v.muted = !v.muted; if (!v.muted) v.currentTime = 0; }
});
addEventListener('click', e => e.clientX < innerWidth * .25 ? back() : next());
let wl = 0; addEventListener('wheel', e => { const t = Date.now(); if (t - wl < 900 || Math.abs(e.deltaY) < 8) return; wl = t; e.deltaY > 0 ? next() : back(); }, { passive: true });
addEventListener('resize', fit);
// ---------- подписи слоёв: держатся за грани блока
const ov = $('#ov').getContext('2d');
function overlay(t) {
  ov.clearRect(0, 0, innerWidth, innerHeight);
  const name = slides[cur] && slides[cur].dataset.nav;
  if (name === 'Конвейер') {
    const pts = [0, 1, 2, 3, 4, 5].map(i => GLX.project(i, 1)), gap = 106 * sc, mid = innerHeight / 2 + 2.6 * gap;
    $$('.lay').forEach(l => {
      const i = +l.dataset.l, y = mid - i * gap * 1.04, st = (y - oy) / sc - 34; l.style.top = st + 'px';
      if (!l.classList.contains('vis')) return;
      const hot = l.classList.contains('hot'), p = pts[i], x1 = ox + 1080 * sc, y1 = oy + (st + 1) * sc;
      ov.strokeStyle = hot ? 'rgba(255,255,255,.85)' : 'rgba(255,255,255,.3)'; ov.lineWidth = 1.5; ov.setLineDash([5, 6]); ov.lineDashOffset = -t * 22;
      ov.beginPath(); ov.moveTo(p[0], p[1]); ov.lineTo(x1 - 44 * sc, y1); ov.lineTo(x1, y1); ov.stroke(); ov.setLineDash([]);
      ov.strokeRect(p[0] - 9, p[1] - 9, 18, 18); ov.fillStyle = hot ? '#0a62ff' : 'rgba(255,255,255,.5)'; ov.fillRect(p[0] - 4, p[1] - 4, 8, 8);
    });
  }
  if (name === 'Старт') { // прицельные рамки вокруг блока
    const a = GLX.project(5, -1), b = GLX.project(2, 1), c = GLX.project(0, -1); ov.strokeStyle = 'rgba(255,255,255,.5)'; ov.lineWidth = 1.3;
    ov.strokeRect(a[0] - 14, a[1] - 60 * sc, 200 * sc, 150 * sc); ov.strokeRect(b[0] - 20, b[1] - 20, 40, 40); ov.strokeRect(c[0] - 12, c[1] - 12, 24, 24);
    ov.setLineDash([4, 6]); ov.lineDashOffset = -t * 18; ov.beginPath(); ov.moveTo(c[0], c[1]); ov.lineTo(a[0] - 14 + 200 * sc, a[1] + 90 * sc); ov.lineTo(b[0], b[1]); ov.closePath(); ov.stroke(); ov.setLineDash([]);
  }
}
function tick(now) {
  GLX.frame(now); overlay(now / 1000);
  for (let i = 0; i < 4; i++) clip[i] += (clipT[i] - clip[i]) * .075;
  $('#gl').style.clipPath = clip.some(v => v > .5) ? `inset(${clip.map(v => v.toFixed(1) + 'px').join(' ')})` : 'none';
  requestAnimationFrame(tick);
}
$$('.row video').forEach(v => eye.observe(v)); document.body.classList.toggle('nogl', !GLX.ok); fit(); go((parseInt(location.hash.slice(1)) || 1) - 1); Object.assign(GLX.S, GLX.T); requestAnimationFrame(tick);

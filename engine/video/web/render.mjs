// Покадровый рендер сцены в Edge без установки пакетов: node engine/video/web/render.mjs job.json
// job: {scene, W, H, fps, total, beats, params, style, out (mp4 без звука) | shots: [{t, file}]}
// Кадр зависит только от времени и данных job: одинаковый вход — одинаковая картинка.
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { pathToFileURL, fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const job = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const edges = [process.env.EDGE_PATH, 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  'C:/Program Files/Microsoft/Edge/Application/msedge.exe', 'C:/Program Files/Google/Chrome/Application/chrome.exe'].filter(Boolean);
const exe = edges.find(p => fs.existsSync(p));
if (!exe) throw new Error('не найден Edge или Chrome; укажите путь в EDGE_PATH');

const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'scene-'));
const br = spawn(exe, ['--headless=new', '--remote-debugging-port=0', `--user-data-dir=${profile}`, '--no-first-run',
  '--no-default-browser-check', '--disable-extensions', '--disable-background-networking', '--hide-scrollbars',
  '--force-color-profile=srgb', '--allow-file-access-from-files', 'about:blank'], { stdio: 'ignore' });

const portFile = path.join(profile, 'DevToolsActivePort');
for (let i = 0; i < 150 && !fs.existsSync(portFile); i++) await new Promise(r => setTimeout(r, 100));
await new Promise(r => setTimeout(r, 200));
const port = fs.readFileSync(portFile, 'utf8').split('\n')[0].trim();
const tab = (await (await fetch(`http://127.0.0.1:${port}/json/list`)).json()).find(x => x.type === 'page');
const ws = new WebSocket(tab.webSocketDebuggerUrl);
await new Promise((ok, bad) => { ws.onopen = ok; ws.onerror = bad; });
let seq = 0, loaded;
const wait = new Map(), onLoad = new Promise(r => { loaded = r; });
ws.onmessage = e => {
  const m = JSON.parse(e.data);
  if (m.method === 'Page.loadEventFired') loaded();
  if (m.id && wait.has(m.id)) {
    const [ok, bad] = wait.get(m.id);
    wait.delete(m.id);
    if (m.error) bad(new Error(JSON.stringify(m.error))); else ok(m.result);
  }
};
const call = (method, params = {}) => new Promise((ok, bad) => {
  const id = ++seq;
  wait.set(id, [ok, bad]);
  ws.send(JSON.stringify({ id, method, params }));
});
const js = async expression => {
  const r = await call('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
  if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text);
  return r.result.value;
};
const frame = async (t, q = 0.93) => Buffer.from(await js(`Stage.shot(${t},${q})`), 'base64');

try {
  await call('Page.enable');
  await call('Page.navigate', { url: pathToFileURL(path.join(here, 'page.html')).href + '?scene=' + encodeURIComponent(job.scene) });
  await onLoad;
  await js(`document.fonts.ready.then(() => { Stage.start(${JSON.stringify(job)}); return 1; })`);
  for (const s of job.shots || []) fs.writeFileSync(s.file, await frame(s.t, 0.9));
  if (job.out) {
    const ff = spawn(job.ffmpeg || 'ffmpeg', ['-y', '-hide_banner', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(job.fps),
      '-c:v', 'mjpeg', '-i', '-', '-vf', 'format=yuv420p', '-c:v', 'libx264', '-preset', 'medium', '-crf', String(job.crf || 23),
      '-movflags', '+faststart', job.out], { stdio: ['pipe', 'inherit', 'inherit'] });
    const done = new Promise((ok, bad) => ff.on('close', c => (c === 0 ? ok() : bad(new Error('ffmpeg ' + c)))));
    const n = Math.ceil(job.total * job.fps);
    for (let i = 0; i < n; i++) {
      if (!ff.stdin.write(await frame(i / job.fps))) await new Promise(r => ff.stdin.once('drain', r));
      if (i % 200 === 0) console.error(`кадр ${i}/${n}`);
    }
    ff.stdin.end();
    await done;
  }
} finally {
  try { await call('Browser.close'); } catch { br.kill(); }
  try { ws.close(); } catch { /* уже закрыт */ }
  for (let i = 0; i < 10; i++) {
    try { fs.rmSync(profile, { recursive: true, force: true }); break; } catch { await new Promise(r => setTimeout(r, 200)); }
  }
}
process.exit(process.exitCode || 0);

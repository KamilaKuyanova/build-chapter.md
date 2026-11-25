// Снимки курса на ширине телефона: out/latyshova/index.html -> presentation/img/*.jpg
import { spawn } from 'node:child_process'; import fs from 'node:fs'; import os from 'node:os'; import path from 'node:path'; import { pathToFileURL } from 'node:url';
const prof = fs.mkdtempSync(path.join(os.tmpdir(), 'shots-'));
const br = spawn('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', ['--headless=new', '--remote-debugging-port=0', '--user-data-dir=' + prof, '--no-first-run', '--allow-file-access-from-files', 'about:blank'], { stdio: 'ignore' });
const pf = path.join(prof, 'DevToolsActivePort'); for (let i = 0; i < 100 && !fs.existsSync(pf); i++) await new Promise(r => setTimeout(r, 100)); await new Promise(r => setTimeout(r, 300));
const port = fs.readFileSync(pf, 'utf8').split('\n')[0].trim(), tab = (await (await fetch(`http://127.0.0.1:${port}/json/list`)).json()).find(x => x.type === 'page');
const ws = new WebSocket(tab.webSocketDebuggerUrl); await new Promise(r => ws.onopen = r); let id = 0; const w = new Map(); ws.onmessage = e => { const m = JSON.parse(e.data); if (w.has(m.id)) { w.get(m.id)(m.result); w.delete(m.id); } };
const call = (method, params = {}) => new Promise(r => { w.set(++id, r); ws.send(JSON.stringify({ id, method, params })); });
const js = async e => (await call('Runtime.evaluate', { expression: e, returnByValue: true, awaitPromise: true })).result?.value;
const wait = ms => new Promise(r => setTimeout(r, ms));
await call('Page.enable'); fs.mkdirSync('presentation/img', { recursive: true });
const shot = async (name, hash, h, from) => {
  await call('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 2, mobile: true });
  await call('Page.navigate', { url: 'about:blank' }); await wait(200);
  await call('Page.navigate', { url: pathToFileURL('out/latyshova/index.html').href + hash }); await wait(1800);
  await js(`(()=>{const k='course:'+document.title,n=[...document.querySelectorAll('.nd')].map(x=>x.dataset.node),o={done:{},seen:{},cards:{},answers:{}};n.slice(0,5).forEach(i=>o.done[i]=true);n.slice(0,6).forEach(i=>o.seen[i]=1);n.slice(0,4).forEach(i=>o.cards[i]='know');o.last=n[5];document.querySelectorAll('.quiz').forEach(q=>{const t=JSON.parse(q.dataset.ex);if(o.done[t.step_id])o.answers[t.id]={first:true,ok:true,tries:1}});localStorage[k]=JSON.stringify(o);location.reload()})()`); await wait(1800);
  await js(`(()=>{const s=document.createElement('style');s.textContent='nav.main{display:none!important}header.top,.unit,.bar{position:relative!important;top:0!important}*{animation:none!important}';document.head.append(s)})()`); await wait(300);
  await js(`document.querySelectorAll('img').forEach(i=>i.loading='eager')`); await wait(900);
  const top = from ? await js(from) : 0, full = await js('document.documentElement.scrollHeight');
  const s = await call('Page.captureScreenshot', { format: 'jpeg', quality: 82, captureBeyondViewport: true, clip: { x: 0, y: top || 0, width: 390, height: Math.min(h, full - (top || 0)), scale: 1 } });
  fs.writeFileSync(`presentation/img/${name}.jpg`, Buffer.from(s.data, 'base64')); console.log(name, full);
};
await shot('path', '#/path', 1500);
await shot('step', '#/step/latyshova.borehole_wall', 3600);
await shot('task', '#/step/latyshova.borehole_wall', 1500, `(()=>{const q=[...document.querySelectorAll('.quiz')].find(e=>e.offsetParent);return q?Math.max(0,q.getBoundingClientRect().top+scrollY-90):0})()`);
await call('Browser.close'); process.exit(0);

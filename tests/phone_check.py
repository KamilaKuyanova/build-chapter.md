#!/usr/bin/env python3
"""Запуск: python tests/phone_check.py latyshova basniev kuznetsov (нужен Microsoft Edge).
Проверка курса на ширине телефона 390 px: каждый шаг открывается в headless Edge, ширина страницы зажата до 390 px,
ищутся элементы, вылезающие за край (без учёта содержимого блоков с собственной прокруткой)."""
import json
import pathlib
import re
import subprocess
import sys

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PROF = str(pathlib.Path.home() / "AppData/Local/Temp/edge-headless-phone")
PROBE = """<style>html{width:390px!important;max-width:390px!important;overflow:visible}</style><script>
function probe(){var W=390,r=[];document.querySelectorAll('main *').forEach(function(e){
 for(var a=e.parentElement;a;a=a.parentElement){var o=getComputedStyle(a).overflowX;if(o=='auto'||o=='scroll'||o=='hidden')return}
 var b=e.getBoundingClientRect();if(b.width>0&&b.right>W+1)r.push(e.tagName+'.'+(e.className||'')+' R='+Math.round(b.right)+' '+(e.textContent||'').slice(0,50).replace(/\\s+/g,' '))});
 return r}
var IDS=__IDS__.concat(['__path__']),out={},k=0;
function next(){if(k>0){var r=probe();if(r.length)out[IDS[k-1]]=r.slice(0,3)}
 if(k>=IDS.length){var d=document.createElement('pre');d.id='PROBE';d.textContent=JSON.stringify(out);document.body.appendChild(d);return}
 var id=IDS[k++];location.hash=id=='__path__'?'#/path':'#/step/'+id;setTimeout(next,60)}
setTimeout(next,500)</script></body>"""

bad = 0
for ch in sys.argv[1:]:
    src = pathlib.Path(f"out/{ch}/index.html")
    probe = src.with_name("probe.html")
    page = src.read_text(encoding="utf-8")
    ids = re.search(r"var ORDER=(\[.*?\]);", page).group(1)
    probe.write_text(page.replace("</body>", PROBE.replace("__IDS__", ids)), encoding="utf-8")
    dom = subprocess.run([EDGE, "--headless=new", "--disable-gpu", f"--user-data-dir={PROF}", "--window-size=500,900",
                          "--virtual-time-budget=30000", "--dump-dom", probe.resolve().as_uri()], capture_output=True, text=True,
                         encoding="utf-8", errors="replace").stdout
    probe.unlink()
    m = re.search(r'<pre id="PROBE">(.*?)</pre>', dom, re.S)
    res = json.loads(m.group(1).replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")) if m else None
    if res is None:
        print(ch, "проба не отработала")
        bad += 1
        continue
    print(f"{ch}: шагов с вылезанием за 390 px: {len(res)}")
    for k, v in list(res.items())[:6]:
        print("  ", k, v)
    bad += len(res)
sys.exit(1 if bad else 0)

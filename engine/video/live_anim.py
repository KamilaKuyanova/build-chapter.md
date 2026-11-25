#!/usr/bin/env python3
"""Живые анимации шагов: немые петли 10–20 с из сцен engine/video/web по файлу data/<глава>/anim_scenes.json.

Файл: {"bases": {имя: {"scene": ..., "params": {...}}},
       "nodes": {"<id узла>": {"base": имя | "scene"+"params", "params": {поверх базы}, "what": "что показано",
                               "script": [{"head": "слова на экране", "claim": "c1", "sec": 3.5, "beat": {...}}]}}}
Каждый кадр ссылается на утверждение своего узла: ничего сверх слоя. Метка происхождения и преувеличения — в кадре.
Собранная петля не пересобирается, если её описание не менялось (хеш рядом с mp4).
Запуск: python engine/video/live_anim.py --dir data/kuznetsov [--only узел] [--preview]"""
import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "engine"))
import domain  # noqa: E402
import tts  # noqa: E402

HOLD = 1.6
SIZE = (960, 1080)  # в курсе на телефоне картинке достаётся 356 px: подпись 44 читается как 16 px


def merged(doc, spec):
    base = (doc.get("bases") or {}).get(spec.get("base"), {})
    return spec.get("scene") or base.get("scene"), dict(base.get("params", {}), **spec.get("params", {}))


def check(doc, layer):
    """Ошибки описания: нет узла, сцены, утверждения; длинный текст или формула на экране."""
    nodes = {n["id"]: n for n in layer["nodes"]}
    cat = {p.stem[6:] for p in (HERE / "web").glob("scene_*.json")}
    errs = []
    for nid, spec in doc.get("nodes", {}).items():
        if nid not in nodes:
            errs.append(f"{nid}: нет такого узла")
            continue
        if spec.get("need_new_scene"):
            continue
        scene, params = merged(doc, spec)
        if scene not in cat:
            errs.append(f"{nid}: нет сцены {scene}")
        if not params.get("assumptions"):
            errs.append(f"{nid}: не названы допущения (params.assumptions)")
        claims = {c["id"].split("#")[1] for c in nodes[nid]["claims"]}
        for i, s in enumerate(spec.get("script", []), 1):
            if s.get("claim") not in claims:
                errs.append(f"{nid}, кадр {i}: нет утверждения {s.get('claim')}")
            if len(s["head"].split()) > 8 or re.search(r"[α-ωΑ-Ω=^]", s["head"]):
                errs.append(f"{nid}, кадр {i}: на экране больше 8 слов или формула")
        if not 2 <= len(spec.get("script", [])) <= 7:
            errs.append(f"{nid}: кадров {len(spec.get('script', []))}, нужно 2–7")
    return errs


def build(d, only=None, preview=False):
    """Возвращает {узел: запись для illustrations.json} по всем живым анимациям главы."""
    d = pathlib.Path(d)
    path = d / "anim_scenes.json"
    if not path.exists():
        return {}
    doc = json.loads(path.read_text(encoding="utf-8"))
    layer = json.loads((d / "layer.json").read_text(encoding="utf-8-sig"))
    errs = check(doc, layer)
    for e in errs:
        print("  [error]", e)
    bad = {e.split(":")[0].split(",")[0] for e in errs}
    nodes = {n["id"]: n for n in layer["nodes"]}
    media, out = d / "media", ROOT / "out" / "anim" / d.name
    media.mkdir(exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    node_exe = shutil.which("node") or os.path.join(os.environ.get("ProgramFiles", ""), "nodejs", "node.exe")
    style, extra = domain.load("styleguide.json"), {}
    for nid, spec in doc["nodes"].items():
        if nid in bad or spec.get("need_new_scene") or (only and only not in nid):
            continue
        scene, params = merged(doc, spec)
        node, beats, t = nodes[nid], [], 0.0
        for s in spec["script"]:
            sec = s.get("sec", 3.6)
            beats.append({"t_start": round(t, 2), "t_end": round(t + sec * 0.82, 2), "text": "", "beat": dict(s["beat"], head=s["head"])})
            t += sec
        total = t + HOLD
        params.setdefault("source", "стр. " + ", ".join(str(p) for p in node.get("pages", [])[:3]))
        job = {"scene": scene, "W": SIZE[0], "H": SIZE[1], "fps": 20, "total": total, "beats": beats, "params": params, "style": style,
               "ffmpeg": tts.ffmpeg(), "crf": 25}
        mark = media / f"anim_{nid}.hash"
        code = "".join((HERE / "web" / f).read_text(encoding="utf-8") for f in ("lib.js", f"scene_{scene}.js"))
        h = hashlib.sha1((json.dumps(job, ensure_ascii=False, sort_keys=True) + code).encode()).hexdigest()[:12]
        mp4 = media / f"anim_{nid}.mp4"
        if preview:
            job["shots"] = [{"t": round(b["t_start"] + 0.9 * (b["t_end"] - b["t_start"]), 2), "file": str(out / f"{nid}_{i}.jpg")}
                            for i, b in enumerate(beats)]
        elif not (mp4.exists() and mark.exists() and mark.read_text() == h):
            job["out"] = str(mp4)
        if preview or job.get("out"):
            jp = out / "job.json"
            jp.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
            for _ in range(2):   # редкий сбой браузера: вторая попытка
                r = subprocess.run([node_exe, str(HERE / "web" / "render.mjs"), str(jp)], capture_output=True, text=True, encoding="utf-8", errors="replace")
                if r.returncode == 0:
                    break
            if r.returncode != 0:
                print(f"  [error] {nid}: {r.stderr.strip()[-300:]}")
                continue
            if not preview:
                mark.write_text(h)
            print(f"  {nid}: {scene}, {total:.0f} с", flush=True)
        title = node.get("title_novice") or node["title"]
        used = sorted({f"{nid}#{s['claim']}" for s in spec["script"]})
        extra[nid] = [{"id": f"{nid}.anim", "file": f"media/anim_{nid}.mp4", "frame_class": "B", "origin": "code_from_model",
                       "label": params.get("label", "схема"), "caption": f"Анимация: {spec['what']}. {total:.0f} с, без звука.",
                       "alt": f"Анимация к шагу «{title}»: {spec['what']}",
                       "source": f"стр. {', '.join(str(p) for p in node.get('pages', [])[:3])}; допущения: {'; '.join(params.get('assumptions', []))}",
                       "claim_ids": used, "prompt": None, "scene": scene}]
    return extra


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--only")
    ap.add_argument("--preview", action="store_true")
    a = ap.parse_args()
    print(len(build(a.dir, a.only, a.preview)), "живых анимаций")

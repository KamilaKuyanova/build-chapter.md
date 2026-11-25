"""Презентация защиты: цифры из data/ и ролики в presentation/media. После теста запустить ещё раз — слайды обновятся сами.

python presentation/build.py          цифры, петли и ролик
python presentation/build.py shots    ещё и снимки курса (нужны Edge и node)
"""
import base64
import glob
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
HERE = ROOT / "presentation"
LOOPS = ["kuznetsov.structural_traps", "latyshova.water_loss", "basniev.psss_radial_front", "kuznetsov.karachaganak_zones",
         "latyshova.owc_transition", "kuznetsov.secondary_porosity", "basniev.piezometric_curves", "kuznetsov.seal_formation",
         "latyshova.borehole_wall", "kuznetsov.group_atoll", "basniev.flow_profile", "kuznetsov.reef_deposits"]
# Контрольный пакет организаторов (ключ открыт для самопроверки), счёт их программой score_review.py
CONTROL = {"targets": 40, "errors": 21, "found": 19, "false": 0, "weighted": 90}
TOTALS_NOTE = "три обучающие главы"


def load(p):
    return json.loads(pathlib.Path(p).read_text(encoding="utf-8-sig"))


def ffmpeg():
    p = shutil.which("ffmpeg")
    if p:
        return p
    pat = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\ffmpeg-*\bin\ffmpeg.exe")
    return (glob.glob(pat) or [None])[0]


def chapter(spec):
    d = ROOT / "data" / spec["id"]
    if not (d / "layer.json").exists():
        return None
    layer, tasks = load(d / "layer.json"), load(d / "tasks.json") if (d / "tasks.json").exists() else {"tasks": []}
    run = subprocess.run([sys.executable, "run.py", "check", spec["id"]], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", env={**os.environ, "PYTHONUTF8": "1"})
    cov = re.search(r"покрытие (\d+)/(\d+)", run.stdout)  # тот же счёт, что у проверки конвейера
    loops = load(d / "anim_scenes.json")["nodes"] if (d / "anim_scenes.json").exists() else {}
    return {"id": spec["id"], "title": spec["title"], "set": spec["set"], "lang": spec.get("lang", "ru"), "domain": spec.get("domain", "geology"),
            "nodes": len(layer["nodes"]), "claims": sum(len(n["claims"]) for n in layer["nodes"]), "tasks": len(tasks["tasks"]),
            "loops": sum(1 for v in loops.values() if not v.get("need_new_scene")),
            "units": int(cov.group(2)) if cov else 0, "covered": int(cov.group(1)) if cov else 0,
            "scan": sum(len(n.get("needs_scan", [])) for n in layer["nodes"])}


def videos():
    out = []
    for p in sorted((ROOT / "videos").glob("*/passport.json")):
        d = load(p)
        out.append({"id": d["video_id"], "format": d["format"], "sec": d["duration_sec"], "check": d.get("audio_check"),
                    "prediction": d.get("prediction_question")})
    return out


def media():
    out = HERE / "media"
    out.mkdir(exist_ok=True)
    ff = ffmpeg()
    if not ff:
        print("нет ffmpeg: видео не подготовлены")
        return
    jobs = [(ROOT / "data" / n.split(".")[0] / "media" / f"anim_{n}.mp4", out / f"loop_{i:02d}.mp4", "scale=560:-2", "28", False) for i, n in enumerate(LOOPS)]
    jobs.append((ROOT / "data/latyshova/media/latyshova_signs.mp4", out / "short.mp4", "scale=720:-2", "24", True))
    for src, dst, vf, crf, sound in jobs:
        if not src.exists():
            print("нет", src.relative_to(ROOT))
            continue
        if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
            continue
        subprocess.run([ff, "-v", "error", "-y", "-i", str(src), "-vf", vf, "-c:v", "libx264", "-crf", crf, "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                        *(["-c:a", "aac", "-b:a", "128k"] if sound else ["-an"]), str(dst)], check=True)
        print("  ", dst.name)


def single():
    """Одна страница со всем внутри: out/Защита.html можно унести на флешке."""
    page = (HERE / "index.html").read_text(encoding="utf-8")
    files = sorted([*(HERE / "media").glob("*.mp4"), *(HERE / "img").glob("*.jpg")])
    data = {f"{p.parent.name}/{p.name}": base64.b64encode(p.read_bytes()).decode() for p in files}
    code = "window.MEDIA = " + json.dumps(data) + ";\n" + "\n".join((HERE / f).read_text(encoding="utf-8") for f in ("facts.js", "gl.js", "deck.js"))
    page = page.replace('<script src="facts.js"></script><script src="gl.js"></script><script src="deck.js"></script>', "<script>" + code.replace("</script", "<\\/script") + "</script>")
    out = ROOT / "out" / "Защита.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print(f"{out.relative_to(ROOT)}: {out.stat().st_size // 2 ** 20} МБ")


def main():
    cfg = load(ROOT / "chapters.json")["chapters"]
    ch = [c for c in (chapter(s) for s in cfg) if c]
    train = [c for c in ch if c["set"] == "train"]
    total = {k: sum(c[k] for c in train) for k in ("nodes", "claims", "tasks", "loops", "units", "covered", "scan")}
    team = next((ln.split(":", 1)[1].strip() for ln in (ROOT / "MANIFEST.md").read_text(encoding="utf-8").splitlines() if ln.startswith("Команда:")), "")
    facts = {"team": "" if "ЗАПОЛНИТЬ" in team else team, "total": total, "train": train, "test": [c for c in ch if c["set"] == "test"],
             "control": CONTROL, "videos": videos(), "loops": LOOPS}
    (HERE / "facts.js").write_text("window.FACTS = " + json.dumps(facts, ensure_ascii=False, indent=1) + ";\n", encoding="utf-8")
    print("facts.js:", total, "| тестовых глав:", len(facts["test"]))
    media()
    single()
    if "shots" in sys.argv:
        subprocess.run([shutil.which("node") or "node", str(HERE / "shots.mjs")], check=True, cwd=ROOT)


if __name__ == "__main__":
    main()

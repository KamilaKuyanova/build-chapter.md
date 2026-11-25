"""Показ сцен без озвучки: python tests/preview_scenes.py wellbore -> out/scene_demos/wellbore_NN.jpg (по кадру на фразу)."""
import json
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))
import domain  # noqa: E402

for name in sys.argv[1:] or ["wellbore", "strata"]:
    d = json.loads((ROOT / "tests" / "scene_demos" / f"{name}.json").read_text(encoding="utf-8"))
    out = ROOT / "out" / "scene_demos"
    out.mkdir(parents=True, exist_ok=True)
    beats = [dict(s, t_start=i * 5.0, t_end=i * 5.0 + 4) for i, s in enumerate(d["script"])]
    W, H = (1080, 1920) if d["format"] == "short" else (1920, 1080)
    job = {"scene": d.get("scene", name), "W": W, "H": H, "fps": 30, "total": len(beats) * 5.0, "beats": beats, "params": d["params"],
           "style": domain.load("styleguide.json"),
           "shots": [{"t": b["t_start"] + 3.2, "file": str(out / f"{name}_{i:02d}.jpg")} for i, b in enumerate(beats)]}
    (out / "job.json").write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
    subprocess.run([shutil.which("node") or "node", str(ROOT / "engine" / "video" / "web" / "render.mjs"), str(out / "job.json")], check=True)
    print(name, len(beats), "кадров ->", out)

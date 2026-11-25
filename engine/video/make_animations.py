#!/usr/bin/env python3
"""Анимации логики шага для видеоёмких узлов без ролика (ТЗ: «в главе без ролика узлы, которым маршрутизация дала видео,
закрываются в курсе интерактивом или анимацией»). Без звука, короткая петля, кадры кодом (класс B, метка «схема»).

Параметры берутся только из текста узла — новых фактов и чисел нет:
- есть decision_on_data  -> step_procedure: признаки → правило → вывод (→ контрпример);
- есть разобранный пример -> step_procedure: шаги примера автора и итог;
- иначе                  -> process_state: утверждения шага по порядку (наблюдение → вывод → допущение) со страницами.
Выход: data/<глава>/media/anim_<узел>.mp4 и data/<глава>/anim_extra.json (для gen_illustrations --extra).
Запуск: python engine/video/make_animations.py --dir data/kuznetsov [--fps 10] [--limit N]"""
import argparse
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "engine"))
import templates  # noqa: E402
import template_coverage  # noqa: E402

KIND = {"observation": "наблюдение", "inference": "вывод", "assumption": "допущение"}
STEP_SEC, HOLD = 3.2, 2.5


def short(s, n=320):
    s = " ".join((s or "").split())
    return s if len(s) <= n else s[:n].rsplit(" ", 1)[0] + "…"


def spec_for(node):
    title = node.get("title_novice") or node["title"]
    pages = ", ".join(str(p) for p in node.get("pages", [])[:3])
    note = f"по тексту шага, стр. {pages}" if pages else "по тексту шага"
    dd = node.get("decision_on_data")
    if dd and dd.get("rule") and dd.get("conclusion"):
        steps = [{"name": "Признаки", "detail": short("; ".join(dd.get("features", [])))},
                 {"name": "Правило", "detail": short(dd["rule"])}, {"name": "Вывод", "detail": short(dd["conclusion"])}]
        if dd.get("counterexample"):
            steps.append({"name": "Где не работает", "detail": short(dd["counterexample"])})
        return "step_procedure", {"title": "Решение на данных: " + title, "source_note": note, "steps": steps}, "признаки → правило → вывод"
    ex = next((x for x in node.get("worked_examples", []) if len(x.get("steps", [])) >= 2), None)
    if ex:
        steps = [{"name": f"Шаг {i + 1}", "detail": short(s)} for i, s in enumerate(ex["steps"][:5])]
        steps.append({"name": "Итог", "detail": short(ex["result"]), "output": f"стр. {ex.get('page_pdf', '')}"})
        return "step_procedure", {"title": "Пример автора: " + title, "source_note": note, "steps": steps}, "шаги примера автора"
    claims = node["claims"][:5]
    stages = [{"name": KIND.get(c["kind"], c["kind"]), "note": short(c["text"], 150) + f" (стр. {c['page_pdf']})", "values": {}}
              for c in claims]
    return "process_state", {"title": title, "source_note": note, "stages": stages, "quantities": [],
                             "chain_title": "Цепочка шага по утверждениям главы"}, "утверждения шага по порядку"


def beats_for(tpl, params):
    n = len(params["steps"] if tpl == "step_procedure" else params["stages"])
    key = "k" if tpl == "step_procedure" else "s"
    return [{"t_start": i * STEP_SEC, "t_end": i * STEP_SEC + STEP_SEC * 0.7, "text": "",
             "beat": {key: [max(0, i - 1), i]}} for i in range(n)], n * STEP_SEC + HOLD


def render(tpl_name, params, out, fps):
    import tts
    tpl = templates.load(tpl_name)
    beats, total = beats_for(tpl_name, params)
    W, H = 1920, 1080
    cmd = [tts.ffmpeg(), "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(fps), "-i", "-", "-vf", "scale=1280:720", "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "26", "-pix_fmt", "yuv420p", "-an", "-movflags", "+faststart", str(out)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(int(total * fps)):
        p.stdin.write(tpl.render(i / fps, beats, params, W, H).tobytes())
    p.stdin.close()
    if p.wait() != 0:
        raise RuntimeError("ffmpeg не собрал анимацию")
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--fps", type=int, default=10)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    d = pathlib.Path(a.dir)
    rep = template_coverage.build(d)
    nodes = {n["id"]: n for n in json.loads((d / "layer.json").read_text(encoding="utf-8-sig"))["nodes"]}
    media = d / "media"
    media.mkdir(exist_ok=True)
    extra, done = {}, 0
    for row in rep["rows"]:
        if row["video"]:
            continue   # у узла есть ролик
        node = nodes[row["node_id"]]
        tpl, params, what = spec_for(node)
        out = media / f"anim_{node['id']}.mp4"
        secs = render(tpl, params, out, a.fps)
        extra[node["id"]] = [{
            "id": f"{node['id']}.anim", "file": f"media/anim_{node['id']}.mp4", "frame_class": "B", "origin": "code_from_model",
            "label": "схема", "caption": f"Анимация логики шага ({what}), {secs:.0f} с, без звука.",
            "alt": f"Анимация: {what} для шага «{node.get('title_novice') or node['title']}»; текст шага на экране",
            "source": f"шаблон {tpl}; текст и страницы — из слоя", "claim_ids": [c["id"] for c in node["claims"]][:3], "prompt": None}]
        done += 1
        print(f"  {node['id']}: {tpl}, {secs:.0f} с")
        if a.limit and done >= a.limit:
            break
    (d / "anim_extra.json").write_text(json.dumps(extra, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{d.name}: анимаций {done}")


if __name__ == "__main__":
    main()

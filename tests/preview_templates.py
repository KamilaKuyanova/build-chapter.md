#!/usr/bin/env python3
"""Превью всех 8 шаблонов сцен на образцах параметров (EXAMPLE) в 9:16 и 16:9 -> out/templates/*.png.
Проверяет, что каждый шаблон рисует кадр без ошибок и даёт спецификацию сцены. Запуск: python tests/preview_templates.py"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine" / "video"))
import templates  # noqa: E402

BEATS = {
    "tool_and_curve": [{"d": [0, 60], "hl": ["RES"], "band": [50, 72]}, {"d": [60, 90], "labels": True}],
    "formula_explorer": [{"tm": [60, 3600]}, {"tm": [3600, 21600], "kappas": [0.1, 1.0, 5.0]}],
    "process_state": [{"s": [0, 1]}, {"s": [1, 1.6]}],
    "time_evolution": [{"T": [0, 6]}, {"T": [6, 9]}],
    "section_views": [{"y": [0, 0.3], "ve": [10, 10]}, {"y": [0.3, 0.3], "ve": [10, 1]}],
    "step_procedure": [{"k": [0, 1]}, {"k": [1, 2]}],
    "decision_panel": [{"case": [0, 0], "band": [1, 1]}, {"case": [1, 1], "band": [1, 1]}],
    "compare_signs": [{"k": [0, 2]}, {"k": [2, 4], "winner": True}],
}


def main():
    out = ROOT / "out" / "templates"
    out.mkdir(parents=True, exist_ok=True)
    ok = True
    for name in templates.NAMES:
        m = templates.load(name)
        beats = [{"t_start": i * 5.0, "t_end": i * 5.0 + 4.5, "text": "", "on_screen": f"Подпись шаблона {name}", "beat": bt}
                 for i, bt in enumerate(BEATS[name])]
        try:
            sp = m.spec(m.EXAMPLE)
            assert sp["state_model"] and sp["invariants"] and sp["frame_class"] in ("A", "B")
            for tag, (W, H) in (("v", (1080, 1920)), ("h", (1920, 1080))):
                m.render(9.2, beats, m.EXAMPLE, W, H).save(out / f"{name}_{tag}.png")
            print(f"OK   {name} ({m.TYPE}): {m.STATE}")
        except Exception as e:  # noqa: BLE001
            ok = False
            print(f"FAIL {name}: {type(e).__name__}: {e}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

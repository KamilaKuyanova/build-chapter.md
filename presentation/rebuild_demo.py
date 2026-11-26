"""Пересборка на защите: меняем одно число в учебном слое и показываем его на странице курса.

python presentation/rebuild_demo.py                 4—8 см³/ч -> 5—8 см³/ч в главе Латышовой
python presentation/rebuild_demo.py "4—8" "6—8"     своё число (старый текст, новый текст)
python presentation/rebuild_demo.py --undo          вернуть как было

Учебный слой собирается из ответов модели в work/<глава>/answers: правим там, затем одна команда
`python run.py rebuild <глава>` пересобирает слой, проверку, задания и курс."""
import json
import pathlib
import shutil
import subprocess
import sys
import time
from urllib.request import pathname2url

ROOT = pathlib.Path(__file__).resolve().parents[1]
CH = "latyshova"
OLD, NEW = "4—8 см³/ч", "5—8 см³/ч"
ANS = ROOT / "work" / CH / "answers"
KEEP = ROOT / "work" / CH / "answers_before_demo"


def rebuild():
    t = time.time()
    out = subprocess.run([sys.executable, "run.py", "rebuild", CH], cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                         env={**__import__("os").environ, "PYTHONUTF8": "1"})
    lines = (out.stdout + out.stderr).splitlines()
    for ln in lines:
        if "NUMBER_NOT_IN_SOURCE" in ln or "итог" in ln or "Итог" in ln:
            print("  " + ln.strip())
    print(f"Пересборка: {time.time() - t:.0f} с")


def open_step(text):
    layer = json.loads((ROOT / "data" / CH / "layer.json").read_text(encoding="utf-8"))
    node = next((n for n in layer["nodes"] if text in json.dumps(n, ensure_ascii=False)), None)
    url = "file:" + pathname2url(str(ROOT / "out" / CH / "index.html")) + (f"#/step/{node['id']}" if node else "")
    edge = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    subprocess.Popen([edge if pathlib.Path(edge).exists() else "msedge", url]) if sys.platform == "win32" else print(url)
    print("Открыт шаг:", node["title_novice"] if node else "путь курса")


def main():
    if "--undo" in sys.argv:
        if not KEEP.exists():
            return print("Нечего возвращать: копии до показа нет.")
        shutil.rmtree(ANS)
        shutil.copytree(KEEP, ANS)
        shutil.rmtree(KEEP)
        print("Ответы возвращены, пересобираю.")
        rebuild()
        return
    old, new = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else (OLD, NEW)
    hits = [p for p in sorted(ANS.glob("*.json")) if old in p.read_text(encoding="utf-8")]
    if not hits:
        return print(f"«{old}» нет в ответах главы {CH}. Возьмите число, которое видно на странице шага.")
    if not KEEP.exists():
        shutil.copytree(ANS, KEEP)
    p = hits[0]
    text = p.read_text(encoding="utf-8")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"В учебном слое ({p.relative_to(ROOT)}): «{old}» -> «{new}»")
    rebuild()
    open_step(new)


if __name__ == "__main__":
    main()

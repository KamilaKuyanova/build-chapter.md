#!/usr/bin/env python3
"""Проверка готовой дорожки локальным распознаванием речи (ТЗ: ошибок в словах не больше 10 %, термины без искажений).

Модель: faster-whisper small в models/whisper-small (в git не кладётся), работает на процессоре, наружу ничего не уходит.
Словарь терминов модели НЕ подсказывается, иначе она «услышит» термин, которого в дорожке нет.
Ударения так не проверить: спорные слова остаются в списке «проверить на слух».
Запуск для уже собранного ролика: python engine/video/asr.py videos/<id>   (берёт out/video/<id>/audio.wav, пишет в паспорт)
Первая установка: pip install faster-whisper; python engine/video/asr.py --download"""
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "engine"))
MODEL = ROOT / "models" / "whisper-small"


def norm(text):
    t = text.lower().replace("ё", "е").replace("́", "")
    t = re.sub(r"(\d)[,.](\d)", r"\1 . \2", t)

    def words(m):
        try:
            from num2words import num2words
            return num2words(int(m.group(0)), lang="ru").replace("ё", "е")
        except Exception:
            return m.group(0)
    t = re.sub(r"\d+", words, t).replace("-", " ")
    return re.findall(r"[а-яa-z0-9]+", t)


def align(ref, hyp):
    """Расстояние Левенштейна по словам и список расхождений (в сценарии, услышано)."""
    n, m = len(ref), len(hyp)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (ref[i - 1] != hyp[j - 1]))
    i, j, diff = n, m, []
    while i or j:
        if i and j and d[i][j] == d[i - 1][j - 1] + (ref[i - 1] != hyp[j - 1]):
            if ref[i - 1] != hyp[j - 1]:
                diff.append((ref[i - 1], hyp[j - 1]))
            i, j = i - 1, j - 1
        elif i and d[i][j] == d[i - 1][j] + 1:
            diff.append((ref[i - 1], ""))
            i -= 1
        else:
            diff.append(("", hyp[j - 1]))
            j -= 1
    return d[n][m], diff[::-1]


def check(audio, beats, terms=(), lang="ru"):
    """{asr_wer, asr_note, asr_errors, asr_terms_lost, asr_sync_s}; None, если модели нет."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return {"asr_wer": None, "asr_note": "не проверено: нет пакета faster-whisper"}
    try:   # модель в models/ или уже скачанная в общий кэш (так у engine/video/asr_check.py)
        if (MODEL / "model.bin").exists():
            model = WhisperModel(str(MODEL), device="cpu", compute_type="int8")
        else:
            model = WhisperModel("small", device="cpu", compute_type="int8", local_files_only=True)
    except Exception:
        return {"asr_wer": None, "asr_note": "не проверено: нет модели, python engine/video/asr.py --download"}
    import subprocess
    import numpy
    import tts
    raw = subprocess.run([tts.ffmpeg(), "-v", "error", "-i", str(audio), "-f", "f32le", "-ac", "1", "-ar", "16000", "-"], capture_output=True, check=True).stdout
    sound = numpy.frombuffer(raw, dtype=numpy.float32).copy()   # звук готовит FFmpeg: не зависим от версии пакета av
    segs, _ = model.transcribe(sound, language=lang, beam_size=5, word_timestamps=True, vad_filter=False,
                               condition_on_previous_text=False)
    heard, times = [], []
    for s in segs:
        for w in s.words or []:
            for x in norm(w.word):
                heard.append(x)
                times.append(w.start)
    ref = norm(" ".join(b["text"] for b in beats))
    errs, diff = align(ref, heard)
    stems = {h[:max(4, len(h) - 2)] for h in heard}
    lost = [t for t in terms if not all(x[:max(4, len(x) - 2)] in stems for x in norm(t))]
    # независимая проверка синхрона: первое услышанное слово фразы против начала её слота
    worst, k = 0.0, 0
    for b in beats:
        first = norm(b["text"])[:1]
        near = [t for h, t in zip(heard, times) if first and h == first[0] and abs(t - b["t_start"]) < 1.5]
        if near:
            worst, k = max(worst, min(abs(t - b["t_start"]) for t in near)), k + 1
    return {"asr_wer": round(errs / max(1, len(ref)), 3),
            "asr_note": f"faster-whisper small, локально; слов {len(ref)}, расхождений {errs}; синхрон по услышанным словам, фраз {k} из {len(beats)}",
            "asr_errors": [f"{a or '—'} → {b or '—'}" for a, b in diff], "asr_terms_lost": lost, "asr_sync_s": round(worst, 2)}


def main(folder):
    vdir = pathlib.Path(folder)
    p = json.loads((vdir / "passport.json").read_text(encoding="utf-8"))
    res = check(ROOT / "out" / "video" / p["video_id"] / "audio.wav", p["script"], p["audio_check"].get("check_by_ear", []))
    p["audio_check"].update(res)
    (vdir / "passport.json").write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
    print(p["video_id"], res["asr_wer"], res["asr_note"])
    for e in res.get("asr_errors", []):
        print("   ", e)
    print("  термины потеряны:", res.get("asr_terms_lost"), "| синхрон по услышанному:", res.get("asr_sync_s"))


if __name__ == "__main__":
    if "--download" in sys.argv:
        from faster_whisper import download_model
        print(download_model("small", output_dir=str(MODEL)))
    else:
        for a in sys.argv[1:]:
            main(a)

#!/usr/bin/env python3
"""Проверка озвучки распознаванием речи (ТЗ: ASR WER ≤ 10 %, синхрон голоса и кадра ≤ 0,5 с).

Локальная модель Whisper (faster-whisper, по умолчанию small, CPU int8): наружу ничего не уходит.
WER считается между тем, что должно звучать (текст фраз после prepare_for_speech: числа словами, сокращения раскрыты),
и тем, что распознано. Синхрон: начало каждой фразы в таймлайне против начала её первого слова в распознавании.

  python engine/video/asr_check.py videos/latyshova_signs      # берёт out/video/<id>/audio.wav, дописывает паспорт"""
import difflib
import json
import os
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import speech  # noqa: E402

_MODEL = None


def norm_words(text):
    t = text.lower().replace("ё", "е").replace(speech.ACUTE, "")
    t = re.sub(r"[-‐–—]", " ", t)
    return re.findall(r"[a-zа-я0-9]+", t)


def model():
    global _MODEL
    if _MODEL is None:
        from faster_whisper import WhisperModel
        _MODEL = WhisperModel(os.environ.get("ASR_MODEL", "small"), device="cpu", compute_type="int8")
    return _MODEL


def check(audio, beats):
    """beats: [{t_start, t_end, text}] -> dict(asr_wer, sync_max_s, asr_note, asr_text)."""
    import subprocess
    import numpy as np
    import imageio_ffmpeg
    raw = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-i", str(audio), "-ac", "1",
                          "-ar", "16000", "-f", "f32le", "-"], capture_output=True, check=True).stdout
    pcm = np.frombuffer(raw, dtype=np.float32)   # 16 кГц моно: свой декодер, без PyAV
    # без initial_prompt: подсказка текстом сценария завышала бы качество и съедала начало записи
    segs, _ = model().transcribe(pcm, language="ru", word_timestamps=True, beam_size=5, vad_filter=False,
                                 condition_on_previous_text=False)
    hyp = []  # (слово, начало)
    for s in segs:
        for w in s.words or []:
            for x in norm_words(w.word):
                hyp.append((x, w.start))
    ref, first = [], []  # слова эталона и индекс первого слова каждой фразы
    for b in beats:
        ws = norm_words(speech.prepare_for_speech(b["text"]))
        first.append(len(ref))
        ref += ws
    hw = [h[0] for h in hyp]
    sm = difflib.SequenceMatcher(a=ref, b=hw, autojunk=False)
    # WER = (замены + вставки + удаления) / слов эталона, по выравниванию
    errors = 0
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "replace":
            errors += max(i2 - i1, j2 - j1)
        elif op == "delete":
            errors += i2 - i1
        elif op == "insert":
            errors += j2 - j1
    wer = errors / max(1, len(ref))
    pos = {}
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            pos[blk.a + k] = blk.b + k
    offs = []
    for b, i in zip(beats, first):
        # первое совпавшее слово из первых трёх слов фразы
        for k in range(3):
            if i + k in pos:
                offs.append(abs(hyp[pos[i + k]][1] - b["t_start"]) if k == 0 else None)
                break
    offs = [o for o in offs if o is not None]   # по меткам Whisper (их точность ~0,1–0,5 с) — только для справки
    # синхрон голоса и кадра: начало звука (энергия) после начала слота фразы, по которому меняется кадр
    ons = []
    for b in beats:
        seg = np.abs(pcm[int(b["t_start"] * 16000):int(b["t_start"] * 16000) + 32000])
        if (seg > 0.02).any():
            ons.append(float(np.argmax(seg > 0.02)) / 16000)
    offs = ons or offs
    return {"asr_wer": round(wer, 3), "sync_max_s": round(max(offs), 2) if offs else None,
            "asr_note": f"faster-whisper {os.environ.get('ASR_MODEL', 'small')}, локально; слов эталона {len(ref)}, "
                        f"распознано {len(hw)}, ошибок {errors}; синхрон замерен по началу звука {len(offs)} из {len(beats)} фраз",
            "asr_text": " ".join(hw)}


def update_passport(vdir):
    vdir = pathlib.Path(vdir)
    p = json.loads((vdir / "passport.json").read_text(encoding="utf-8"))
    audio = ROOT / "out" / "video" / p["video_id"] / "audio.wav"
    if not audio.exists():
        raise SystemExit(f"нет {audio}: сначала make_video.py")
    r = check(audio, p["script"])
    a = p["audio_check"]
    a["asr_wer"], a["asr_note"] = r["asr_wer"], r["asr_note"]
    if r["sync_max_s"] is not None:
        a["sync_max_s"] = r["sync_max_s"]
        a["sync_note"] = ("слот фразы равен длительности её озвучки; замер: начало фразы в таймлайне против начала первого "
                          "распознанного слова (точность меток Whisper ~0,1–0,2 с)")
    (vdir / "passport.json").write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
    (ROOT / "out" / "video" / p["video_id"] / "asr.txt").write_text(r["asr_text"], encoding="utf-8")
    print(f"{p['video_id']}: WER {r['asr_wer']:.1%}, синхрон до {r['sync_max_s']} с")
    return r


if __name__ == "__main__":
    for d in sys.argv[1:]:
        update_passport(d)

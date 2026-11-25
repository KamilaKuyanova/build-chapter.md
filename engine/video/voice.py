#!/usr/bin/env python3
"""Озвучка голосами Microsoft (edge-tts): наружу уходит ТОЛЬКО текст сценария (требование ТЗ), главы — нет.
Запасной голос включается автоматически при отказе основного (бесплатный онлайн-синтез ограничивает частоту запросов).
Выход: <out>/phrase_NNN.mp3 и timings.json (реальная длительность фразы по меткам слов) — для проверки синхрона ≤0.5 с.
Запуск: python engine/video/voice.py passport.json [--out out/voice] [--voice ru-RU-DmitryNeural] [--fallback ru-RU-SvetlanaNeural]
"""
import argparse
import asyncio
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import speech  # noqa: E402


async def _one(text, voice, mp3, rate):
    import edge_tts
    com = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    end = 0.0
    with open(mp3, "wb") as f:
        async for ch in com.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                end = max(end, (ch["offset"] + ch["duration"]) / 1e7)  # 100 нс → с
    return end


def synth(script, out, voice, fallback, rate="+0%", retries=2):
    out = pathlib.Path(out)
    out.mkdir(parents=True, exist_ok=True)
    timings = []
    for i, p in enumerate(script):
        text = speech.prepare_for_speech(p["text"])
        mp3, used, dur, last = out / f"phrase_{i:03d}.mp3", voice, None, None
        for v in [voice] * (retries + 1) + [fallback]:
            try:
                dur, used = asyncio.run(_one(text, v, mp3, rate)), v
                break
            except Exception as e:  # сеть, лимиты запросов, голос недоступен
                last = e
        if dur is None:
            raise RuntimeError(f"фраза {i}: синтез не удался ни основным, ни запасным голосом: {last}")
        slot = p["t_end"] - p["t_start"]
        timings.append({"i": i, "voice": used, "audio_sec": round(dur, 2), "slot_sec": round(slot, 2),
                        "overrun_sec": round(max(0.0, dur - slot), 2)})
    (out / "timings.json").write_text(json.dumps(timings, ensure_ascii=False, indent=1), encoding="utf-8")
    return timings


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("passport")
    ap.add_argument("--out", default="out/voice")
    ap.add_argument("--voice", default="ru-RU-DmitryNeural")
    ap.add_argument("--fallback", default="ru-RU-SvetlanaNeural")
    a = ap.parse_args()
    pp = json.loads(pathlib.Path(a.passport).read_text(encoding="utf-8-sig"))
    tm = synth(pp["script"], a.out, a.voice, a.fallback)
    bad = [t for t in tm if t["overrun_sec"] > 0.5]
    print(f"Озвучено фраз: {len(tm)}; выходят за слот более чем на 0,5 с: {len(bad)}")
    for t in bad:
        print(f"  ! фраза {t['i']}: речь {t['audio_sec']} с в слоте {t['slot_sec']} с — сократите текст или расширьте слот")
    sys.exit(2 if bad else 0)

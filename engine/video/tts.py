#!/usr/bin/env python3
"""Озвучка с заменяемым голосом. По ответу организаторов голос Microsoft не обязателен: это только базовый уровень.

Голоса перечислены по порядку в video.json: "voices": [{"engine": ..., "voice": ..., "rate": ...}, ...]; берётся первый,
который сработал для ВСЕХ фраз (один голос на ролик). Общий порядок для серии: domain_pack/voices.json.
Движки:
  piper       открытый локальный голос: команда piper или python -m piper, voice — путь к модели .onnx (или имя в models/voices)
  elevenlabs  облако, ключ в переменной ELEVENLABS_API_KEY, voice — id голоса; наружу уходит только текст фразы
  winrt       голос Windows (Microsoft Pavel, Irina), локально, с метками слов; установки не требует
  sapi        старый голос Windows (System.Speech), последний запасной путь
synth(phrases, out, voices) -> {"engine", "voice", "wavs": [...], "words": [[{t, w}]] или None, "tried": [...]}"""
import base64
import json
import os
import pathlib
import shutil
import subprocess
import sys
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def ffmpeg():
    """FFmpeg из PATH, из установки winget или из пакета imageio-ffmpeg."""
    if shutil.which("ffmpeg"):
        return shutil.which("ffmpeg")
    base = pathlib.Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    for p in sorted(base.glob("Gyan.FFmpeg*/ffmpeg-*/bin/ffmpeg.exe")):
        return str(p)
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def _run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout)[-400:])
    return r.stdout


def _wav(src, dst):
    _run([ffmpeg(), "-y", "-hide_banner", "-loglevel", "error", "-i", str(src), "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", str(dst)])


def winrt(phrases, out, voice, rate=1.0):
    job = out / "winrt_job.json"
    job.write_text(json.dumps({"voice": voice, "fallback": voice, "rate": rate, "phrases": phrases, "out": str(out)},
                              ensure_ascii=False), encoding="utf-8")
    _run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(HERE / "winrt_voice.ps1"), "-Job", str(job)])
    words = json.loads((out / "words.json").read_text(encoding="utf-8-sig"))["words"]
    for i in range(len(phrases)):
        p = out / f"phrase_{i:03d}.wav"
        _wav(p, p.with_suffix(".tmp.wav"))
        p.with_suffix(".tmp.wav").replace(p)
    return words


def piper(phrases, out, voice, rate=1.0):
    model = pathlib.Path(voice)
    if not model.exists():
        model = ROOT / "models" / "voices" / (voice if voice.endswith(".onnx") else voice + ".onnx")
    if not model.exists():
        raise RuntimeError(f"нет модели голоса {model}")
    cmd = [shutil.which("piper")] if shutil.which("piper") else [sys.executable, "-m", "piper"]
    for i, txt in enumerate(phrases):
        raw = out / f"phrase_{i:03d}.raw.wav"
        _run(cmd + ["--model", str(model), "--length-scale", f"{1 / rate:.3f}", "--output_file", str(raw)], input=txt)
        _wav(raw, out / f"phrase_{i:03d}.wav")
    return None


def elevenlabs(phrases, out, voice, rate=1.0):
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise RuntimeError("нет ELEVENLABS_API_KEY")
    words = []
    for i, txt in enumerate(phrases):
        body = json.dumps({"text": txt, "model_id": "eleven_multilingual_v2",
                           "voice_settings": {"stability": 0.55, "similarity_boost": 0.8, "speed": rate}}).encode()
        req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps", body,
                                     {"xi-api-key": key, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            d = json.loads(r.read())
        mp3 = out / f"phrase_{i:03d}.mp3"
        mp3.write_bytes(base64.b64decode(d["audio_base64"]))
        _wav(mp3, out / f"phrase_{i:03d}.wav")
        al, cur, t0, row = d["alignment"], "", 0.0, []
        for ch, st in zip(al["characters"] + [" "], al["character_start_times_seconds"] + [0]):
            if ch.isalnum():
                t0, cur = (st if not cur else t0), cur + ch
            elif cur:
                row.append({"t": t0, "w": cur})
                cur = ""
        words.append(row)
    return words


def sapi(phrases, out, voice, rate=1.0):
    lines = ["Add-Type -AssemblyName System.Speech", "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer",
             f"$s.SelectVoice('{voice}')", f"$s.Rate = {round((rate - 1) * 10)}"]
    for i, txt in enumerate(phrases):
        lines += [f"$s.SetOutputToWaveFile('{out / f'phrase_{i:03d}.raw.wav'}')", "$s.Speak('" + txt.replace("'", "''") + "')"]
    lines += ["$s.SetOutputToNull()", "$s.Dispose()"]
    ps1 = out / "sapi.ps1"
    ps1.write_text("\n".join(lines), encoding="utf-8-sig")
    _run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1)])
    for i in range(len(phrases)):
        _wav(out / f"phrase_{i:03d}.raw.wav", out / f"phrase_{i:03d}.wav")
    return None


ENGINES = {"winrt": winrt, "piper": piper, "elevenlabs": elevenlabs, "sapi": sapi}
WHERE = {"winrt": "локально, Windows", "sapi": "локально, Windows", "piper": "локально, открытая модель",
         "elevenlabs": "облако, наружу уходит только текст сценария"}


def synth(phrases, out, voices):
    out = pathlib.Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    tried = []
    for v in voices:
        for old in out.glob("phrase_*"):
            old.unlink()
        try:
            words = ENGINES[v["engine"]](phrases, out, v["voice"], float(v.get("rate", 1.0)))
            return {"engine": v["engine"], "voice": v["voice"], "where": WHERE[v["engine"]], "words": words, "tried": tried,
                    "wavs": [out / f"phrase_{i:03d}.wav" for i in range(len(phrases))]}
        except Exception as e:  # нет программы, ключа, сети, модели — следующий голос
            tried.append(f"{v['engine']} {v['voice']}: {str(e).strip()[-160:]}")
    raise RuntimeError("не сработал ни один голос:\n" + "\n".join(tried))

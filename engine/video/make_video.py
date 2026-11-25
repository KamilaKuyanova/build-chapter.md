#!/usr/bin/env python3
"""Сборка ролика одной командой (часть Б): сценарий -> озвучка -> таймлайн -> кадры -> звук -16 LUFS -> mp4 + паспорт.

Вход: videos/<id>/video.json (сценарий со ссылками на утверждения слоя и «битами» сцены).
Выход: out/video/<id>/video.mp4 (отключаемые субтитры — отдельная дорожка), subtitles.srt, кадр-превью;
       videos/<id>/passport.json (официальная passport.schema) и scene_spec.json.
Голос: локальный Microsoft (Windows, SAPI) — наружу ничего не уходит; запасной голос из спецификации.
Синхрон по построению: слот фразы = длительность её озвучки, кадр берёт состояние из того же таймлайна.
Запуск: python engine/video/make_video.py videos/latyshova_short [--fps 24] [--preview]"""
import argparse
import array
import json
import math
import pathlib
import re
import subprocess
import sys
import wave

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "engine"))
import speech  # noqa: E402


def ffmpeg():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def sapi_synth(phrases, out_dir, voice, fallback, rate):
    """Озвучка локальным голосом Microsoft через System.Speech; возвращает (пути wav, использованный голос)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = ["Add-Type -AssemblyName System.Speech",
             "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer",
             "$names = $s.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name }",
             f"$v = if ($names -contains '{voice}') {{ '{voice}' }} else {{ '{fallback}' }}",
             "$s.SelectVoice($v)", f"$s.Rate = {rate}", "Write-Output $v"]
    paths = []
    for i, txt in enumerate(phrases):
        p = out_dir / f"phrase_{i:03d}.wav"
        paths.append(p)
        safe = txt.replace("'", "''")
        lines += [f"$s.SetOutputToWaveFile('{p}')", f"$s.Speak('{safe}')"]
    lines += ["$s.SetOutputToNull()", "$s.Dispose()"]
    ps1 = out_dir / "synth.ps1"
    ps1.write_text("\n".join(lines), encoding="utf-8-sig")
    import shutil
    shell = shutil.which("pwsh") or "powershell"  # в PowerShell 7 видны голоса OneCore (Pavel), в 5.1 — нет
    r = subprocess.run([shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("синтез речи не удался: " + r.stderr[-500:])
    return paths, (r.stdout.strip().splitlines() or [voice])[-1]


def speech_len(path, thr=500):
    """Длительность речи без хвостовой тишины, с."""
    with wave.open(str(path)) as w:
        sr, n, sw = w.getframerate(), w.getnframes(), w.getsampwidth()
        data = array.array("h", w.readframes(n)) if sw == 2 else None
    if data is None:
        return n / sr
    last = len(data) - 1
    while last > 0 and abs(data[last]) < thr:
        last -= 1
    return (last + 1) / sr + 0.05


def measure_lufs(path):
    r = subprocess.run([ffmpeg(), "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    m = re.findall(r"I:\s+(-?\d+(?:\.\d+)?)\s+LUFS", r.stderr)
    return float(m[-1]) if m else None


def build_audio(wavs, starts, total, out):
    ins, fl = [], []
    for i, (w, st) in enumerate(zip(wavs, starts)):
        ins += ["-i", str(w)]
        fl.append(f"[{i}:a]aresample=48000,adelay=delays={int(st * 1000)}:all=1[a{i}]")
    mix = "".join(f"[a{i}]" for i in range(len(wavs)))
    fl.append(f"{mix}amix=inputs={len(wavs)}:normalize=0,apad=whole_dur={total:.2f},atrim=0:{total:.2f},"
              f"loudnorm=I=-16:TP=-1.5:LRA=11[out]")
    cmd = [ffmpeg(), "-y", "-hide_banner", "-loglevel", "error"] + ins + ["-filter_complex", ";".join(fl), "-map", "[out]",
                                                                         "-ar", "48000", "-ac", "1", str(out)]
    subprocess.run(cmd, check=True)


def layer_claims(chapter):
    ly = json.loads((ROOT / "data" / chapter / "layer.json").read_text(encoding="utf-8-sig"))
    nodes = {n["id"]: n for n in ly["nodes"]}
    claims = {c["id"]: c for n in ly["nodes"] for c in n["claims"]}
    return nodes, claims


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--preview", action="store_true", help="только кадры-превью, без видео")
    a = ap.parse_args()
    vdir = pathlib.Path(a.dir)
    spec = json.loads((vdir / "video.json").read_text(encoding="utf-8"))
    out = ROOT / "out" / "video" / spec["video_id"]
    out.mkdir(parents=True, exist_ok=True)
    nodes, claims = layer_claims(spec["chapter"])
    for ph in spec["script"]:
        if ph.get("claim_id") and ph["claim_id"] not in claims:
            raise SystemExit(f"утверждение {ph['claim_id']} нет в слое {spec['chapter']}")
    scene = __import__(spec["scene"])

    # 1. озвучка
    texts = [speech.prepare_for_speech(p["text"]).replace(speech.ACUTE, "") for p in spec["script"]]
    wavs, used_voice = sapi_synth(texts, out / "voice", spec["voice"], spec["fallback_voice"], spec.get("rate", 1))
    lens = [speech_len(w) for w in wavs]

    # 2. таймлайн из длительностей озвучки (синхрон по построению)
    beats, cur = [], spec.get("lead", 0.2)
    for i, (ph, ln) in enumerate(zip(spec["script"], lens)):
        b = dict(ph, t_start=round(cur, 2), t_end=round(cur + ln, 2))
        beats.append(b)
        cur += ln + (spec.get("pause_prediction", 1.4) if ph.get("prediction") else spec.get("gap", 0.35))
    total = cur + spec.get("hold_end", 2.0)
    starts = [b["t_start"] for b in beats]

    # 3. звук: сведение, нормализация до -16 LUFS, замер
    audio = out / "audio.wav"
    build_audio(wavs, starts, total, audio)
    lufs = measure_lufs(audio)
    if lufs is not None and abs(lufs + 16) > 0.3:  # второй проход: точная подгонка к -16 LUFS без клиппинга
        tmp = out / "audio_raw.wav"
        audio.replace(tmp)
        subprocess.run([ffmpeg(), "-y", "-hide_banner", "-loglevel", "error", "-i", str(tmp), "-af",
                        f"volume={-16 - lufs:.2f}dB,alimiter=limit=0.89:level=disabled", "-ar", "48000", str(audio)], check=True)
        lufs = measure_lufs(audio)

    # 4. субтитры (полный текст голоса, отдельная дорожка)
    srt = out / "subtitles.srt"
    srt_text = speech.subtitles_srt([{"t_start": b["t_start"], "t_end": b["t_end"], "text": b["text"]} for b in beats])
    srt.write_text(srt_text, encoding="utf-8")
    # WebVTT для курса (браузер показывает отключаемые субтитры через <track>)
    (out / "video.vtt").write_text("WEBVTT\n\n" + re.sub(r"(\d{2}:\d{2}:\d{2}),(\d{3})", r"\1.\2", srt_text), encoding="utf-8")

    # 5. кадры -> видео
    W, H = scene.W, scene.H
    previews = [beats[k]["t_start"] + 0.8 * (beats[k]["t_end"] - beats[k]["t_start"]) for k in range(len(beats))]
    for k, tp in enumerate(previews):
        if k % 3 == 0 or k == len(previews) - 1:
            scene.render(tp, beats).save(out / f"preview_{k:02d}.png")
    if not a.preview:
        cmd = [ffmpeg(), "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
               "-r", str(a.fps), "-i", "-", "-i", str(audio), "-i", str(srt), "-map", "0:v", "-map", "1:a", "-map", "2:s",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
               "-c:s", "mov_text", "-metadata:s:s:0", "language=rus", "-t", f"{total:.2f}", str(out / "video.mp4")]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        n = int(math.ceil(total * a.fps))
        for i in range(n):
            proc.stdin.write(scene.render(i / a.fps, beats).tobytes())
        proc.stdin.close()
        if proc.wait() != 0:
            raise SystemExit("ffmpeg не собрал видео")

    # 6. паспорт (официальная схема) + спецификация сцены
    (vdir / "scene_spec.json").write_text(json.dumps(scene.SPEC, ensure_ascii=False, indent=1), encoding="utf-8")
    node = nodes[spec["node_id"]]
    used = sorted({b["claim_id"] for b in beats if b.get("claim_id")})
    pcs = json.loads((ROOT / "domain_pack" / "physics_checklist.json").read_text(encoding="utf-8"))
    script = [{k: v for k, v in b.items() if k in ("t_start", "t_end", "text", "claim_id", "is_analogy", "on_screen")}
              for b in beats]
    for s in script:
        s.setdefault("claim_id", None)
    passport = {
        "video_id": spec["video_id"], "node_id": spec["node_id"], "format": spec["format"],
        "node_card": {"id": node["id"], "title": node["title"], "title_novice": node.get("title_novice"),
                      "main": node["layers"]["main"]["text"], "chapter": spec["chapter"]},
        "script": script,
        "sources": [{"claim_id": c, "page_or_dataset": f"стр. {claims[c]['page_pdf']}", "quote": claims[c]["quote"]} for c in used],
        "scene_spec": f"videos/{spec['video_id']}/scene_spec.json",
        "frames": [{"t": b["t_start"], "class": scene.SPEC["frame_class"], "label": scene.SPEC["label"]} for b in beats],
        "exaggerations": spec["exaggerations"],
        "prediction_question": spec["prediction_question"], "transfer_question": spec["transfer_question"],
        "data_it_bridge": spec["data_it_bridge"],
        "physics_checklist": [{"item": p["id"], "answer": (spec["physics"].get(p["id"]) or ["н/п"])[0],
                               "note": (spec["physics"].get(p["id"]) or ["н/п", "к сцене не относится"])[-1]} for p in pcs],
        "audio_check": {"voice": used_voice + " (локально, Windows)", "fallback_voice": spec["fallback_voice"],
                        "wpm": round(speech.wpm(beats), 1), "lufs": lufs, "sync_max_s": 0.0,
                        "sync_note": "слот фразы равен длительности её озвучки; кадр берёт состояние из того же таймлайна",
                        "asr_wer": None, "asr_note": "распознавание речи локальной моделью ещё не подключено",
                        "check_by_ear": spec.get("check_by_ear", [])},
        "duration_sec": round(total, 1),
    }
    (vdir / "passport.json").write_text(json.dumps(passport, ensure_ascii=False, indent=1), encoding="utf-8")
    # 7. ролик в курс: mp4 + субтитры в data/<глава>/media, запись для illustrations.json (gen_illustrations --extra)
    if not a.preview:
        import shutil
        media = ROOT / "data" / spec["chapter"] / "media"
        media.mkdir(exist_ok=True)
        shutil.copyfile(out / "video.mp4", media / f"{spec['video_id']}.mp4")
        shutil.copyfile(out / "video.vtt", media / f"{spec['video_id']}.vtt")
        ex_path = ROOT / "data" / spec["chapter"] / "media_extra.json"
        extra = json.loads(ex_path.read_text(encoding="utf-8")) if ex_path.exists() else {}
        fmt_ru = "шортс 9:16" if spec["format"] == "short" else "разбор 16:9"
        extra[spec["node_id"]] = [{
            "id": f"{spec['node_id']}.video", "file": f"media/{spec['video_id']}.mp4", "frame_class": scene.SPEC["frame_class"],
            "origin": "code_from_model", "label": scene.SPEC["label"],
            "caption": f"Ролик ({fmt_ru}, {total:.0f} с): {spec['prediction_question']}",
            "alt": spec.get("alt", f"Ролик {fmt_ru} по шагу; субтитры включаются в плеере"),
            "source": f"паспорт: videos/{spec['video_id']}/passport.json", "claim_ids": used, "prompt": None}]
        ex_path.write_text(json.dumps(extra, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{spec['video_id']}: {total:.1f} с, фраз {len(beats)}, голос {used_voice}, громкость {lufs} LUFS, "
          f"темп {passport['audio_check']['wpm']} слов/мин -> {out}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Список голосов ElevenLabs (чтобы выбрать один голос на всю серию роликов). Ключ — ELEVENLABS_API_KEY.
Запуск: python engine/video/elevenlabs_voices.py
Затем в videos/<ролик>/video.json: "voice": "elevenlabs:<voice_id>" (одинаковый во всех роликах серии)."""
import json
import os
import sys
import urllib.request

key = os.environ.get("ELEVENLABS_API_KEY")
if not key:
    sys.exit("не задан ELEVENLABS_API_KEY")
req = urllib.request.Request("https://api.elevenlabs.io/v1/voices", headers={"xi-api-key": key})
with urllib.request.urlopen(req, timeout=60) as r:
    voices = json.loads(r.read().decode("utf-8")).get("voices", [])
for v in voices:
    labels = v.get("labels") or {}
    print(f"{v['voice_id']}  {v.get('name')}  ({labels.get('gender', '')}, {labels.get('accent', '')}, {labels.get('language', '')})")

#!/usr/bin/env python3
"""Клиент ЛОКАЛЬНОЙ модели через Ollama (http://localhost:11434). Только stdlib. Данные наружу не уходят.

Особенности по ТЗ:
- модель и версия записываются в manifest.json (скрипт `python engine/llm_client.py --manifest`);
- ответ ограничивается JSON-схемой (structured output), чтобы малая модель не ломала формат;
- модель заменяема: имя берётся из LLM_MODEL (по умолчанию qwen3:8b), конвейер не привязан к поставщику.
"""
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
MODEL = os.environ.get("LLM_MODEL", "qwen3:8b")


class LLMError(RuntimeError):
    pass


def _post(path, payload, timeout=1800):
    req = urllib.request.Request(HOST + path, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise LLMError(f"Ollama недоступна на {HOST}: {e}. Установлена и запущена? `ollama list`")


def available_models():
    try:
        with urllib.request.urlopen(HOST + "/api/tags", timeout=5) as r:
            return [m["name"] for m in json.loads(r.read().decode("utf-8")).get("models", [])]
    except Exception:
        return None


def generate_json(prompt, schema=None, system=None, model=None, temperature=0.1, retries=2):
    """Возвращает dict, строго разобранный из ответа. Повторяет при невалидном JSON."""
    last = None
    for attempt in range(retries + 1):
        payload = {"model": model or MODEL, "prompt": prompt, "stream": False,
                   "format": schema or "json",
                   "options": {"temperature": temperature, "seed": 7, "num_ctx": 8192}}
        if system:
            payload["system"] = system
        out = _post("/api/generate", payload)
        txt = out.get("response", "")
        try:
            return json.loads(txt)
        except json.JSONDecodeError as e:
            last = f"{e}: {txt[:200]}"
    raise LLMError("модель не вернула валидный JSON: " + str(last))


def write_manifest_entry():
    models = available_models()
    if models is None:
        print("Ollama не запущена: манифест не обновлён.")
        return 1
    mp = ROOT / "manifest.json"
    m = json.loads(mp.read_text(encoding="utf-8"))
    m["models"] = [{"name": MODEL, "runtime": "Ollama (локально)", "role": "извлечение узлов учебного слоя",
                    "external_data": False, "installed": MODEL in models}]
    mp.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    print("manifest.json обновлён:", MODEL, "установлена" if MODEL in models else "НЕ установлена")
    return 0


if __name__ == "__main__":
    if "--manifest" in sys.argv:
        sys.exit(write_manifest_entry())
    ms = available_models()
    print("Ollama:", "не отвечает" if ms is None else f"модели: {ms}")

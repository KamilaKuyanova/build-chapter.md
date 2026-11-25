#!/usr/bin/env python3
"""Клиент Claude (официальный SDK `anthropic`) для конвейера. Единственный бэкенд модели в проекте.

ВАЖНО по ТЗ:
- Текст главы уходит во внешний сервис Anthropic. Это записано в manifest.json (external_data=true).
  Главы и ролики не публикуются: никаких общих ссылок; ключ API в репозиторий не кладём.
- Ключ берётся из переменной окружения ANTHROPIC_API_KEY (или профиля `ant auth login`).
- Модель заменяема: LLM_MODEL (по умолчанию claude-opus-5-5). Версия фиксируется в теге заморозки.

Установка:  pip install anthropic
Проверка:   python engine/llm_client.py --ping      (один короткий платный запрос)
Манифест:   python engine/llm_client.py --manifest
"""
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
MODEL = os.environ.get("LLM_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("LLM_EFFORT", "high")  # low | medium | high | xhigh | max
# Серверный запасной вариант при отказе классификаторов безопасности (рекомендация справочника для Opus 5.5).
# Пустое значение отключает.
FALLBACK_MODEL = os.environ.get("LLM_FALLBACK_MODEL", "claude-opus-4-8")
MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", "32000"))


class LLMError(RuntimeError):
    pass


def _client():
    try:
        import anthropic
    except ImportError:
        raise LLMError("Не установлен SDK: выполните  pip install anthropic")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        # SDK умеет брать учётные данные и из профиля `ant auth login`; предупреждаем, но не блокируем.
        print("  (ANTHROPIC_API_KEY не задан; используем другие учётные данные SDK, если они есть)", file=sys.stderr)
    return anthropic.Anthropic()


def generate_json(prompt, schema, system=None, model=None, max_tokens=None):
    """Один запрос -> dict, строго по JSON-схеме (structured outputs). Стриминг: ответы могут быть длинными."""
    import anthropic
    client = _client()
    kwargs = dict(
        model=model or MODEL,
        max_tokens=max_tokens or MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
        output_config={"effort": EFFORT, "format": {"type": "json_schema", "schema": schema}},
    )
    if system:
        kwargs["system"] = system
    try:
        if FALLBACK_MODEL and (model or MODEL).startswith("claude-opus-5-5"):
            stream_cm = client.beta.messages.stream(
                betas=["server-side-fallback-2026-07-01"], fallbacks=[{"model": FALLBACK_MODEL}], **kwargs)
        else:
            stream_cm = client.messages.stream(**kwargs)
        with stream_cm as stream:
            msg = stream.get_final_message()
    except anthropic.RateLimitError as e:
        raise LLMError(f"лимит запросов (429): {e}")
    except anthropic.APIConnectionError as e:
        raise LLMError(f"нет связи с API: {e}")
    except anthropic.APIStatusError as e:
        raise LLMError(f"ошибка API {e.status_code}: {e}")
    if msg.stop_reason == "refusal":
        cat = getattr(getattr(msg, "stop_details", None), "category", None)
        raise LLMError(f"модель отказалась отвечать (refusal, категория {cat})")
    if msg.stop_reason == "max_tokens":
        raise LLMError("ответ обрезан по max_tokens: уменьшите порцию текста или поднимите LLM_MAX_TOKENS")
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise LLMError(f"невалидный JSON от модели: {e}: {text[:200]}")


def write_manifest_entry():
    mp = ROOT / "manifest.json"
    m = json.loads(mp.read_text(encoding="utf-8"))
    m["models"] = [{
        "name": MODEL, "provider": "Anthropic (Claude API)", "role": "извлечение узлов учебного слоя, задания, сценарии",
        "external_data": True,
        "data_sent": "текст единиц главы (без публикации; ключ API не хранится в репозитории)",
        "fallback_model": FALLBACK_MODEL or None, "effort": EFFORT,
    }]
    m["policy"] = [p for p in m.get("policy", []) if "локаль" not in p.lower()]
    mp.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    print("manifest.json обновлён:", MODEL)
    return 0


if __name__ == "__main__":
    if "--manifest" in sys.argv:
        sys.exit(write_manifest_entry())
    if "--ping" in sys.argv:
        r = generate_json("Верни JSON с полем ok=true.", {"type": "object", "properties": {"ok": {"type": "boolean"}},
                                                          "required": ["ok"], "additionalProperties": False}, max_tokens=2000)
        print("Ответ модели:", r)
        sys.exit(0)
    print(__doc__)

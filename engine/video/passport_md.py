#!/usr/bin/env python3
"""Паспорт ролика в читаемом виде для ментора и жюри: videos/<id>/passport.json -> videos/<id>/passport.md.
Запуск: python engine/video/passport_md.py videos/latyshova_signs"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]


def esc(s):
    return str(s if s is not None else "—").replace("|", "\\|").replace("\n", " ")


def main(d):
    d = pathlib.Path(d)
    p = json.loads((d / "passport.json").read_text(encoding="utf-8"))
    spec = json.loads((ROOT / p["scene_spec"]).read_text(encoding="utf-8")) if (ROOT / p["scene_spec"]).exists() else {}
    src = {s["claim_id"]: s for s in p["sources"]}
    fmt = "шортс 9:16" if p.get("format") == "short" else "разбор 16:9"
    a = p["audio_check"]
    L = [f"# Паспорт ролика `{p['video_id']}` ({fmt}, {p.get('duration_sec', '?')} с)", "",
         f"**Узел:** {esc(p['node_card'].get('title_novice') or p['node_card']['title'])} (`{p['node_id']}`), глава {p['node_card'].get('chapter')}",
         f"**Суть узла:** {esc(p['node_card'].get('main'))}", "",
         "## Что проверить ментору до рендера",
         "1. Физика: каждая строка чек-листа ниже («да» / «н/п» с пояснением); кадры против спецификации сцены.",
         "2. Каждая фраза закадра опирается на утверждение главы (страница и цитата в таблице).",
         "3. Ударения на слух в словах: " + (", ".join(a.get("check_by_ear", [])) or "—"), "",
         "## Сценарий с таймкодами", "", "| Время, с | Фраза закадра | На экране | Опора (утверждение, стр.) |", "| --- | --- | --- | --- |"]
    for s in p["script"]:
        c = s.get("claim_id")
        ref = "аналогия" if s.get("is_analogy") else (f"`{c}`, {src[c]['page_or_dataset']}" if c in src else esc(c))
        L.append(f"| {s['t_start']:.1f}–{s['t_end']:.1f} | {esc(s['text'])} | {esc(s.get('on_screen'))} | {ref} |")
    L += ["", "## Таблица источников", "", "| Утверждение | Страница | Цитата автора |", "| --- | --- | --- |"]
    L += [f"| `{s['claim_id']}` | {esc(s['page_or_dataset'])} | «{esc(s.get('quote'))}» |" for s in p["sources"]]
    L += ["", "## Спецификация сцены", "", f"- **Шаблон:** {esc(spec.get('template') or spec.get('scene'))}; "
          f"модель состояния: {esc(spec.get('state_model'))}",
          f"- **Класс кадров:** {esc(spec.get('frame_class'))}, метка «{esc(spec.get('label'))}», как сделано: {esc(spec.get('origin'))}"]
    L += ["- **Объекты:** " + "; ".join(esc(o) for o in spec.get("objects", []))]
    L += ["- **Инварианты:**"] + [f"  - {esc(i)}" for i in spec.get("invariants", [])]
    L += ["- **Допущения:**"] + [f"  - {esc(i)}" for i in spec.get("assumptions", [])]
    if p.get("references"):
        L += ["- **Референсы:**"] + [f"  - {esc(i)}" for i in p["references"]]
    L += ["", "## Честность", "", "**Преувеличения:** " + "; ".join(esc(x) for x in p["exaggerations"]),
          "", f"**Вопрос-предсказание:** {esc(p['prediction_question'])}", "", f"**Вопрос на перенос:** {esc(p['transfer_question'])}",
          "", f"**Мост к данным и ИТ:** {esc(p['data_it_bridge'])}", "", "## Чек-лист физики", "", "| Пункт | Ответ | Пояснение |", "| --- | --- | --- |"]
    pcs = {c["id"]: c["item"] for c in json.loads((ROOT / "domain_pack" / "physics_checklist.json").read_text(encoding="utf-8"))}
    L += [f"| {esc(pcs.get(x['item'], x['item']))} | {x['answer']} | {esc(x.get('note'))} |" for x in p["physics_checklist"]]
    L += ["", "## Звук", "", f"- Голос: {esc(a.get('voice'))}; запасной: {esc(a.get('fallback_voice'))}",
          f"- Темп: {a.get('wpm')} слов/мин (норма 110–150); громкость: {a.get('lufs')} LUFS (норма −16)",
          f"- Синхрон голоса и кадра: до {a.get('sync_max_s')} с ({esc(a.get('sync_note'))})",
          f"- Распознавание речи: ошибок {esc(a.get('asr_wer'))} (норма ≤ 0,10) {esc(a.get('asr_note', ''))}", ""]
    (d / "passport.md").write_text("\n".join(L), encoding="utf-8")
    print(f"{d / 'passport.md'}")


if __name__ == "__main__":
    for x in sys.argv[1:]:
        main(x)

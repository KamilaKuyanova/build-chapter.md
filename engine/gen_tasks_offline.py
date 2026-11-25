#!/usr/bin/env python3
"""Задания без API-ключа: детерминированная сборка из учебного слоя (часть Б). Ничего не выдумывает.
Каждое задание строится из текста шага, а evidence — дословная цитата/фрагмент шага (проверяет validate_layer).

Типы (формат task.schema организаторов):
- single   «Какое утверждение верно для шага?»: верное = утверждение шага; неверные = утверждения других шагов главы
           и типичное заблуждение шага (с id misc.* — курс покажет «типичное заблуждение»);
- multiple «Какие утверждения верны?»: 2 верных утверждения шага + 2 чужих;
- gap      пропуск ключевого термина в утверждении шага;
- order    этапы «решения на данных»: признаки → правило → вывод (шаги с decision_on_data);
- single (kind=data) «Какой вывод по правилу?» для шагов с decision_on_data.
Запуск: python engine/gen_tasks_offline.py --dir data/latyshova [--per-node 2]  → пишет tasks.json"""
import argparse
import json
import pathlib
import random
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import nodetext  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORD = re.compile(r"[А-Яа-яЁё]{7,}")
STOP = {"который", "которая", "которые", "которых", "является", "поэтому", "только", "может", "могут", "обычно",
        "должен", "должна", "должны", "можно", "нужно", "также", "между", "через", "более", "менее", "очень"}


def short(s, n=170):
    s = re.sub(r"\s+", " ", s or "").strip()
    return s if len(s) <= n else s[:n].rsplit(" ", 1)[0] + "…"


def pick_gap_word(claim_text, node):
    terms = [t.lower() for t in node.get("terms_introduced", [])]
    low = claim_text.lower()
    for t in terms:  # сначала термин узла, если он однословный и входит в утверждение
        if " " not in t and len(t) >= 6 and t in low:
            m = re.search(re.escape(t), claim_text, re.I)
            return m.group(0)
    words = [w for w in WORD.findall(claim_text) if w.lower() not in STOP]
    return max(words, key=len) if words else None


class Gen:
    def __init__(self, layer):
        self.layer = layer
        self.nodes = sorted(layer["nodes"], key=lambda n: n["order"])
        self.pool = [(n["id"], c) for n in self.nodes for c in n["claims"] if len(c["text"]) >= 25]
        self.dec_pool = [(n["id"], n["decision_on_data"]["conclusion"]) for n in self.nodes
                         if n.get("decision_on_data") and n["decision_on_data"].get("conclusion")]

    def others(self, nid, k, rng, avoid_text=()):
        cand = [c for (i, c) in self.pool if i != nid and c["text"] not in avoid_text]
        rng.shuffle(cand)
        out, seen = [], set()
        for c in cand:
            key = c["text"][:40]
            if key not in seen:
                seen.add(key)
                out.append(c)
            if len(out) == k:
                break
        return out

    @staticmethod
    def opts(items, rng):
        """items: [(text, is_right, misconception|None)] -> (options, ids правильных) в случайном порядке"""
        items = list(items)
        rng.shuffle(items)
        options = [{"id": f"o{i + 1}", "text": t, "misconception": m} for i, (t, r, m) in enumerate(items)]
        right = [o["id"] for o, (t, r, m) in zip(options, items) if r]
        return options, right

    def base(self, node, k, ty, kind, claim, prompt, expl):
        return {"id": f"{node['id']}.t{k}", "type": ty, "step_id": node["id"], "claim_ids": [claim["id"]], "prompt": prompt,
                "explanation": expl, "kind": kind}

    def for_node(self, node, i, per_node):
        out, rng = [], random.Random(node["id"])
        title = node.get("title_novice") or node["title"]
        claims = [c for c in node["claims"] if len(c["text"]) >= 25]
        if not claims:
            return out
        c0 = claims[0]
        # 1. single: узнавание утверждения шага
        wrong = self.others(node["id"], 3, rng, avoid_text={c["text"] for c in claims})
        mc = node.get("misconception") if isinstance(node.get("misconception"), dict) else None
        items = [(short(c0["text"]), True, None)] + [(short(w["text"]), False, None) for w in wrong[:2]]
        if mc and mc.get("text"):
            items.append((short(mc["text"]), False, mc.get("ref") or None))
        elif len(wrong) > 2:
            items.append((short(wrong[2]["text"]), False, None))
        if len(items) >= 3:
            o, right = self.opts(items, rng)
            t = self.base(node, len(out) + 1, "single", "recall", c0, f"Какое утверждение верно для шага «{title}»?",
                          f"Так сказано в главе (стр. {c0['page_pdf']}): {short(c0['text'], 150)}")
            t.update(options=o, answer=right[0], evidence=c0["quote"])
            out.append(t)
        # 2. вариант по номеру шага: gap / multiple / «заблуждение»
        variant = i % 4
        if variant == 0 or (variant == 1 and len(claims) < 2):
            c = claims[-1]
            w = pick_gap_word(c["text"], node)
            if w:
                pr = re.sub(re.escape(w), "{{1}}", c["text"], count=1, flags=re.I)
                t = self.base(node, len(out) + 1, "gap", "understanding", c, "Допишите пропущенное слово: «" + short(pr, 230) + "»",
                              f"В главе (стр. {c['page_pdf']}): {short(c['text'], 150)}")
                t.update(answer=[w.lower()])
                out.append(t)
        elif variant == 1:
            two = claims[:2]
            wr = self.others(node["id"], 2, rng, avoid_text={c["text"] for c in claims})
            if len(wr) == 2:
                o, right = self.opts([(short(c["text"]), True, None) for c in two] + [(short(w["text"]), False, None) for w in wr], rng)
                t = self.base(node, len(out) + 1, "multiple", "understanding", two[0],
                              f"Какие утверждения верны для шага «{title}»? Выберите все.",
                              "Верные утверждения взяты из этого шага; два других относятся к другим шагам главы.")
                t.update(options=o, answer=right, evidence=two[0]["quote"])
                out.append(t)
        elif variant == 2 and mc and mc.get("text"):
            o, right = self.opts([(short(c0["text"]), True, None), (short(mc["text"]), False, mc.get("ref") or None)] +
                                 [(short(w["text"]), False, None) for w in self.others(node["id"], 1, rng, {c0["text"]})], rng)
            t = self.base(node, len(out) + 1, "single", "transfer", c0, f"Часто думают: «{short(mc['text'], 140)}». Что верно на самом деле?",
                          f"Так сказано в главе (стр. {c0['page_pdf']}): {short(c0['text'], 150)}")
            t.update(options=o, answer=right[0], evidence=c0["quote"])
            out.append(t)
        # 3. шаги «решение на данных»: order и задание на данных
        dd = node.get("decision_on_data")
        if dd and dd.get("features") and dd.get("rule") and dd.get("conclusion"):
            f0 = dd["features"][0]
            items = [("Признак: " + short(f0, 110), "a"), ("Правило: " + short(dd["rule"], 110), "b"),
                     ("Вывод: " + short(dd["conclusion"], 110), "c")]
            order_opts = [{"id": f"o{k + 1}", "text": t, "misconception": None} for k, (t, _) in enumerate(items)]
            shuffled = order_opts[:]
            rng.shuffle(shuffled)
            t = self.base(node, len(out) + 1, "order", "data", c0, "Расставьте этапы решения на данных по порядку: от признака к выводу.",
                          "Сначала смотрим признаки, потом применяем правило, затем делаем вывод.")
            t.update(options=shuffled, answer=[o["id"] for o in order_opts], evidence=dd["rule"])
            out.append(t)
            other_concl = [c for (i2, c) in self.dec_pool if i2 != node["id"]]
            rng.shuffle(other_concl)
            if other_concl:
                o, right = self.opts([(short(dd["conclusion"]), True, None)] + [(short(x), False, None) for x in other_concl[:2]], rng)
                t = self.base(node, len(out) + 1, "single", "data", c0,
                              f"Признаки: {short(f0, 120)}. Правило: {short(dd['rule'], 120)}. Какой вывод?",
                              f"По правилу шага: {short(dd['conclusion'], 150)}")
                t.update(options=o, answer=right[0], evidence=dd["conclusion"])
                out.append(t)
        return out[:max(per_node, 2) + 2]

    def run(self, per_node):
        tasks = []
        for i, n in enumerate(self.nodes):
            tasks += self.for_node(n, i, per_node)
        return tasks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--per-node", type=int, default=2)
    a = ap.parse_args()
    d = pathlib.Path(a.dir)
    layer = json.loads((d / "layer.json").read_text(encoding="utf-8-sig"))
    tasks = Gen(layer).run(a.per_node)
    (d / "tasks.json").write_text(json.dumps({"chapter": layer["chapter"], "tasks": tasks}, ensure_ascii=False, indent=1), encoding="utf-8")
    by = {}
    for t in tasks:
        by[t["type"]] = by.get(t["type"], 0) + 1
    print(f"{d.name}: заданий {len(tasks)}, по типам {by}")


if __name__ == "__main__":
    main()

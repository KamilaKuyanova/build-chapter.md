"""Распознавание по набору признаков (Р — распознавание): таблица «признак × вариант» с баллами.
Модель состояния: число рассмотренных признаков k; суммы по вариантам считаются из открытых строк, в конце подсвечивается
вариант с наибольшей суммой. Параметры: features [строки], candidates [{name, color}], scores [[балл варианта…] по строкам].
beat: k [от, до], winner (true — подсветить итог), card."""
from canvas import SG, caption, card, color, current, font, header, layout, new, rgb, text, track, wrap

NAME, TYPE = "compare_signs", "Р"
STATE = "число открытых признаков k; суммы баллов — функция k"
EXAMPLE = {"title": "Какая это порода?",
           "features": ["сопротивление высокое", "ПС отклоняется", "ГК низкий", "есть глинистая корка"],
           "candidates": [{"name": "коллектор с нефтью", "color": "fluids.oil"}, {"name": "плотная порода", "color": "lithology.dense"},
                          {"name": "глина", "color": "lithology.shale"}],
           "scores": [[2, 2, 0], [2, 0, 0], [2, 1, 0], [2, 0, 0]]}


def spec(params):
    return {"scene": NAME, "difficulty_type": TYPE, "state_model": STATE,
            "objects": ["признаки: " + "; ".join(params["features"]), "варианты: " + ", ".join(c["name"] for c in params["candidates"])],
            "parameters": params,
            "invariants": ["баллы признаков не меняются между кадрами", "вывод — вариант с наибольшей суммой",
                           "строки открываются синхронно с голосом"],
            "assumptions": params.get("assumptions", ["баллы отражают признаки из таблицы главы"]),
            "frame_class": "B", "origin": "code_from_model", "label": "схема"}


def render(t, beats, params, W, H):
    im, dr = new(W, H)
    L = layout(W, H)
    b = current(beats, t)
    beat = b.get("beat") or {}
    F, C, S = params["features"], params["candidates"], params["scores"]
    k = max(0.0, min(len(F), track(beats, t, "k", 0.0)))
    nk = int(k + 0.001)
    header(dr, L, params.get("title", ""), params.get("source_note"), "схема")
    x0, x1 = L["main"][0], L["side"][2]
    y0, y1 = L["main"][1], (L["side"][3] if L["vertical"] else L["main"][3])
    fw = (x1 - x0) * (0.42 if L["vertical"] else 0.40)
    cw = (x1 - x0 - fw) / len(C)
    head_h = 150
    row_h = min(120, (y1 - y0 - head_h - 140) / (len(F) + 1))
    sums = [sum(S[r][c] for r in range(nk)) for c in range(len(C))]
    win = max(range(len(C)), key=lambda c: sums[c]) if beat.get("winner") else None
    for c, cand in enumerate(C):
        cx0 = x0 + fw + c * cw
        dr.rounded_rectangle([cx0 + 6, y0, cx0 + cw - 6, y0 + head_h - 10], radius=12,
                             fill=rgb(color(cand["color"])), outline=rgb(SG["text"]) if win == c else None, width=6)
        hs = 36 if not L["vertical"] else 32
        for i, ln in enumerate(wrap(cand["name"], hs, cw - 24, True)[:3]):
            text(dr, (cx0 + cw / 2, y0 + 16 + i * (hs + 6)), ln, hs, True, SG["background"], anchor="ma")
    y = y0 + head_h
    for r, f in enumerate(F):
        shown = r < nk
        is_cur = r == nk - 1
        dr.rectangle([x0, y, x1, y + row_h - 6], fill=rgb(SG["panel"]) if not is_cur else rgb(SG["panel"], 255),
                     outline=rgb(color("measurement")) if is_cur else None, width=4)
        for i, ln in enumerate(wrap(f, 38, fw - 30)[:2]):
            text(dr, (x0 + 16, y + 14 + i * 42), ln, 38, is_cur, SG["text"] if shown else SG["muted"])
        if shown:
            for c in range(len(C)):
                text(dr, (x0 + fw + c * cw + cw / 2, y + row_h / 2), str(S[r][c]), 48, True,
                     SG["text"] if S[r][c] else SG["muted"], anchor="mm")
        y += row_h
    dr.line([x0, y + 4, x1, y + 4], fill=rgb(SG["text"]), width=3)
    text(dr, (x0 + 16, y + 20), "сумма", 44, True)
    for c in range(len(C)):
        text(dr, (x0 + fw + c * cw + cw / 2, y + 44), str(sums[c]), 56, True,
             color("measurement") if win == c else SG["text"], anchor="mm")
    if win is not None:
        text(dr, (x0 + 16, y + 100), f"вывод: {C[win]['name']}", 46, True, color("measurement"))
    if beat.get("card"):
        c = beat["card"]
        card(dr, (W * 0.1, H * 0.22, W * 0.9, H * 0.72), c[0], c[1:], 46, color("measurement"))
    caption(dr, W, H, b.get("on_screen", ""), L["caption_bottom"], L["caption_size"])
    return im

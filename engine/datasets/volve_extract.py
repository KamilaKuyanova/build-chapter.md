#!/usr/bin/env python3
"""Открытые данные Volve (Equinor) -> небольшой срез для практикума курса: data/<глава>/datasets/<id>.json.

Один раз, при наличии LAS-файлов (пакет вводных, папка 07_открытые_данные; в git не кладутся):
  python engine/datasets/volve_extract.py --spec data/latyshova/datasets/volve_15_9-19A.spec.json
Срез: каротаж (ГК, сопротивление, плотность, нейтронный) с шагом 0,5 м и ключ по зонам из официальной интерпретации
Equinor (CPI: водонасыщенность SW, глинистость VSH, пористость PHIF, флаг коллектора SAND_FLAG). Числа не правятся."""
import argparse
import json
import pathlib
import warnings

ROOT = pathlib.Path(__file__).resolve().parents[2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    a = ap.parse_args()
    import lasio
    import numpy as np
    import pandas as pd
    warnings.filterwarnings("ignore")
    sp = pathlib.Path(a.spec)
    S = json.loads(sp.read_text(encoding="utf-8"))
    base = ROOT / S["las_dir"]
    logs = lasio.read(base / S["las_logs"]).df()[list(S["curves"].values())]
    cpi = lasio.read(base / S["las_cpi"]).df()[["SW", "VSH", "PHIF", "SAND_FLAG"]]
    d0, d1 = S["interval"]
    grid = np.round(np.arange(d0, d1 + 1e-9, S.get("step", 0.5)), 2)
    L = logs.sort_index()
    L = L[~L.index.duplicated()]
    rows = L.reindex(L.index.union(grid)).interpolate("index", limit_area="inside").reindex(grid)
    out = {"id": S["id"], "title": S["title"], "source": S["source"], "licence": S["licence"], "well": S["well"],
           "interval": [d0, d1], "step": S.get("step", 0.5), "depth": grid.tolist(), "curves": {}, "zones": []}
    for name, col in S["curves"].items():
        v = rows[col].to_numpy(dtype=float)
        out["curves"][name] = [None if np.isnan(x) else round(float(x), 4) for x in v]
    C = cpi.sort_index()
    for z in S["zones"]:
        part = C[(C.index >= z["from"]) & (C.index <= z["to"])]
        lp = L[(L.index >= z["from"]) & (L.index <= z["to"])]
        key = {k: round(float(part[k].median()), 3) for k in ("SW", "VSH", "PHIF", "SAND_FLAG")}
        logs_med = {n: round(float(lp[c].median()), 3) for n, c in S["curves"].items()}
        out["zones"].append(dict(z, key=key, logs=logs_med))
    dst = sp.with_name(S["id"] + ".json")
    dst.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(dst, len(grid), "точек;", [(z["label"], z["key"], z["logs"]) for z in out["zones"]])


if __name__ == "__main__":
    main()

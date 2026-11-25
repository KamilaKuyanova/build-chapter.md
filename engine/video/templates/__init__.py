"""Шаблоны сцен по типам трудности (общие для всех доменов: предметное приходит параметрами из сценария ролика).

Каждый модуль: NAME, TYPE (М, В, И, Ф, П, Пр, Н, Р), STATE (модель состояния), EXAMPLE (параметры-образец),
spec(params) -> спецификация сцены (объекты, параметры, инварианты, допущения), render(t, beats, params, W, H) -> кадр PIL.
Кадры — детерминированная графика из одной модели состояния (класс A/B), генерации нет."""
import importlib

NAMES = ["process_state", "time_evolution", "tool_and_curve", "formula_explorer", "section_views",
         "step_procedure", "decision_panel", "compare_signs"]


def load(name):
    if name not in NAMES:
        raise KeyError(f"нет шаблона {name}; есть: {', '.join(NAMES)}")
    return importlib.import_module(f"templates.{name}")


def registry():
    out = {}
    for n in NAMES:
        m = load(n)
        out[n] = {"type": m.TYPE, "state": m.STATE, "description": m.__doc__.strip().splitlines()[0]}
    return out

"""Где лежит доменный пакет. Движок не знает геологии: всё предметное читается отсюда.
Домен выбирается переменной окружения DOMAIN: geology (по умолчанию) -> domain_pack/, иначе -> domains/<домен>/.
Если в пакете нового домена файла нет, берётся общий из domain_pack/ (например, стайлгайд) — это видно в отчёте сборки пакета."""
import json
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def name():
    return os.environ.get("DOMAIN", "geology")


def pack_dir(domain=None):
    d = domain or name()
    return ROOT / "domain_pack" if d == "geology" else ROOT / "domains" / d


def path(rel, domain=None):
    p = pack_dir(domain) / rel
    return p if p.exists() else ROOT / "domain_pack" / rel


def load(rel, domain=None):
    return json.loads(path(rel, domain).read_text(encoding="utf-8-sig"))

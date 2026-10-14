"""Выпуск: правила, которые нельзя потерять молча (27-я сессия).

Сама механика проверяется пробной меткой на сборочной машине; здесь —
то, что должно оставаться верным в файлах между выпусками.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

КОРЕНЬ = Path(__file__).resolve().parent.parent
ВЫПУСК = КОРЕНЬ / ".github" / "workflows" / "release.yml"


def _задание() -> dict:
    return yaml.safe_load(ВЫПУСК.read_text(encoding="utf-8"))


def test_машина_кладёт_только_черновик():
    """Опубликовать выпуск — кнопка автора, не машины."""
    текст = ВЫПУСК.read_text(encoding="utf-8")
    assert "gh release create" in текст and "--draft" in текст
    assert "--draft=false" not in текст
    assert not re.search(r"gh release edit[^\n]*--draft", текст)


def test_право_писать_только_у_черновика_и_проверки_скачиванием():
    задание = _задание()
    assert задание["permissions"] == {"contents": "read"}
    с_правом = {имя for имя, работа in задание["jobs"].items()
                if (работа.get("permissions") or {}).get("contents") == "write"}
    assert с_правом == {"draft", "verify-windows"}, с_правом


def test_номер_версии_живёт_в_одном_месте():
    """Метку сверяют с pyproject.toml; своего номера в задании нет."""
    текст = ВЫПУСК.read_text(encoding="utf-8")
    assert "pyproject.toml" in текст
    assert not re.search(r"\b\d+\.\d+\.\d+\b", текст.split("jobs:", 1)[1])


def test_в_выпуск_едут_оба_архива_и_суммы():
    текст = ВЫПУСК.read_text(encoding="utf-8")
    for файл in ("Vertcut-mac.zip", "Vertcut-windows.zip", "SHA256SUMS.txt"):
        assert файл in текст, файл
    заметки = (КОРЕНЬ / ".github" / "release-notes.md").read_text(encoding="utf-8")
    assert "@VERSION@" in заметки
    assert "SHA256SUMS.txt" in заметки


def test_виндовая_раздача_проверяется_скачиванием_из_черновика():
    работа = _задание()["jobs"]["verify-windows"]
    assert работа["uses"] == "./.github/workflows/windows.yml"
    assert работа["with"]["release_tag"]

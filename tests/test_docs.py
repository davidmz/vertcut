"""Публичные документы: README, INSTALL.md и прочие у входа в репозиторий.

Человек ставит по README, агент — по INSTALL.md, сборочная машина
проверяет команды, вынутые из README (`tools/doc-commands.py`).
Если блоки в двух документах разойдутся, проверен будет один путь,
а сломается другой.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parent.parent
ДОКУМЕНТЫ = ["README.md", "INSTALL.md", "AGENTS.md", "CONTRIBUTING.md",
             "SECURITY.md"]


def _инструмент():
    спец = importlib.util.spec_from_file_location(
        "команды_из_документа", КОРЕНЬ / "tools" / "doc-commands.py")
    модуль = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(модуль)
    return модуль


def _текст(имя: str) -> str:
    return (КОРЕНЬ / имя).read_text(encoding="utf-8")


def test_команды_в_README_и_INSTALL_одни_и_те_же():
    блоки = _инструмент().блоки
    человеку = блоки(_текст("README.md"))
    агенту = блоки(_текст("INSTALL.md"))
    нужны = {"clone-unix", "install-unix", "clone-windows",
             "install-windows", "update-unix", "update-windows"}
    assert нужны <= set(человеку), нужны - set(человеку)
    assert set(человеку) == set(агенту), set(человеку) ^ set(агенту)
    for имя in человеку:
        assert человеку[имя] == агенту[имя], f"блок {имя} разошёлся"


def test_сборочная_машина_берёт_команды_из_README():
    """Задания путей «сам в терминале» зовут инструмент, а не держат
    свою копию команд."""
    for файл, система in (("windows.yml", "windows"), ("linux.yml", "unix")):
        текст = (КОРЕНЬ / ".github" / "workflows" / файл).read_text(
            encoding="utf-8")
        assert "tools/doc-commands.py" in текст, файл
        for блок in ("clone", "install", "update"):
            assert f"{блок}-{система}" in текст, f"{файл}: нет {блок}-{система}"


def test_подмена_адреса_только_в_клоне(tmp_path, capsys):
    инструмент = _инструмент()
    assert инструмент.main([str(КОРЕНЬ / "README.md"), "clone-unix",
                            "--repo", "/tmp/клон"]) == 0
    assert "/tmp/клон" in capsys.readouterr().out
    assert инструмент.main([str(КОРЕНЬ / "README.md"), "install-unix",
                            "--repo", "/tmp/клон"]) == 1


def test_ссылки_внутри_репозитория_ведут_в_существующее():
    """Относительные ссылки и картинки: файл должен быть на месте,
    а якорь — среди заголовков. Внешние адреса здесь не проверяются
    (страница выпусков и Issues открываются вместе с репозиторием)."""
    for имя in ДОКУМЕНТЫ:
        текст = _текст(имя)
        for цель in re.findall(r"\]\(([^)\s]+)\)", текст):
            if цель.startswith(("http://", "https://", "mailto:")):
                continue
            путь, _, якорь = цель.partition("#")
            файл = (КОРЕНЬ / путь) if путь else (КОРЕНЬ / имя)
            assert файл.exists(), f"{имя}: {цель}"
            if якорь and файл.suffix == ".md":
                assert якорь in _якоря(файл.read_text(encoding="utf-8")), \
                    f"{имя}: нет якоря {цель}"


def _якоря(текст: str) -> set[str]:
    """Якоря заголовков так, как их строит GitHub."""
    вышло = set()
    for строка in текст.splitlines():
        if строка.startswith("#"):
            заголовок = строка.lstrip("#").strip().lower()
            заголовок = re.sub(r"[^\w\- ]", "", заголовок)
            вышло.add(заголовок.replace(" ", "-"))
    return вышло


def test_ko_fi_нигде_не_объясняется():
    """Решение автора: поддержка — только его, и где её поменять,
    не говорится нигде. В CONTRIBUTING её нет вовсе."""
    assert "ko-fi" not in _текст("CONTRIBUTING.md").lower()
    assert "kofi" not in _текст("CONTRIBUTING.md").lower()

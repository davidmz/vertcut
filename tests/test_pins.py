"""Файл точных версий (`constraints.txt`) и те, кто им пользуется.

27-я сессия нашла, что av 19 молча ломал разбор у каждой свежей
установки: библиотека через две ступени вышла новой, а у нас не
поменялось ничего. Файл закрывает это для всех дорог установки сразу —
если каждая дорога им действительно пользуется. Это и стережётся здесь.

Ставится ли файл на каждой системе и каждом питоне, проверяет
`tools/pins.py` (нужна сеть); что ставится на самом деле —
он же с `--installed` на сборочных машинах.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

КОРЕНЬ = Path(__file__).resolve().parent.parent
ФАЙЛ = КОРЕНЬ / "constraints.txt"


def _строки() -> list[Requirement]:
    return [Requirement(с.split("#", 1)[0].strip())
            for с in ФАЙЛ.read_text(encoding="utf-8").splitlines()
            if с.split("#", 1)[0].strip()]


def _блоки(документ: str) -> dict[str, str]:
    метка = re.compile(r"<!-- commands:([a-z0-9-]+) -->\n```[a-z]*\n(.*?)```",
                       re.S)
    return dict(метка.findall((КОРЕНЬ / документ).read_text(encoding="utf-8")))


def test_каждая_строка_файла_одна_точная_версия():
    """«>=» в файле точных версий — это снова «что выйдет завтра»."""
    for строка in _строки():
        условия = list(строка.specifier)
        assert len(условия) == 1 and условия[0].operator == "==", строка


def test_версии_файла_укладываются_в_вилки_pyproject():
    """Файл не может обещать то, что запрещает `pyproject.toml`: такую
    установку pip отвергнет на машине человека, а не здесь. И у каждой
    прямой зависимости в файле есть строка — иначе главная библиотека
    поедет свежей."""
    проект = tomllib.loads((КОРЕНЬ / "pyproject.toml").read_text(
        encoding="utf-8"))["project"]
    строки = _строки()
    for запись in проект["dependencies"] + проект["optional-dependencies"]["dev"]:
        нужно = Requirement(запись)
        свои = [с for с in строки
                if canonicalize_name(с.name) == canonicalize_name(нужно.name)]
        assert свои, f"нет строки в constraints.txt: {нужно.name}"
        for с in свои:
            версия = next(iter(с.specifier)).version
            assert нужно.specifier.contains(версия, prereleases=True), \
                f"{с} не укладывается в {нужно}"


def test_команды_установки_и_обновления_ставят_по_файлу():
    """README и INSTALL — один и тот же текст (это стережёт
    `test_docs.py`), и сборочные машины берут их строки буквально.
    Каждая строка с `pip install` в этих блоках — с файлом."""
    for документ in ("README.md", "INSTALL.md"):
        блоки = _блоки(документ)
        for имя in ("install-unix", "install-windows",
                    "update-unix", "update-windows"):
            строки = [с for с in блоки[имя].splitlines() if "pip install" in с]
            assert строки, f"{документ}: в {имя} нет pip install"
            for строка in строки:
                assert строка.rstrip().endswith("-c constraints.txt"), \
                    f"{документ}, {имя}: {строка}"


def test_установщик_ставит_по_файлу_и_везёт_его_с_собой():
    """Раздача: файл кладётся рядом с установщиком, установщик зовёт
    pip с ним, и проверка раздачи краснеет, если его нет."""
    установщик = (КОРЕНЬ / "install" / "installer.py").read_text(encoding="utf-8")
    assert re.search(r'"-c",\s*str\(constraints\)', установщик)
    assert 'HERE / "constraints.txt"' in установщик
    сборщик = (КОРЕНЬ / "install" / "build-launcher.py").read_text(encoding="utf-8")
    assert 'ИЗ_КОРНЯ_УСТАНОВКИ = ["constraints.txt"]' in сборщик
    раздача = (КОРЕНЬ / "install" / "build-release.py").read_text(encoding="utf-8")
    assert раздача.count("constraints.txt") >= 2, "проверены не обе системы"


def test_сборочные_машины_ставят_по_файлу():
    """Проверки на Windows ставят pytest в питон установщика — тоже
    по файлу, иначе прогон проверок шёл бы на другом окружении."""
    виндовый = (КОРЕНЬ / ".github" / "workflows" / "windows.yml").read_text(
        encoding="utf-8")
    for строка in виндовый.splitlines():
        if "pip install" in строка and "--upgrade pip wheel" not in строка:
            assert "constraints.txt" in строка, строка
    линукс = (КОРЕНЬ / ".github" / "workflows" / "linux.yml").read_text(
        encoding="utf-8")
    # Установщик, README на Windows, README на Linux — сверка у каждой.
    assert виндовый.count("pins.py") >= 2
    assert re.search(r"pins\.py\S*\s+--installed", линукс)


def test_еженедельная_проверка_ставит_свежее_без_файла():
    """Её смысл — увидеть поломку раньше, чем файл обновят. С файлом
    она проверяла бы то, что уже проверено."""
    текст = (КОРЕНЬ / ".github" / "workflows" / "newest.yml").read_text(
        encoding="utf-8")
    assert "schedule:" in текст and "workflow_dispatch:" in текст
    for строка in текст.splitlines():
        if "pip install" in строка:
            assert "-c " not in строка, строка
    for команда in ("ingest", "pick", "render"):
        assert f"vertcut {команда}" in текст, команда


def test_опись_лицензий_совпадает_с_файлом():
    """Опись (`LICENSES.md`) отстала от жизни на целый набор: в 28-й
    сессии в ней ещё стояли certifi и platformdirs, которых
    huggingface-hub 2 уже не тянет, и не было httpx2 и truststore,
    которые он тянет. Теперь список один — файл точных версий, — а опись
    сверяется с ним в обе стороны. Библиотеки для проверок не в счёт:
    человеку они не ставятся."""
    текст = ФАЙЛ.read_text(encoding="utf-8")
    для_людей = текст.split("# Only for running Vertcut's tests")[0]
    в_файле = {canonicalize_name(Requirement(с.split("#", 1)[0].strip()).name)
               for с in для_людей.splitlines() if с.split("#", 1)[0].strip()}
    опись = (КОРЕНЬ / "LICENSES.md").read_text(encoding="utf-8")
    таблица = опись.split("| library | license |")[1].split("\n\n")[0]
    в_описи = set()
    for строка in таблица.splitlines()[2:]:
        for имя in строка.split("|")[1].split(","):
            в_описи.add(canonicalize_name(имя.strip()))
    assert в_файле - в_описи == set(), "нет в LICENSES.md"
    assert в_описи - в_файле == set(), "в LICENSES.md, но не ставится"

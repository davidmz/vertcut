"""Файл точных версий: ставится ли он на каждой системе и каждом питоне.

    python tools/pins.py            — сверить `constraints.txt`
    python tools/pins.py --newest   — что вышло новее того, что в файле
    python tools/pins.py --installed — то ли встало в ЭТОТ питон

`--installed` нужен сборочным машинам: проверка ниже собирает чужую
машину на бумаге, а здесь — то, что pip на самом деле поставил, своими
пометками своей системы. Сервис (`vertcut`) и сам pip не в счёт.

Для каждой пары «система × питон» из обещанного README pip собирает
установку ЧУЖОЙ машины (`--platform`, `--python-version`) только из
готовых колёс (`--only-binary`), ничего не ставя (`--dry-run`). Пара
считается прошедшей, если:

- готовое колесо нашлось у каждой библиотеки — человеку не придётся
  собирать её из исходников, у него для этого нет ничего;
- каждая библиотека, которую pip взял, есть в файле, и именно этой
  версии. Новая зависимость, приехавшая следом, без строки в файле —
  ровно та дыра, через которую пришёл av 19.

Строка файла, которой не воспользовалась ни одна пара, — тоже отказ:
значит, библиотека больше никому не нужна, и строка врёт.

`--newest` то же самое делает БЕЗ файла и печатает, где свежие версии
расходятся с файлом. С этого начинается обновление (CONTRIBUTING.md);
после правки файла — снова без ключа. Нужен интернет; ставить ничего
не нужно — нужен только pip и `packaging`, которые есть в окружении
сервиса.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import tomllib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

КОРЕНЬ = Path(__file__).resolve().parent.parent
ФАЙЛ = КОРЕНЬ / "constraints.txt"

# Системы — те, что названы в README: метки колёс и то, чем система
# называет себя в пометках вида `; sys_platform == "win32"`.
#
# Номер у macOS — НИЖНЯЯ граница, и pip сам спускается к более старым
# меткам. Apple Silicon — macOS 14: ниже у av и onnxruntime сборок нет
# с прошлого года. У Linux pip сам НЕ спускается (замер: tokenizers
# с меткой manylinux_2_17 не находился при manylinux_2_28), поэтому
# метки перечислены все: glibc 2.28 (onnxruntime ниже не собирается,
# это Ubuntu 20.04, Debian 10 и новее) и всё, что старше.
LINUX = ([f"manylinux_2_{м}_x86_64" for м in range(28, 16, -1)]
         + ["manylinux2014_x86_64"])
СИСТЕМЫ = {
    "macOS Apple Silicon": (["macosx_14_0_arm64"],
                            {"sys_platform": "darwin", "platform_machine": "arm64",
                             "platform_system": "Darwin", "os_name": "posix"}),
    "macOS Intel": (["macosx_13_0_x86_64"],
                    {"sys_platform": "darwin", "platform_machine": "x86_64",
                     "platform_system": "Darwin", "os_name": "posix"}),
    "Windows": (["win_amd64"],
                {"sys_platform": "win32", "platform_machine": "AMD64",
                 "platform_system": "Windows", "os_name": "nt"}),
    "Linux": (LINUX,
              {"sys_platform": "linux", "platform_machine": "x86_64",
               "platform_system": "Linux", "os_name": "posix"}),
}

# Пары, которых нет и быть не может, — с причиной. Не «пропустить, чтобы
# позеленело»: без причины строка сюда не пишется.
ДЫРЫ = {
    ("macOS Intel", "3.14"): "onnxruntime has no Intel Mac build for "
                             "Python 3.14 (its last Intel build, 1.23.2, "
                             "stops at 3.13)",
}


def питоны() -> list[str]:
    """Вилка из `requires-python`: «>=3.11,<3.15» → 3.11 … 3.14."""
    вилка = tomllib.loads((КОРЕНЬ / "pyproject.toml").read_text(
        encoding="utf-8"))["project"]["requires-python"]
    низ = int(re.search(r">=\s*3\.(\d+)", вилка).group(1))
    верх = int(re.search(r"<\s*3\.(\d+)", вилка).group(1))
    return [f"3.{н}" for н in range(низ, верх)]


def что_просим() -> list[str]:
    """Зависимости сервиса и проверок — из `pyproject.toml`, не копией."""
    проект = tomllib.loads((КОРЕНЬ / "pyproject.toml").read_text(
        encoding="utf-8"))["project"]
    return (list(проект["dependencies"])
            + list(проект["optional-dependencies"]["dev"]))


def строки_файла() -> list[Requirement]:
    вышло = []
    for строка in ФАЙЛ.read_text(encoding="utf-8").splitlines():
        строка = строка.split("#", 1)[0].strip()
        if строка:
            вышло.append(Requirement(строка))
    return вышло


def окружение(система: str, питон: str) -> dict:
    return {"python_version": питон, "python_full_version": питон + ".0",
            "implementation_name": "cpython",
            "platform_python_implementation": "CPython", "extra": "",
            **СИСТЕМЫ[система][1]}


def подходит(требование: Requirement, среда: dict) -> bool:
    return требование.marker is None or требование.marker.evaluate(среда)


# ЛОВУШКА, НАЙДЕННАЯ ПЕРВЫМ ЖЕ ПРОГОНОМ: pip, собирая установку чужой
# машины, читает пометки (`; python_version < "3.12"`,
# `; platform_system == "Windows"`) по ТОЙ машине, где запущен, а не
# по чужой. Строка файла «numpy 2.4.6 для питона 3.11» на маке с 3.13
# молча не применялась, а colorama, которую click берёт только
# на Windows, в виндовую установку не попадала вовсе.
#
# Поэтому и то и другое делается здесь, под чужую машину: файл
# отдаётся pip уже без пометок — только строки, которые к ней относятся,
# — а то, что каждая библиотека тянет следом, перебирается по её же
# описанию (`requires_dist` в отчёте pip) с пометками чужой машины.
# Чего pip не взял, а чужой машине нужно, — просится явно, и сборка
# повторяется.
def собрать(система: str, питон: str, с_файлом: bool) -> dict:
    """Что встало бы на этой паре: {имя: версия} или {"": беда}."""
    среда = окружение(система, питон)
    корни = [Requirement(с) for с in что_просим()]
    просим = [str(к) for к in корни]
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        команда = [sys.executable, "-m", "pip", "install", "--dry-run",
                   "--quiet", "--ignore-installed", "--disable-pip-version-check",
                   "--only-binary=:all:", "--target", str(tmp / "t"),
                   "--python-version", питон, "--implementation", "cp",
                   "--report", str(tmp / "report.json")]
        for метка in СИСТЕМЫ[система][0]:
            команда += ["--platform", метка]
        if с_файлом:
            свой = tmp / "constraints.txt"
            свой.write_text("".join(
                f"{с.name}{с.specifier}\n" for с in строки_файла()
                if подходит(с, среда)), encoding="utf-8")
            команда += ["-c", str(свой)]
        for _ in range(4):
            готово = subprocess.run(команда + просим, capture_output=True,
                                    text=True)
            if готово.returncode != 0:
                хвост = [с for с in готово.stderr.splitlines() if с.strip()]
                return {"": "\n      ".join(хвост[-4:])}
            данные = json.loads((tmp / "report.json").read_text(
                encoding="utf-8"))
            взято = {canonicalize_name(x["metadata"]["name"]): x["metadata"]
                     for x in данные["install"]}
            # Обход от корней по описаниям — с пометками чужой машины.
            нужно: dict[str, str] = {}
            очередь = [к for к in корни if подходит(к, среда)]
            нет = set()
            while очередь:
                имя = canonicalize_name(очередь.pop().name)
                if имя in нужно or имя in нет:
                    continue
                if имя not in взято:
                    нет.add(имя)
                    continue
                нужно[имя] = взято[имя]["version"]
                for строка in взято[имя].get("requires_dist") or []:
                    дальше = Requirement(строка)
                    if подходит(дальше, среда):
                        очередь.append(дальше)
            if not нет:
                return нужно
            просим += sorted(нет)
    return {"": "the list of libraries didn't settle in four rounds"}


def пары() -> list[tuple[str, str]]:
    return [(с, п) for с in СИСТЕМЫ for п in питоны()]


def сверить() -> int:
    строки = строки_файла()
    использованы: set[int] = set()
    беды = []
    with ThreadPoolExecutor(4) as пул:
        итоги = dict(zip(пары(), пул.map(lambda п: собрать(*п, True), пары())))
    for (система, питон), взято in итоги.items():
        имя_пары = f"{система}, Python {питон}"
        if (система, питон) in ДЫРЫ:
            print(f"–  {имя_пары}: not supported — {ДЫРЫ[(система, питон)]}")
            continue
        if "" in взято:
            беды.append(f"{имя_пары}: pip can't install it\n      {взято['']}")
            print(f"✗  {имя_пары}")
            continue
        среда = окружение(система, питон)
        свои = []
        for имя, версия in взято.items():
            подходят = [(н, с) for н, с in enumerate(строки)
                        if canonicalize_name(с.name) == имя
                        and подходит(с, среда)]
            if not подходят:
                свои.append(f"{имя} {версия} isn't in the file")
                continue
            for н, с in подходят:
                использованы.add(н)
                if not с.specifier.contains(версия, prereleases=True):
                    свои.append(f"{имя} {версия} doesn't match {с}")
        if свои:
            беды.append(f"{имя_пары}:\n      " + "\n      ".join(свои))
            print(f"✗  {имя_пары}")
        else:
            print(f"✓  {имя_пары}: {len(взято)} libraries, all ready-made")
    лишние = [str(с) for н, с in enumerate(строки) if н not in использованы]
    if лишние:
        беды.append("lines no system needs (remove them):\n      "
                    + "\n      ".join(лишние))
    if беды:
        print("\nPROBLEMS:\n  " + "\n  ".join(беды))
        return 1
    print("\nconstraints.txt installs from ready-made packages everywhere.")
    return 0


def свежее() -> int:
    строки = строки_файла()
    with ThreadPoolExecutor(4) as пул:
        итоги = dict(zip(пары(), пул.map(lambda п: собрать(*п, False), пары())))
    расхождения: dict[str, dict[str, list[str]]] = {}
    for (система, питон), взято in итоги.items():
        if (система, питон) in ДЫРЫ:
            continue
        if "" in взято:
            print(f"✗  {система}, Python {питон}: {взято['']}")
            continue
        среда = окружение(система, питон)
        for имя, версия in взято.items():
            в_файле = [с for с in строки if canonicalize_name(с.name) == имя
                       and подходит(с, среда)]
            было = (str(в_файле[0].specifier).lstrip("=") if в_файле
                    else "not in the file")
            if было != версия:
                расхождения.setdefault(f"{имя}: {было} → {версия}", {}) \
                    .setdefault(система, []).append(питон)
    if not расхождения:
        print("The file already has the newest versions everywhere.")
        return 0
    print("Newer than the file (where):")
    for что, где in sorted(расхождения.items()):
        места = "; ".join(f"{с} {', '.join(п)}" for с, п in где.items())
        print(f"  {что}   [{места}]")
    return 0


def поставлено() -> int:
    """Всё ли, что стоит в этом питоне, — из файла и той же версии."""
    import importlib.metadata as md

    from packaging.markers import default_environment

    среда = {**default_environment(), "extra": ""}
    строки = [с for с in строки_файла() if подходит(с, среда)]
    свои = {"vertcut", "pip", "setuptools", "wheel"}
    беды = []
    стоит = 0
    for пакет in md.distributions():
        имя = canonicalize_name(пакет.metadata["Name"] or "")
        if not имя or имя in свои:
            continue
        стоит += 1
        версия = пакет.version
        строка = next((с for с in строки
                       if canonicalize_name(с.name) == имя), None)
        if строка is None:
            беды.append(f"{имя} {версия} isn't in constraints.txt")
        elif not строка.specifier.contains(версия, prereleases=True):
            беды.append(f"{имя} {версия}, but the file says {строка}")
    if беды:
        print("Installed differently from constraints.txt:\n  "
              + "\n  ".join(беды))
        return 1
    print(f"All {стоит} installed libraries match constraints.txt.")
    return 0


def main(аргументы=None) -> int:
    разбор = argparse.ArgumentParser(
        description="Check constraints.txt on every system and Python")
    разбор.add_argument("--newest", action="store_true",
                        help="show where the newest versions differ "
                             "from the file")
    разбор.add_argument("--installed", action="store_true",
                        help="check what is installed in this Python "
                             "against the file")
    это = разбор.parse_args(аргументы)
    if это.installed:
        return поставлено()
    return свежее() if это.newest else сверить()


if __name__ == "__main__":
    sys.exit(main())

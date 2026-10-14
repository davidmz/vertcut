"""Команды установки — прямо из документа, а не копией.

    python tools/doc-commands.py README.md install-windows
    python tools/doc-commands.py README.md clone-unix --repo /путь/к/клону

Печатает блок кода, перед которым в документе стоит
`<!-- commands:ИМЯ -->`. Им пользуется сборочная машина: путь
«сам в терминале» проверяется теми самыми строками, которые человек
скопирует из README, и разойтись с ними проверка не может.

`--repo` подменяет адрес репозитория (пока он закрыт, клонировать
его анонимно нельзя) — это единственная правка, и делается она здесь,
у всех на виду, а не в задании сборочной машины.

**Блоки в README и в INSTALL.md одинаковые** — человек и агент ставят
одними командами. Это сторожит `tests/test_docs.py`.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

АДРЕС = "https://github.com/eduard1414ed/vertcut.git"
МЕТКА = re.compile(r"<!-- commands:([a-z0-9-]+) -->\n```[a-z]*\n(.*?)```",
                   re.S)


def блоки(текст: str) -> dict[str, str]:
    """Все помеченные блоки документа: имя → текст блока."""
    вышло: dict[str, str] = {}
    for имя, тело in МЕТКА.findall(текст):
        if имя in вышло:
            raise SystemExit(f"two blocks named {имя}")
        вышло[имя] = тело
    return вышло


def main(аргументы=None) -> int:
    разбор = argparse.ArgumentParser(
        description="Print a marked command block from a document")
    разбор.add_argument("document", type=Path)
    разбор.add_argument("name")
    разбор.add_argument("--repo", default=None,
                        help="clone from here instead of GitHub")
    это = разбор.parse_args(аргументы)
    все = блоки(это.document.read_text(encoding="utf-8"))
    if это.name not in все:
        print(f"no block {это.name} in {это.document}; there are: "
              + ", ".join(sorted(все)), file=sys.stderr)
        return 1
    тело = все[это.name]
    if это.repo:
        if АДРЕС not in тело:
            print(f"--repo given, but block {это.name} doesn't clone",
                  file=sys.stderr)
            return 1
        # Путь с пробелами — в кавычках: так его читают и bash,
        # и PowerShell.
        откуда = f'"{это.repo}"' if " " in это.repo else это.repo
        тело = тело.replace(АДРЕС, откуда)
    sys.stdout.write(тело)
    return 0


if __name__ == "__main__":
    sys.exit(main())

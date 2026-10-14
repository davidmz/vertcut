"""Сценарий: docx или txt → текст, который был произнесён.

**Читается без сторонних библиотек.** `.docx` — это zip с XML внутри,
и разобрать оттуда абзацы стоит двадцати строк. Ставить ради этого
пакет значит удлинить список, который чужой человек ставит руками
на своей машине.

**Из документа выбрасывается то, что не произносится.** В сценариях
стоят заголовки разделов капсом и разделители из звёздочек. Для укладки
на звук это слова, которым надо найти место в звуке, — и не найдётся:
времена поедут, а границы фраз встанут не туда.

**Выброшенное показывается всегда.** Правило простое и потому иногда
неправо: фраза, сказанная капсом всерьёз, под него попадёт. Показанный
список — единственный способ это заметить, и он дешевле любой умной
проверки.

**Комментарии Word не читаются.** Они лежат отдельным файлом внутри
архива и в текст документа не входят. Это удобно и нарочно: пометки
на полях не произносятся.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from .errors import VertcutError

# Пространство имён вордовского XML. Одно на весь формат.
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

_LETTER = re.compile(r"[^\W\d_]", re.UNICODE)

# Строчные буквы — признак того, что строка произносится.
#
# Список языков здесь ограниченный, и это честно названная слабость
# раздачи: строка на греческом или на грузинском будет сочтена
# заголовком и выброшена. Записано в TODO.md вместе с транслитерацией —
# у обеих бед одна причина и одно решение.
_LOWER = re.compile(r"[a-zа-яё]")   # язык видео


def _paragraphs_docx(path: Path) -> list[str]:
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        raise VertcutError(
            f"The file does not open as a Word document: {path}",
            hint="save the script as .docx or .txt",
        ) from None
    with archive:
        try:
            body = archive.read("word/document.xml")
        except KeyError:
            raise VertcutError(
                f"The document has no text inside: {path}",
                hint="save it again from Word",
            ) from None
    root = ElementTree.fromstring(body.decode("utf-8"))
    out = []
    for para in root.iter(f"{_W}p"):
        # Разрыв строки внутри абзаца — тоже разрыв: им разделяют
        # реплики, и склеивать их в одну строку нельзя.
        pieces = []
        for node in para.iter():
            if node.tag == f"{_W}t":
                pieces.append(node.text or "")
            elif node.tag == f"{_W}br":
                pieces.append("\n")
        out.extend("".join(pieces).split("\n"))
    return out


def _paragraphs_txt(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").split("\n")


def is_spoken(line: str) -> bool:
    """Произносится ли эта строка."""
    text = line.strip()
    if not text:
        return False
    letters = _LETTER.findall(text)
    if len(letters) < 2:
        # `***`, номера, одинокая буква — не речь.
        return False
    return bool(_LOWER.search(text))


def read(path: Path) -> tuple[str, list[str]]:
    """Текст сценария и список выброшенных строк.

    Абзацы разделяются пустой строкой: сегментация фраз рвёт по абзацу
    всегда, и склеить два абзаца в один значит однажды получить фразу,
    сшитую из конца одного раздела и начала другого.
    """
    path = Path(path)
    if not path.exists():
        raise VertcutError(f"Script file not found: {path}")
    suffix = path.suffix.lower()
    if suffix == ".docx":
        raw = _paragraphs_docx(path)
    elif suffix in (".txt", ".md"):
        raw = _paragraphs_txt(path)
    else:
        raise VertcutError(
            f"Cannot read {suffix or 'a file with no extension'}: {path}",
            hint="the script must be .docx or .txt",
        )

    kept, dropped = [], []
    for line in raw:
        text = line.strip()
        if not text:
            continue
        (kept if is_spoken(text) else dropped).append(text)

    if not kept:
        raise VertcutError(
            f"The script has no spoken lines: {path}",
            hint="check that the text is in the document itself, "
                 "not in comments in the margins",
        )
    return "\n\n".join(kept) + "\n", dropped

"""Шрифты: набор в поставке, свой файл, какие знаки шрифт знает.

## Зачем отдельный файл

Шрифт ломается тихо. Подключили красивый — а он не знает кириллицы,
и вместо букв в ролике встают квадратики. Увидит это зритель: сборка
пройдёт, заслоны пройдут (субтитр ЕСТЬ и стоит на месте — квадратики
тоже краска), и человек узнает о беде из комментариев.

Поэтому проверка знаков написана своя и точная: разбирается таблица
`cmap` самого файла шрифта. Не «нарисуем и посмотрим, похоже ли
на квадратик» — это гадание, а таблица знает точно.

## Где лежат шрифты

Три места, и порядок тот же, что у профиля:

1. рядом с профилем ВИДЕО — если человек положил файл туда;
2. `~/.vertcut/fonts/` — свои шрифты, снаружи репозитория: обновление
   сервиса не должно их сносить;
3. `assets/fonts/` — поставляемые.

**Имя шрифта в профиле — это имя ФАЙЛА, а не название гарнитуры.**
Название гарнитуры лежит внутри файла и у переменных шрифтов бывает
не одно; имя файла человек видит в проводнике и может проверить
глазами.

## Лицензии

У каждого поставляемого шрифта своя, и она лежит рядом файлом.
Проверяется автотестом: положили шрифт без лицензии — покраснело.
Раздача чужого шрифта без его лицензии — это не мелочь, а нарушение,
и заметят его позже всех.
"""

from __future__ import annotations

import struct
from pathlib import Path

from . import layout
from .errors import VertcutError

# Что поставляется. Все под свободными лицензиями, все с кириллицей
# и латиницей, все проверены автотестом на покрытие алфавита.
#
# Набор нарочно РАЗНЫЙ, а не пять оттенков одного: человеку нужен
# выбор, а не иллюзия выбора. Гротеск, гротеск с характером, узкий,
# серифный.
НАБОР = [
    {"файл": "InterTight.ttf", "лицензия": "InterTight-OFL.txt",
     "какой": "sans-serif, neutral — the default"},
    {"файл": "GolosText.ttf", "лицензия": "GolosText-OFL.txt",
     "какой": "sans-serif, a bit warmer, made for Cyrillic"},
    {"файл": "Oswald.ttf", "лицензия": "Oswald-OFL.txt",
     "какой": "narrow — more words fit on a line"},
    {"файл": "Literata.ttf", "лицензия": "Literata-OFL.txt",
     "какой": "serif — a very different voice"},
]


def набор() -> list[dict]:
    """Поставляемые шрифты с путями и тем, есть ли они на месте."""
    вышло = []
    for шрифт in НАБОР:
        путь = layout.fonts() / шрифт["файл"]
        вышло.append({**шрифт, "путь": путь, "есть": путь.exists()})
    return вышло


def найти(имя: str, project: Path | None = None) -> Path:
    """Файл шрифта по имени из профиля.

    Имя с разделителем пути берётся как путь — человек вправе указать
    файл где угодно. Голое имя ищется в трёх местах по порядку.
    """
    сырое = str(имя).strip()
    if not сырое:
        raise VertcutError(
            "The subtitle style has no font set",
            hint="choose a font in the subtitle editor")
    прямой = Path(сырое).expanduser()
    if len(прямой.parts) > 1:
        if прямой.exists():
            return прямой
        raise VertcutError(f"The font file isn't there: {прямой}",
                           hint="choose a font again in the subtitle editor")

    где = ([layout.project_subs(project).parent] if project is not None
           else [])
    где += [layout.my_fonts(), layout.fonts()]
    for папка in где:
        путь = папка / сырое
        if путь.exists():
            return путь
    raise VertcutError(
        f"The font “{сырое}” isn't in any of the places Vertcut looks:\n"
        + "\n".join(f"  {п}" for п in где),
        hint="choose another font in the subtitle editor (terminal: "
             "vertcut fonts)")


def поставить(файл: Path) -> Path:
    """Положить свой шрифт к себе — в `~/.vertcut/fonts/`.

    **Копируется, а не запоминается путём.** Путь на рабочий стол
    через месяц ведёт в пустоту, и ролик соберётся без букв. Копия
    живёт рядом с личным профилем ровно потому же, почему он сам живёт
    снаружи репозитория.
    """
    import shutil

    файл = Path(файл).expanduser()
    if not файл.exists():
        raise VertcutError(f"No such file: {файл}")
    if файл.suffix.lower() not in (".ttf", ".otf", ".ttc"):
        raise VertcutError(
            f"This doesn't look like a font: {файл.name}",
            hint="use a .ttf, .otf or .ttc file")
    знаки(файл)          # разбирается — значит это правда шрифт
    куда = layout.my_fonts() / файл.name
    куда.parent.mkdir(parents=True, exist_ok=True)
    if файл.resolve() != куда.resolve():
        # Копируется СОДЕРЖИМОЕ, без прав и меток файла. Это замер,
        # а не осторожность: первое, на что человек показывает пальцем,
        # — системный шрифт, а системные файлы macOS помечены флагом
        # «защищённый». `copy2` тащит метки за собой и падает
        # с «Operation not permitted» на совершенно исправной просьбе.
        shutil.copyfile(файл, куда)
    return куда


# ─────────────────────────────────────────────────────────────────────
# Какие знаки шрифт знает: разбор таблицы cmap
# ─────────────────────────────────────────────────────────────────────
#
# Разбор свой, двести строк, и это то же решение, что было принято
# с детектором лиц: библиотека ради одной таблицы — это ещё одна
# зависимость в списке, который человек ставит руками на своей машине.
#
# Разбираются форматы 0, 4, 6 и 12 — ими написаны все шрифты, какие
# встречаются живьём. Формат, которого сервис не знает, ПРОПУСКАЕТСЯ
# молча, но если в итоге не набралось ни одной таблицы — это отказ,
# а не пустой ответ: пустой означал бы «шрифт не знает ни одной буквы»,
# и сервис заругался бы на все знаки подряд.
#
# Таблицы платформы Macintosh (platformID 1) не берутся вовсе: там
# коды байтовые, а не юникодные, и принять их за юникод значит
# объявить знакомыми буквы, которых в шрифте нет.


def _таблицы(данные: bytes) -> tuple[int, int]:
    """Начало таблиц шрифта и сколько их. Понимает и сборники (.ttc)."""
    if len(данные) < 12:
        raise VertcutError("The font file is too short")
    метка = данные[:4]
    начало = 0
    if метка == b"ttcf":
        сколько = struct.unpack(">I", данные[8:12])[0]
        if not сколько:
            raise VertcutError("The font collection has no fonts in it")
        начало = struct.unpack(">I", данные[12:16])[0]
        метка = данные[начало:начало + 4]
    if метка not in (b"\x00\x01\x00\x00", b"true", b"OTTO"):
        raise VertcutError("This isn't a font: its header is unknown")
    таблиц = struct.unpack(">H", данные[начало + 4:начало + 6])[0]
    return начало + 12, таблиц


def _где_cmap(данные: bytes) -> int:
    начало, таблиц = _таблицы(данные)
    for n in range(таблиц):
        шаг = начало + n * 16
        имя = данные[шаг:шаг + 4]
        if имя == b"cmap":
            return struct.unpack(">I", данные[шаг + 8:шаг + 12])[0]
    raise VertcutError("The font has no character table (cmap)")


def _подтаблица(данные: bytes, где: int) -> set[int] | None:
    вид = struct.unpack(">H", данные[где:где + 2])[0]
    коды: set[int] = set()
    if вид == 0:
        for код in range(256):
            if данные[где + 6 + код]:
                коды.add(код)
        return коды
    if вид == 4:
        сегментов = struct.unpack(">H", данные[где + 6:где + 8])[0] // 2
        концы = struct.unpack(f">{сегментов}H",
                              данные[где + 14:где + 14 + сегментов * 2])
        шаг = где + 14 + сегментов * 2 + 2
        начала = struct.unpack(f">{сегментов}H",
                               данные[шаг:шаг + сегментов * 2])
        шаг += сегментов * 2
        дельты = struct.unpack(f">{сегментов}h",
                               данные[шаг:шаг + сегментов * 2])
        шаг += сегментов * 2
        сдвиги = struct.unpack(f">{сегментов}H",
                              данные[шаг:шаг + сегментов * 2])
        for n in range(сегментов):
            if начала[n] > концы[n]:
                continue
            for код in range(начала[n], min(концы[n], 0xFFFF) + 1):
                if сдвиги[n] == 0:
                    номер = (код + дельты[n]) & 0xFFFF
                else:
                    место = (шаг + n * 2 + сдвиги[n]
                             + (код - начала[n]) * 2)
                    if место + 2 > len(данные):
                        continue
                    номер = struct.unpack(">H", данные[место:место + 2])[0]
                    if номер:
                        номер = (номер + дельты[n]) & 0xFFFF
                if номер:
                    коды.add(код)
        return коды
    if вид == 6:
        первый, сколько = struct.unpack(">HH", данные[где + 6:где + 10])
        номера = struct.unpack(f">{сколько}H",
                               данные[где + 10:где + 10 + сколько * 2])
        return {первый + n for n, номер in enumerate(номера) if номер}
    if вид == 12:
        групп = struct.unpack(">I", данные[где + 12:где + 16])[0]
        for n in range(групп):
            шаг = где + 16 + n * 12
            с, по, номер = struct.unpack(">III", данные[шаг:шаг + 12])
            if not номер or по < с or по - с > 0x30000:
                continue
            коды.update(range(с, по + 1))
        return коды
    return None


def знаки(путь: Path) -> set[int]:
    """Коды знаков, которые шрифт умеет рисовать."""
    try:
        данные = путь.read_bytes()
    except OSError as bad:
        raise VertcutError(f"Can't read the font file: {путь}") from bad
    где = _где_cmap(данные)
    сколько = struct.unpack(">H", данные[где + 2:где + 4])[0]
    все: set[int] = set()
    разобрано = 0
    for n in range(сколько):
        шаг = где + 4 + n * 8
        площадка = struct.unpack(">H", данные[шаг:шаг + 2])[0]
        сдвиг = struct.unpack(">I", данные[шаг + 4:шаг + 8])[0]
        if площадка == 1:
            continue
        свои = _подтаблица(данные, где + сдвиг)
        if свои is None:
            continue
        разобрано += 1
        все |= свои
    if not разобрано:
        raise VertcutError(
            f"Can't read the font's character table: {путь.name}",
            hint="use another font file — Vertcut can't read this one")
    return все


def чего_нет(текст: str, путь: Path) -> list[str]:
    """Знаки текста, которых в шрифте нет. По одному, по порядку.

    Пробелы и переводы строк не спрашиваются: их рисует не глиф,
    а продвижение пера.
    """
    умеет = знаки(путь)
    вышло, видели = [], set()
    for знак in текст:
        if знак.isspace() or знак in видели or ord(знак) in умеет:
            continue
        видели.add(знак)
        вышло.append(знак)
    return вышло


def сведения(путь: Path) -> dict:
    """Что сервис знает про этот файл шрифта."""
    from PIL import ImageFont

    шрифт = ImageFont.truetype(str(путь), 40)
    оси = []
    try:
        оси = [ось.get("name", b"").decode("utf-8", "replace")
               if isinstance(ось.get("name"), bytes) else str(ось.get("name"))
               for ось in шрифт.get_variation_axes()]
    except Exception:
        оси = []
    return {"путь": путь, "имя": путь.name,
            "гарнитура": " ".join(str(ч) for ч in шрифт.getname() if ч),
            "оси": оси, "переменный": bool(оси),
            "знаков": len(знаки(путь))}

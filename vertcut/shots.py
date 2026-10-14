"""Склейки видео и контактный лист планов.

**Детектор здесь свой в четыре строки, а метрику считает библиотека.**
Так же поступил и сосед, и по той же причине: у библиотеки, откуда
перенесена механика, порог и минимальная длина вбиты константами
внутрь модуля, а её же уборка делает две вещи, которые здесь вредны, —
режет края и рубит длинные планы пополам. Брать было нечего, кроме
одной строки вызова.

**Числа — в `tuning.py`, и там же написано их происхождение.** Порог 45
снят на анимешном эссе. На видео, снятом камерой, он, скорее всего,
поедет; на разговорном видео с одной камерой планов будет один-два
на всё видео, и это не поломка, а правда про материал.

**Ищется по уменьшенной копии.** Замер: проход по копии 33 секунды,
по исходнику 341. Копия детектору склеек НЕ врёт — связь метрик 0.995,
а при рабочем пороге совпали все склейки до одной. Детектору лиц она
врёт, и это разные задачи: склейка — «насколько кадр непохож
на предыдущий», и мелочь на неё не влияет; лицо — это мелочь и есть.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from . import layout, media, report, tuning
from .errors import VertcutError


def detect(proxy: Path, fps: float, total: float,
           говорить=None) -> list[dict]:
    """Границы планов по уменьшенной копии.

    Метрику считает `scenes.py` — своя, без opencv, и дающая те же
    границы, что давала библиотека: проверено на четырёх видео,
    70 тысяч кадров, ноль расхождений.
    """
    from . import scenes

    резы = scenes.склейки(
        proxy, tuning.SCENE_THRESHOLD,
        max(1, int(round(tuning.MIN_SHOT * fps))),
        on_tick=(lambda n: говорить(f"    frames: {n}")) if говорить else None,
    )
    # Склейка — это номер кадра, с которого начинается новый план.
    # Времена считаются здесь и только здесь: своей арифметики времени
    # у метрики нет вовсе.
    границы = [0, *резы]
    scenes_ = [(границы[i] / fps,
                (границы[i + 1] / fps if i + 1 < len(границы) else total))
               for i in range(len(границы))]

    # Склеек нет ни одной: всё видео — один план. Это законный случай,
    # а не поломка, и для раздачи он гораздо обычнее, чем был у соседа:
    # разговор на одну камеру так и выглядит.
    if not scenes_:
        scenes_ = [(0.0, total)]

    низ = tuning.TRIM_HEAD
    верх = max(низ, total - tuning.TRIM_TAIL)
    out = []
    for start, end in scenes_:
        start, end = max(start, низ), min(end, верх)
        if end - start <= 0:
            continue
        out.append({"idx": len(out) + 1,
                    "start": round(start, 3),
                    "end": round(end, 3),
                    "duration": round(end - start, 3)})
    if not out:
        raise VertcutError("No shots left after trimming the edges")
    return out


def thumbs(proxy: Path, found: list[dict], project: Path,
           говорить=report.скажи) -> int:
    """Кадр на план, из середины. По уменьшенной копии.

    Кадры для контактного листа берутся из копии нарочно: лист нужен,
    чтобы глазами проверить, что склейки встали по местам, и 320
    пикселей для этого достаточно. Рамку по такому кадру ставить
    нельзя — это делается на стадии кадра и по исходнику.
    """
    куда = layout.frames(project)
    куда.mkdir(parents=True, exist_ok=True)
    for старый in куда.glob("[0-9]*.jpg"):
        старый.unlink()
    времена = [(s["start"] + s["end"]) / 2 for s in found]
    вышло = media.grab_frames(
        proxy, времена, куда, tuning.THUMB_WIDTH,
        on_tick=lambda n, всего: говорить(f"    frames: {n} of {всего}"))
    if len(вышло) != len(found):
        raise VertcutError(
            f"Got {len(вышло)} frames for {len(found)} shots — "
            "the contact sheet would number them wrong")
    # Имена от ffmpeg идут по порядку, но не по номеру плана:
    # переименуем так, чтобы имя файла и номер плана были одним числом.
    for план, путь in zip(found, вышло):
        путь.rename(layout.thumb(project, план["idx"]))
    return len(вышло)


# Где искать шрифт для подписей на контактном листе.
#
# Список системный и намеренно длинный: сервис раздаётся, и «шрифт
# из моей системы» — первое, что ломается на чужой машине. Не нашлось
# ничего — берётся шрифт самого Pillow: подписи станут некрасивыми,
# но лист соберётся. Ронять разбор из-за шрифта на подписи нельзя.
ШРИФТЫ = {
    "darwin": ["/System/Library/Fonts/Supplemental/Verdana.ttf",
               "/System/Library/Fonts/Helvetica.ttc"],
    "win32": ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf"],
    "linux": ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"],
}


def шрифт_подписей(размер: int):
    """Шрифт подписей на листе.

    Берётся тот же, что у субтитров, — не ради красоты, а чтобы имя
    файла шрифта жило в одном месте. Профиль субтитров может быть
    испорчен или ещё не прочитан, и тогда лист всё равно обязан
    собраться: подписи станут некрасивыми, но разбор из-за шрифта
    падать не должен.

    Берётся ПОСТАВЛЯЕМЫЙ профиль, а не профиль этого видео. Подписи
    на контактном листе — не субтитр: человек настраивает стиль
    субтитров, а не подписей под кадрами, и менять их вместе значит
    удивить его там, где он ничего не просил.
    """
    from PIL import ImageFont
    пути = []
    try:
        from . import subs
        свой = subs.profile()["шрифт"]
        if свой.exists():
            пути.append(str(свой))
    except Exception:
        pass
    ключ = "win32" if sys.platform.startswith("win") else (
        "darwin" if sys.platform == "darwin" else "linux")
    пути += ШРИФТЫ[ключ]
    for путь in пути:
        try:
            return ImageFont.truetype(путь, размер)
        except OSError:
            continue
    return ImageFont.load_default()


def sheets(found: list[dict], project: Path,
           namer=layout.sheet, рисовать_рамку: bool = False) -> list[Path]:
    """Контактные листы: планы одной картинкой, с номером и временем.

    Время на подписи — не украшение. Именно по нему человек находит
    место в видео, когда видит на листе, что склейка встала не туда.
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        raise VertcutError(
            "Pillow is not installed — cannot make a contact sheet",
            hint="install the dependencies: pip install -e . -c constraints.txt",
        ) from None

    на_страницу = tuning.SHEET_COLS * tuning.SHEET_ROWS
    шрифт = шрифт_подписей(20)
    мелкий = шрифт_подписей(17)
    вышло: list[Path] = []

    for страница, сдвиг in enumerate(range(0, len(found), на_страницу), 1):
        кусок = found[сдвиг:сдвиг + на_страницу]
        первый = Image.open(layout.thumb(project, кусок[0]["idx"]))
        ш, в = первый.size
        подпись, поле = 30, 6
        рядов = math.ceil(len(кусок) / tuning.SHEET_COLS)
        лист = Image.new(
            "RGB",
            (tuning.SHEET_COLS * (ш + поле) + поле,
             рядов * (в + подпись + поле) + поле),
            (22, 22, 26),
        )
        перо = ImageDraw.Draw(лист)

        for n, план in enumerate(кусок):
            стб, ряд = n % tuning.SHEET_COLS, n // tuning.SHEET_COLS
            x = поле + стб * (ш + поле)
            y = поле + ряд * (в + подпись + поле)
            кадр = Image.open(layout.thumb(project, план["idx"])).convert("RGB")
            if кадр.size != (ш, в):
                кадр = кадр.resize((ш, в))
            лист.paste(кадр, (x, y))

            if рисовать_рамку and план.get("crop_cx") is not None:
                половина = tuning.VERTICAL / 2 * в / ш
                слева = int((план["crop_cx"] - половина) * ш)
                справа = int((план["crop_cx"] + половина) * ш)
                цвет = ((120, 220, 120) if план.get("crop_by") == "face"
                        else (150, 150, 155))
                перо.rectangle([x + слева, y, x + справа, y + в - 1],
                               outline=цвет, width=3)

            при = план["start"]
            перо.text((x + 5, y + в + 5), f"{план['idx']:03d}",
                      font=шрифт, fill=(240, 240, 245))
            перо.text((x + 60, y + в + 7),
                      f"{int(при // 60)}:{при % 60:05.2f}  "
                      f"{план['duration']:.1f}s",
                      font=мелкий, fill=(150, 150, 158))
            if рисовать_рамку and план.get("crop_by"):
                # По словарю, как у команды. До 24-й сессии здесь были
                # «лицо» и «центр» — одиночные слова, которые заслон
                # принимал за ключи; нашёл прочёс, прочитав лист.
                метка = {"face": "face", "hand": "by hand"}.get(
                    план["crop_by"], "centered")
                перо.text((x + ш - 5, y + в + 7), метка, font=мелкий,
                          fill=(150, 150, 158), anchor="ra")

        куда = namer(project, страница)
        лист.save(куда, quality=88)
        вышло.append(куда)
    return вышло


def write(found: list[dict], project: Path) -> None:
    """Записать `shots.json` целиком и разом, через времянку.

    Рамки досчитываются по ролику, и два счёта могут кончиться в одну
    секунду. Запись напрямую оставила бы в этом случае обрезанный json,
    а это потеря всего разбора планов.
    """
    from . import works

    works.записать(layout.shots(project), {"shots": found})


def read(project: Path) -> list[dict]:
    путь = layout.shots(project)
    if not путь.exists():
        raise VertcutError(f"Shots are not worked out yet: {путь.name} is missing",
                           hint="analyze the video first: vertcut ingest")
    return json.loads(путь.read_text(encoding="utf-8"))["shots"]


def stats(found: list[dict]) -> dict:
    длины = sorted(s["duration"] for s in found)
    середина = длины[len(длины) // 2]
    return {
        "count": len(found),
        "mean": round(sum(длины) / len(длины), 2),
        "median": round(середина, 2),
        "under_1s": sum(1 for x in длины if x < 1.0),
        "over_8s": sum(1 for x in длины if x > 8.0),
        "longest": round(длины[-1], 2),
    }


def кадр_плана(project: Path, план: dict, ширина: int = 640) -> Path:
    """Кадр этого плана покрупнее — для экрана. Считается один раз.

    **Из уменьшенной копии, а не из исходника.** Копия и так 640
    пикселей в ширину, а рамку рукой ставят на кадре шириной примерно
    в столько же: больше просто неоткуда взять. Зато копия лежит
    рядом и не требует, чтобы исходный диск был подключён.

    Отдельно от контактных листов: там кадр 320 и на нём нельзя
    поставить рамку — так и записано в раскладке у `big_frame`.
    """
    готовый = layout.big_frame(project, план["idx"])
    if готовый.exists():
        return готовый
    proxy = layout.proxy(project)
    if not proxy.exists():
        raise VertcutError(
            f"No smaller copy — nowhere to take the frame of shot {план['idx']} from",
            hint="it is made by the first stage of analysis")
    # Из середины плана — как и кадр для контактного листа. Своего
    # числа тут не заводится: две доли на один вопрос однажды
    # разъедутся, и кадр на экране будет не тем, что на листе.
    при = (план["start"] + план["end"]) / 2
    # Времянку заводит `media.кадр_в_файл`, и заводит СВОЮ на каждый
    # вызов: экран просит кадры десятка планов разом, и общая времянка
    # означала бы чужую картинку под номером плана. Там же написано,
    # как это выглядело.
    return media.кадр_в_файл(proxy, при, готовый, ширина)

"""Три уровня профиля субтитров.

Главное, что здесь проверяется, — не «копируется ли файл», а то, ради
чего уровней три: **правка личного образца не устаревает ничего.**
Отпечаток профиля входит в штамп сборки, и если бы видео читало личный
образец напрямую, «сделал стиль своим» устаревало бы ролики всех
остальных видео.

Проверяется это ЧИСЛАМИ: причиной, которую называет сам сервис, — а не
глазами и не рассуждением.
"""

from __future__ import annotations

import pytest

from vertcut import cli, layout, render, subs
from vertcut.errors import VertcutError


@pytest.fixture(autouse=True)
def чистый_кэш():
    subs.сбросить_кэш()
    yield
    subs.сбросить_кэш()


def завести_видео(слаг: str):
    """Папка разбора с одним «собранным» роликом.

    Всё, кроме профиля, у ролика в порядке: файл на месте, границы
    те же, монтаж тот же. Значит любая причина пересобрать, которую
    назовёт сервис, придёт ровно от профиля.
    """
    папка = layout.project(слаг)
    папка.mkdir(parents=True, exist_ok=True)
    cut = {"id": "0000-0005", "файл": "ролик.mp4",
           "words": {"first": 0, "last": 5, "count": 6},
           "render": {"куски": [[0, 5]], "montage": {"hand": {}},
                      "subs": {}}}
    файл = layout.out(папка, cut)
    файл.parent.mkdir(parents=True, exist_ok=True)
    файл.write_text("не пусто", encoding="utf-8")
    cut["render"]["subs"]["профиль"] = subs.отпечаток(project=папка)
    return папка, cut


def поправить_кегль(файл, кегль: float) -> None:
    данные = subs.из_файла(файл)
    данные["size"] = кегль
    subs.записать(файл, данные)
    subs.сбросить_кэш()


# ─── откуда берётся копия ────────────────────────────────────────────

def test_копия_заводится_из_поставляемого_когда_личного_нет():
    папка = layout.project("первое")
    папка.mkdir(parents=True)
    путь, откуда = subs.завести(папка)
    assert откуда == subs.ПОСТАВЛЯЕМЫЙ
    assert путь == layout.project_subs(папка)
    assert путь.read_bytes() == layout.subs_yaml().read_bytes()


def test_копия_заводится_из_личного_когда_он_есть():
    """Настроил на первом видео, загрузил второе — стиль приехал.

    Ради этого уровней и три: без личного образца человек настраивал бы
    заново на каждом видео и на третьем справедливо разозлился.
    """
    личный = layout.my_subs()
    личный.parent.mkdir(parents=True, exist_ok=True)
    поправить_кегль_в_новом(личный, 0.06)

    папка = layout.project("второе")
    папка.mkdir(parents=True)
    путь, откуда = subs.завести(папка)
    assert откуда == subs.ЛИЧНЫЙ
    assert subs.settings(папка)["size"] == 0.06


def поправить_кегль_в_новом(файл, кегль: float) -> None:
    данные = subs.образец()
    данные["size"] = кегль
    subs.записать(файл, данные)
    subs.сбросить_кэш()


def test_копия_делается_один_раз_и_дальше_живёт_своей_жизнью():
    папка = layout.project("своё")
    папка.mkdir(parents=True)
    путь, _ = subs.завести(папка)
    поправить_кегль(путь, 0.09)
    снова, откуда = subs.завести(папка)
    assert откуда == subs.СВОЙ
    assert снова == путь
    assert subs.settings(папка)["size"] == 0.09


# ─── устаревание: главное здесь ──────────────────────────────────────

def test_правка_личного_образца_не_устаревает_ничего():
    """То, ради чего уровней три.

    Копия уже сделана, и чужие видео к личному образцу отношения
    не имеют. Сервис обязан не назвать профиль причиной пересобрать.
    """
    папка, cut = завести_видео("одно")
    assert render.почему_устарел(папка, cut) != render.ПРОФИЛЬ_ПОМЕНЯЛСЯ

    личный = layout.my_subs()
    личный.parent.mkdir(parents=True, exist_ok=True)
    поправить_кегль_в_новом(личный, 0.08)

    причина = render.почему_устарел(папка, cut)
    assert причина != render.ПРОФИЛЬ_ПОМЕНЯЛСЯ, (
        "правка моего образца устарела ролик чужого видео — "
        "значит копии нет и видео читает личный образец напрямую")


def test_правка_копии_в_видео_устаревает_его_ролики():
    """Обратная сторона того же: поправили кегль у видео — его ролики
    обязаны стать устаревшими сами, без напоминания."""
    папка, cut = завести_видео("одно")
    assert render.почему_устарел(папка, cut) != render.ПРОФИЛЬ_ПОМЕНЯЛСЯ

    поправить_кегль(layout.project_subs(папка), 0.08)
    assert render.почему_устарел(папка, cut) == render.ПРОФИЛЬ_ПОМЕНЯЛСЯ


def test_у_каждого_видео_профиль_свой():
    первое, cut1 = завести_видео("первое")
    второе, cut2 = завести_видео("второе")

    поправить_кегль(layout.project_subs(первое), 0.08)

    assert render.почему_устарел(первое, cut1) == render.ПРОФИЛЬ_ПОМЕНЯЛСЯ
    assert render.почему_устарел(второе, cut2) != render.ПРОФИЛЬ_ПОМЕНЯЛСЯ
    assert subs.profile(второе)["кегль"] != subs.profile(первое)["кегль"]


# ─── поставляемый образец не правится ────────────────────────────────

def test_поставляемый_образец_никто_не_переписывает():
    """Он лежит в репозитории: правка отсюда пропала бы при первом
    обновлении сервиса, и притом молча."""
    было = layout.subs_yaml().read_bytes()
    папка, _ = завести_видео("одно")
    поправить_кегль(layout.project_subs(папка), 0.08)
    assert cli.main(["style", "одно", "--save-as-my-style"]) == 0
    assert cli.main(["style", "одно", "--my-style"]) == 0
    assert cli.main(["style", "одно", "--default-style"]) == 0
    assert layout.subs_yaml().read_bytes() == было


def test_взять_мой_стиль_когда_его_нет_отказ_словами():
    завести_видео("одно")
    assert cli.main(["style", "одно", "--my-style"]) == 1


def test_две_кнопки_переносят_стиль_на_другое_видео():
    """«Сделать этот стиль моим» и «взять мой стиль» — весь путь
    из спеки, кнопок ровно две."""
    первое, _ = завести_видео("первое")
    # Второе видео заводится ДО того, как стиль стал моим: его копия
    # уже сделана, и сама она не переедет. Ровно для этого случая
    # и нужна кнопка «взять мой стиль».
    второе, _ = завести_видео("второе")

    поправить_кегль(layout.project_subs(первое), 0.08)
    assert cli.main(["style", "первое", "--save-as-my-style"]) == 0
    assert subs.profile(второе)["кегль"] != subs.profile(первое)["кегль"]

    assert cli.main(["style", "второе", "--my-style"]) == 0
    subs.сбросить_кэш()
    assert subs.settings(второе)["size"] == 0.08


def test_новое_видео_берёт_личный_образец_само():
    """Кнопку «взять мой стиль» на новом видео нажимать не надо:
    копия делается из личного образца при разборе."""
    первое, _ = завести_видео("первое")
    поправить_кегль(layout.project_subs(первое), 0.08)
    assert cli.main(["style", "первое", "--save-as-my-style"]) == 0

    третье = layout.project("третье")
    третье.mkdir(parents=True)
    assert subs.settings(третье)["size"] == 0.08


# ─── форма файла ─────────────────────────────────────────────────────

def test_недостающее_достраивается_из_поставляемого():
    """Личный образец лежит у человека на диске. Заведётся новый ключ —
    его файл не должен от этого сломаться."""
    папка = layout.project("одно")
    папка.mkdir(parents=True)
    subs.записать(layout.project_subs(папка), {"version": 1, "size": 0.05})
    subs.сбросить_кэш()
    данные = subs.settings(папка)
    assert данные["size"] == 0.05
    assert данные["font"] == subs.образец()["font"]
    assert данные["box"]["height"] == subs.образец()["box"]["height"]


def test_незнакомый_ключ_называется_словами():
    """Опечатка «sise» вместо «size» иначе прошла бы тихо: файл
    читается, сервис работает, а число не доехало."""
    папка = layout.project("одно")
    папка.mkdir(parents=True)
    данные = subs.образец()
    данные["sise"] = 0.05
    subs.записать(layout.project_subs(папка), данные)
    subs.сбросить_кэш()
    with pytest.raises(VertcutError) as беда:
        subs.settings(папка)
    assert "sise" in беда.value.message


def test_незнакомый_ключ_виден_и_внутри_блока():
    папка = layout.project("одно")
    папка.mkdir(parents=True)
    данные = subs.образец()
    данные["box"]["color_"] = "#000000"
    subs.записать(layout.project_subs(папка), данные)
    subs.сбросить_кэш()
    with pytest.raises(VertcutError) as беда:
        subs.settings(папка)
    assert "box.color_" in беда.value.message


def test_испорченное_число_роняет_с_именем_ключа():
    папка = layout.project("одно")
    папка.mkdir(parents=True)
    данные = subs.образец()
    данные["size"] = "крупный"
    subs.записать(layout.project_subs(папка), данные)
    subs.сбросить_кэш()
    with pytest.raises(VertcutError) as беда:
        subs.settings(папка)
    assert "size" in беда.value.message


# ─── правка чисел: примечания не теряются ────────────────────────────

def test_правка_числа_не_стирает_примечаний():
    """В профиле у каждого числа написано, как оно мерялось. Записать
    его словарём значит стереть их все и оставить человеку двадцать
    голых чисел, которые он побоится трогать."""
    папка, _ = завести_видео("одно")
    путь = layout.project_subs(папка)
    было = путь.read_text(encoding="utf-8")
    примечаний = было.count("#")

    сказано = subs.задать(путь, {"size": "0.062"})
    стало = путь.read_text(encoding="utf-8")

    assert сказано == ["size: 0.04167 → 0.062"]
    assert стало.count("#") == примечаний
    assert "size: 0.062" in стало
    assert "ORIGIN: one channel, one taste" in стало
    subs.сбросить_кэш()
    assert subs.settings(папка)["size"] == 0.062


def test_правка_вложенного_числа():
    папка, _ = завести_видео("одно")
    путь = layout.project_subs(папка)
    subs.задать(путь, {"box.color": "#101010", "lines.max": "3"})
    subs.сбросить_кэш()
    данные = subs.settings(папка)
    assert данные["box"]["color"] == "#101010"
    assert данные["lines"]["max"] == 3
    assert 'color: "#101010"' in путь.read_text(encoding="utf-8")


def test_недостающий_ключ_вписывается_вместе_с_примечаниями():
    """Ключ мог приехать в профиль достройкой — в файле человека его
    нет. Вписать голое число значит отдать ему число без причины."""
    папка, _ = завести_видео("одно")
    путь = layout.project_subs(папка)
    строки = [с for с in путь.read_text(encoding="utf-8").split("\n")
              if not с.startswith("size:")]
    путь.write_text("\n".join(строки), encoding="utf-8")
    subs.сбросить_кэш()

    subs.задать(путь, {"size": "0.05"})
    текст = путь.read_text(encoding="utf-8")
    assert "size: 0.05" in текст
    assert "ORIGIN: one channel, one taste" in текст
    subs.сбросить_кэш()
    assert subs.settings(папка)["size"] == 0.05


def test_недостающий_вложенный_ключ_ложится_в_свой_блок():
    папка, _ = завести_видео("одно")
    путь = layout.project_subs(папка)
    строки = [с for с in путь.read_text(encoding="utf-8").split("\n")
              if "radius:" not in с]
    путь.write_text("\n".join(строки), encoding="utf-8")
    subs.сбросить_кэш()

    subs.задать(путь, {"box.radius": "0.01"})
    subs.сбросить_кэш()
    данные = subs.settings(папка)
    assert данные["box"]["radius"] == 0.01
    # Лёг в свой блок, а не хвостом файла: иначе он стал бы ключом
    # верхнего уровня и не доехал бы никуда.
    assert данные["box"]["color"] == subs.образец()["box"]["color"]


def test_незнакомый_ключ_в_правке_это_отказ():
    """Опечатка иначе легла бы в файл и осталась там навсегда,
    ничего не делая."""
    папка, _ = завести_видео("одно")
    with pytest.raises(VertcutError) as беда:
        subs.задать(layout.project_subs(папка), {"sise": "0.05"})
    assert "sise" in беда.value.message


def test_число_словами_это_отказ():
    папка, _ = завести_видео("одно")
    with pytest.raises(VertcutError) as беда:
        subs.задать(layout.project_subs(папка), {"size": "крупный"})
    assert "number" in беда.value.message


def test_правка_из_команды_устаревает_ролики():
    папка, cut = завести_видео("одно")
    assert cli.main(["style", "одно", "--set", "size=0.062"]) == 0
    subs.сбросить_кэш()
    assert render.почему_устарел(папка, cut) == render.ПРОФИЛЬ_ПОМЕНЯЛСЯ


def test_профиль_считается_и_без_диска():
    """Лист «до и после» иначе показать нечем: «до» лежит только
    в памяти — на диске его уже нет."""
    числа = subs.образец()
    числа["size"] = 0.062
    prof = subs.к_пикселям(числа)
    assert prof["кегль"] == round(1080 * 0.062)


def test_ключ_из_блока_которого_в_файле_нет_ложится_в_свой_блок():
    """Поймано живьём: профиль видео сохранён до того, как блок
    «подсветка» завёлся, и правка «подсветка.режим» легла ребёнком
    последнего блока файла — в «положение». Файл после этого
    не читался вовсе."""
    папка, _ = завести_видео("одно")
    путь = layout.project_subs(папка)
    # Профиль «постарше»: блока подсветки в нём нет.
    строки, внутри = [], False
    for строка in путь.read_text(encoding="utf-8").split("\n"):
        if строка.startswith("karaoke:"):
            внутри = True
            continue
        if внутри and (not строка or строка.startswith((" ", "#"))):
            continue
        внутри = False
        строки.append(строка)
    путь.write_text("\n".join(строки), encoding="utf-8")
    subs.сбросить_кэш()
    assert "karaoke:" not in путь.read_text(encoding="utf-8")

    subs.задать(путь, {"karaoke.mode": "word"})
    subs.сбросить_кэш()
    данные = subs.settings(папка)
    assert данные["karaoke"]["mode"] == "word"
    assert данные["karaoke"]["by"] == subs.образец()["karaoke"]["by"]
    assert "mode" not in данные["position"]


def test_испорченный_профиль_чинится_той_же_командой():
    """Иначе человек с одной опечаткой в файле остаётся без команды,
    которой он эту опечатку убирает."""
    папка, _ = завести_видео("одно")
    путь = layout.project_subs(папка)
    путь.write_text(путь.read_text(encoding="utf-8") + "\nчепуха: 1\n",
                    encoding="utf-8")
    subs.сбросить_кэш()
    with pytest.raises(VertcutError):
        subs.settings(папка)

    assert cli.main(["style", "одно", "--default-style"]) == 0
    subs.сбросить_кэш()
    assert subs.settings(папка) == subs.образец()


# ─── английские имена и версия файла (сессия 20) ─────────────────────
#
# Ключи и слова профиля стали английскими. Переезда внутри программы
# нет: файл без `version` узнаётся и называется словами. Таблица
# «старое имя → новое» одна и лежит в разовом скрипте вне пакета —
# проверки ниже читают её оттуда же. Скрипт — в `private/`, личной
# папке автора, которая в репозиторий не входит: у остальных проверки
# честно пропускаются, как сверка с пакетом дизайна.

def _таблица() -> dict:
    import runpy
    from pathlib import Path

    скрипт = (Path(__file__).resolve().parent.parent
              / "private" / "tools" / "rename-style-keys.py")
    if not скрипт.exists():
        pytest.skip("разового скрипта автора рядом нет (private/)")
    return runpy.run_path(str(скрипт))


def test_таблица_покрывает_каждый_ключ_образца():
    """Ключ образца, которого нет в таблице, скрипт молча оставил бы
    числом образца — и чужое число человека пропало бы."""
    новые = set(_таблица()["КЛЮЧИ"].values())
    образца = set(subs.плоско(subs.образец())) - {subs.ВЕРСИЯ}
    блоков = {к.rsplit(".", 1)[0] for к in образца if "." in к}
    assert образца <= новые, образца - новые
    assert новые - образца <= блоков | {б.rsplit(".", 1)[0] for б in блоков}


def test_таблица_знает_те_же_слова_что_программа():
    слова = _таблица()["ЗНАЧЕНИЯ"]
    assert set(слова["case"].values()) == set(subs.РЕГИСТРЫ)
    assert set(слова["background"].values()) == set(subs.ПОДЛОЖКИ)
    assert set(слова["karaoke.mode"].values()) == set(subs.ПОДСВЕТКИ)
    assert set(слова["karaoke.by"].values()) == set(subs.ЧЕМ_КРАСИМ)
    виды = _таблица()["ВИДЫ"]
    assert set(виды.values()) == set(subs.виды())


def test_скрипт_переводит_старый_профиль_туда_и_обратно():
    """Старый профиль собирается из нового ОБРАТНОЙ таблицей — и скрипт
    обязан вернуть ровно те же значения. Так проверяется вся таблица
    сразу, без хранения старого файла в репозитории."""
    т = _таблица()
    обратно_ключи = {н: с for с, н in т["КЛЮЧИ"].items()}
    обратно_слова = {к: {н: с for с, н in сл.items()}
                     for к, сл in т["ЗНАЧЕНИЯ"].items()}
    новое = subs.плоско(subs.образец())
    новое.pop(subs.ВЕРСИЯ)
    новое["background"] = subs.ОБВОДКА      # не только значения образца
    новое["end_card.show"] = True
    новое["end_card.image"] = "мой фон.png"
    старое: dict = {}
    for ключ, значение in новое.items():
        значение = обратно_слова.get(ключ, {}).get(значение, значение)
        где, части = старое, обратно_ключи[ключ].split(".")
        for часть in части[:-1]:
            где = где.setdefault(часть, {})
        где[части[-1]] = значение

    вышло, чужие = т["перевести"](старое)
    assert чужие == []
    assert вышло == новое
    текст = т["собрать"](вышло)
    assert т["сверить"](текст, вышло) == []
    assert текст.count("#") == layout.subs_yaml().read_text(
        encoding="utf-8").count("#"), "примечания образца потерялись"


def test_скрипт_не_трогает_файл_с_незнакомым_ключом():
    _, чужие = _таблица()["перевести"]({"кегль": 0.05, "кегл": 0.06})
    assert чужие == ["кегл"]


def test_профиль_старого_образца_называется_словами():
    """Файл, сохранённый до английских ключей, — это тридцать русских
    имён и ни одного знакомого. Отказ «незнакомые ключи: …» честен, но
    бесполезен: человек должен узнать, ЧТО это за файл и что делать."""
    папка = layout.project("одно")
    папка.mkdir(parents=True)
    subs.записать(layout.project_subs(папка),
                  {"шрифт": "InterTight.ttf", "кегль": 0.05,
                   "зоны": {"беречь": "да"}})
    subs.сбросить_кэш()
    with pytest.raises(VertcutError) as беда:
        subs.settings(папка)
    assert "older version" in беда.value.message
    assert str(layout.project_subs(папка)) in беда.value.message
    assert "default style" in (беда.value.hint or "")
    assert "кегль" not in беда.value.message, "вывалил незнакомые ключи"


def test_старый_личный_образец_говорит_сохранить_стиль_заново():
    личный = layout.my_subs()
    личный.parent.mkdir(parents=True, exist_ok=True)
    subs.записать(личный, {"кегль": 0.05})
    with pytest.raises(VertcutError) as беда:
        subs.из_файла(личный)
    assert "my style" in беда.value.message
    assert "Save as my style" in (беда.value.hint or "")


def test_взять_старый_личный_образец_нельзя():
    """Скопируй его в видео — и отказ назвал бы не тот файл: «стиль
    этого видео старый», хотя старый — личный."""
    завести_видео("одно")
    личный = layout.my_subs()
    личный.parent.mkdir(parents=True, exist_ok=True)
    subs.записать(личный, {"кегль": 0.05})
    было = layout.project_subs(layout.project("одно")).read_bytes()
    assert cli.main(["style", "одно", "--my-style"]) == 1
    assert layout.project_subs(layout.project("одно")).read_bytes() == было


def test_версия_новее_программы_тоже_отказ():
    папка = layout.project("одно")
    папка.mkdir(parents=True)
    данные = subs.образец()
    данные[subs.ВЕРСИЯ] = subs.ВЕРСИЯ_СЕЙЧАС + 1
    subs.записать(layout.project_subs(папка), данные)
    subs.сбросить_кэш()
    with pytest.raises(VertcutError) as беда:
        subs.settings(папка)
    assert "version" in беда.value.message


def test_версия_не_правится_как_настройка():
    папка, _ = завести_видео("одно")
    with pytest.raises(VertcutError):
        subs.задать(layout.project_subs(папка), {subs.ВЕРСИЯ: "2"})


def test_да_и_нет_в_файле_настоящие_правда_и_ложь():
    """`yes`/`no`/`on`/`off` yaml превращает в правду и ложь сам, и
    человек, написавший слово, получил бы не то, что написал. Поэтому
    в файле true/false, а выключенная подсветка — `none`, не `off`."""
    данные = subs.образец()
    assert данные["safe_zones"]["enabled"] is True
    assert данные["end_card"]["show"] is False
    assert данные["karaoke"]["mode"] == subs.НЕТ_ПОДСВЕТКИ == "none"


def test_починить_меняет_тот_файл_который_не_читается():
    """«Вернуть стиль» на экране отказа заводила вертикалке свой стиль
    из образца, а не читался стиль ВИДЕО — он оставался прежним, и
    следующий показ экрана падал на нём снова."""
    папка, cut = завести_видео("одно")
    layout.cut(папка, cut["id"]).mkdir(parents=True, exist_ok=True)
    layout.project_subs(папка).write_text("кегль: 0.05\n", encoding="utf-8")
    subs.сбросить_кэш()
    with pytest.raises(VertcutError):
        subs.settings(папка, cut["id"])

    починено = subs.починить(папка, cut["id"], layout.subs_yaml())
    assert починено == [subs.СВОЙ]
    assert not subs.свой_ли(папка, cut["id"]), "завёл вертикалке свой стиль"
    assert subs.settings(папка, cut["id"]) == subs.образец()
    # Читается — не трогается.
    assert subs.починить(папка, cut["id"], layout.subs_yaml()) == []


def test_вид_не_может_задать_версию(monkeypatch, tmp_path):
    подделка = tmp_path / "looks.yaml"
    подделка.write_text("odd:\n  about: test\n  cost: {essay: 0.1}\n"
                        "  settings: {version: 2}\n", encoding="utf-8")
    monkeypatch.setattr(layout, "looks", lambda: подделка)
    with pytest.raises(VertcutError):
        subs.виды()


def test_отказ_называет_чей_стиль_и_ведёт_в_редактор():
    """Старый стиль вертикалки назывался «стилем видео» — путь у них
    похож. И отказ несёт видео и вертикалку: страница ставит под ним
    кнопку в редактор, где стиль чинится."""
    папка, cut = завести_видео("одно")
    свой = layout.cut_subs(папка, cut["id"])
    свой.parent.mkdir(parents=True, exist_ok=True)
    свой.write_text("кегль: 0.05\n", encoding="utf-8")
    subs.сбросить_кэш()
    with pytest.raises(VertcutError) as беда:
        subs.settings(папка, cut["id"])
    assert беда.value.message.startswith("This clip's subtitle style")
    assert беда.value.вид == subs.ОТКАЗ_СТИЛЯ
    assert (беда.value.слаг, беда.value.ключ) == ("одно", cut["id"])

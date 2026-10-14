"""Разбор от начала до конца — на видео, которое проверка делает сама.

**Проверка гоняется на своём материале, а не на живых разборах.**
Видео собирается ffmpeg-ом на месте: секунда цветных полос и синусоида.
Оно ничего не доказывает про качество — оно доказывает, что стадия
доходит до конца, ставит штамп и отказывается там, где обязана.
"""

from __future__ import annotations

import subprocess

import pytest

from vertcut import ingest, layout
from vertcut.errors import VertcutError


# ffmpeg зовётся ТЕМ ЖЕ ПУТЁМ, каким его зовёт сервис.
#
# Голым именем «ffmpeg» он находится только там, где лежит в PATH —
# то есть у автора, поставившего его через brew. На машине, где сервис
# поставлен как у человека, своя копия лежит РЯДОМ С СЕРВИСОМ, и в PATH
# её нет: сборочная машина ответила «не найден указанный файл»
# на пятнадцати проверках сразу.
#
# Правило проекта — «ffmpeg запускается только через run.py» — писалось
# про код сервиса, а проверки его нарушали. Не всплывало это ровно
# потому, что гонялись они на одной машине.
def ффмпег() -> str:
    from vertcut import run as дорога

    return дорога.where("ffmpeg") or "ffmpeg"


def собрать_видео(путь, *, тон=300, узор="testsrc", секунд=1) -> None:
    subprocess.run([
        ффмпег(), "-v", "error", "-y",
        "-f", "lavfi", "-i", f"{узор}=size=320x240:rate=25:duration={секунд}",
        "-f", "lavfi", "-i", f"sine=frequency={тон}:duration={секунд}",
        "-c:v", "libx264", "-crf", "35", "-c:a", "aac", "-shortest", str(путь),
    ], check=True)


@pytest.fixture
def видео(песочница):
    файл = песочница / "проба.mp4"
    собрать_видео(файл)
    return файл


@pytest.fixture(autouse=True)
def только_дорожка(monkeypatch):
    """Проверки этого файла — про устройство разбора, а не про речь.

    Секунда синусоиды словами не является, и распознавать в ней нечего.
    Поэтому здесь идёт одна стадия — снятие дорожки; укладку на звук
    проверяет прогон на настоящем видео, и он записан в private/docs/sessions.md.
    """
    monkeypatch.setattr(ingest, "СТАДИИ", ["extract"])


def test_разбор_доходит_до_конца_и_ставит_штамп(видео):
    meta = ingest.run(видео, говорить=lambda *_: None)
    папка = ingest.where(видео)
    assert layout.audio(папка).stat().st_size > 0
    assert layout.proxy(папка).stat().st_size > 0
    assert meta["stages"]["extract"]["когда"]
    assert meta["fingerprint"]


def test_повтор_переступает_сделанное(видео):
    ingest.run(видео, говорить=lambda *_: None)
    было = layout.audio(ingest.where(видео)).stat().st_mtime_ns
    сказано = []
    ingest.run(видео, говорить=сказано.append)
    стало = layout.audio(ingest.where(видео)).stat().st_mtime_ns
    assert было == стало, "стадия переделалась вместо того, чтобы переступиться"
    # Сказано, что сделанное пропускается, а не делается заново.
    assert any("already done, skipping" in с for с in сказано)


def test_заново_действительно_переделывает(видео):
    ingest.run(видео, говорить=lambda *_: None)
    было = layout.audio(ingest.where(видео)).stat().st_mtime_ns
    ingest.run(видео, заново=True, говорить=lambda *_: None)
    стало = layout.audio(ingest.where(видео)).stat().st_mtime_ns
    assert было != стало


def test_подменённый_файл_роняет_разбор(видео):
    """Подменили видео под тем же именем — стадия падает, а не режет
    по старым временам. Молчание здесь означало бы ролики, собранные
    из чужих секунд."""
    ingest.run(видео, говорить=lambda *_: None)
    собрать_видео(видео, тон=800, узор="testsrc2")
    with pytest.raises(VertcutError) as беда:
        ingest.run(видео, говорить=lambda *_: None)
    # Сказано, что файл другой, и показаны оба отпечатка — было и стало.
    assert "has changed" in беда.value.message
    assert "was " in беда.value.message and "now " in беда.value.message
    assert "rename" in беда.value.hint
    assert беда.value.hint and "--again" in беда.value.hint


def test_журнал_пишется_до_первой_стадии(видео, monkeypatch):
    """`meta.json` ложится сразу, как только видео опознано.

    Пока его нет, разбора не видно в списке — и первые минуты человеку
    было бы негде посмотреть, что работа вообще идёт.
    """
    def падаем(*_a, **_k):
        raise VertcutError("ffmpeg упал нарочно")

    monkeypatch.setitem(ingest.ДЕЛА, "extract", падаем)
    with pytest.raises(VertcutError):
        ingest.run(видео, говорить=lambda *_: None)
    журнал = layout.meta(ingest.where(видео))
    assert журнал.exists(), "разбор упал, и его не видно в списке вовсе"


def test_видео_без_звука_отказывает_словами(песочница):
    файл = песочница / "немой.mp4"
    subprocess.run([
        ффмпег(), "-v", "error", "-y", "-f", "lavfi",
        "-i", "testsrc=size=320x240:rate=25:duration=1",
        "-c:v", "libx264", str(файл),
    ], check=True)
    with pytest.raises(VertcutError) as беда:
        ingest.run(файл, говорить=lambda *_: None)
    # Названо, чего нет, и объяснено, почему без этого нельзя.
    assert "no audio track" in беда.value.message
    assert беда.value.hint


def test_сменившийся_текст_делает_укладку_несделанной(видео, песочница):
    """Разобрали без сценария, потом принесли сценарий.

    Молча оставить машинный текст значит принять сценарий, ничего с ним
    не сделать и не сказать об этом. Стережёт это не особый случай,
    а отпечаток: укладка помнит, ИЗ ЧЕГО посчитана.
    """
    папка = ingest.where(видео)
    папка.mkdir(parents=True, exist_ok=True)
    layout.heard(папка).write_text('{"text": "машина", "words": []}',
                                   encoding="utf-8")
    meta = {"stages": {}}
    ingest.штамп(meta, "align", 1.0, папка)
    assert ingest.сделана(meta, "align", папка)

    layout.script(папка).write_text("Живые слова автора.\n",
                                    encoding="utf-8")
    assert not ingest.сделана(meta, "align", папка), \
        "сценарий пришёл, а укладка считает себя сделанной"


def test_правила_нарезки_фраз_делают_укладку_несделанной(видео, monkeypatch):
    """Поменяли порог — стадия по-прежнему «сделана», и новый порог
    не доехал бы никуда, молча."""
    from vertcut import tuning

    папка = ingest.where(видео)
    папка.mkdir(parents=True, exist_ok=True)
    layout.script(папка).write_text("текст", encoding="utf-8")
    meta = {"stages": {}}
    ingest.штамп(meta, "align", 1.0, папка)

    monkeypatch.setattr(tuning, "PAUSE_SPLIT", tuning.PAUSE_SPLIT + 0.1)
    assert not ingest.сделана(meta, "align", папка)


def test_распознавание_отпечатком_не_стережётся(видео):
    """И это решение: оно зависит только от звука, а звук стережёт
    отпечаток исходника. Стереги его правилами нарезки — и каждая
    правка порога стоила бы минут распознавания."""
    assert "hear" not in ingest.ОТПЕЧАТКИ


def test_разбор_без_сценария_доходит_до_фраз(видео, monkeypatch):
    """Второй вход в ту же стадию: сценария нет — текстом становится
    расшифровка, и стадия доходит до фраз, а не отказывает словами.

    Распознавание подменено: секунда синусоиды словами не является,
    а проверяется здесь устройство стадии, а не слух машины.
    """
    from vertcut import speech

    monkeypatch.setattr(ingest, "СТАДИИ", ["extract", "hear", "align"])
    слова = ["мы", "идем", "домой"]
    monkeypatch.setattr(speech, "hear", lambda *a, **k: (
        [{"word": w, "start": i * 0.3, "end": i * 0.3 + 0.2, "p": 0.8}
         for i, w in enumerate(слова)],
        "Мы идем домой.", 0.1))

    meta = ingest.run(видео, говорить=lambda *_: None)
    папка = ingest.where(видео)
    уложено = speech.read(папка)

    assert meta["text_source"] == speech.РАСШИФРОВКА
    assert layout.transcript(папка).exists()
    assert [ф["text"] for ф in уложено["phrases"]] == ["Мы идем домой."]
    assert speech.phrase_confidence(уложено) == [0.8]


def test_штампы_стадий_лежат_в_порядке_стадий(видео):
    """`videos` печатает их как есть и читается человеком.

    «extract, align, hear» выглядит так, будто укладка шла
    до распознавания. Сортировать при печати нельзя: она нарочно
    не знает про стадии и читает голый json.
    """
    meta = {"stages": {}}
    папка = ingest.where(видео)
    for стадия in reversed(ingest.СТАДИИ):
        ingest.штамп(meta, стадия, 1.0, папка)
    assert list(meta["stages"]) == ingest.СТАДИИ


def test_папки_с_точки_не_видео(песочница):
    """Найдено автором на живом экране, а не тестом.

    В песочнице настройки лежат ВНУТРИ корня, и папка `.настройки`
    показывалась на экране видео — с меткой «журнала нет»
    и предложением её разобрать. Слаг видео с точки не начинается
    никогда, а системного мусора с точкой на диске сколько угодно:
    `.DS_Store`, `.git`, `.Trash`.
    """
    from vertcut import ingest, layout

    корень = layout.root()
    корень.mkdir(parents=True, exist_ok=True)
    (корень / ".настройки").mkdir()
    (корень / ".DS_Store").mkdir()
    (корень / "живое-видео").mkdir()

    слаги = [это["слаг"] for это in ingest.список()]
    assert слаги == ["живое-видео"]


def test_собрана_та_вертикалка_у_которой_файл_лежит(песочница):
    """Колонка вертикалок говорила «собрано» про только что созданную.

    Смотрела она на поле `файл`, а там с момента выбора лежит БУДУЩЕЕ
    имя файла. Поймано глазами на снимке экрана 18-й сессии.
    """
    from vertcut import layout

    project = layout.project("proba")
    cut = {"id": "0001-0020", "файл": "Проба.mp4"}
    assert ingest.собран(project, cut) is False, "имя есть, файла нет"

    cut["render"] = {"когда": "вчера"}
    assert ingest.собран(project, cut) is False, "штамп есть, файла нет"

    layout.out(project, cut).parent.mkdir(parents=True)
    layout.out(project, cut).write_bytes(b"mp4")
    assert ingest.собран(project, cut) is True


def test_meta_пишут_двое_разом(песочница):
    """Два разбора, пущенные разом, писали `meta.json` через общую
    времянку и роняли друг друга (прочёс 27-й сессии)."""
    import threading

    from vertcut import ingest, layout

    папка = layout.root() / "двое"
    беды = []

    def писать(н):
        try:
            for i in range(40):
                ingest.write_meta(папка, {"кто": н, "i": i})
        except Exception as б:          # noqa: BLE001
            беды.append(б)

    нити = [threading.Thread(target=писать, args=(н,)) for н in range(4)]
    for н in нити:
        н.start()
    for н in нити:
        н.join()
    assert not беды, беды
    assert ingest.read_meta(папка)["i"] == 39
    assert not list(папка.glob("*.tmp")) and not list(папка.glob("*.part"))

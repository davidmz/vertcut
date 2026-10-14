"""Описания моделью: то же поле, та же правка, другая метка авторства.

**Ни один тест отсюда в сеть не ходит.** Поставщик подделывается;
проверяется то, что сервис делает с его ответом.
"""

from __future__ import annotations

import io
import json
import os
import urllib.error

import pytest

from vertcut import config, describe, layout, notes, pick
from vertcut.errors import VertcutError

from tests.test_suggest import разбор


def видео(песочница, сколько: int = 3):
    """Разбор и несколько вертикалок в песочнице."""
    project = layout.project("видео")
    project.mkdir(parents=True, exist_ok=True)
    laid = разбор(фраз=60)
    layout.align(project).write_text(json.dumps(laid, ensure_ascii=False),
                                     encoding="utf-8")
    layout.meta(project).write_text(json.dumps(
        {"source": "/где-то/видео.mp4", "duration": 180.0}, ensure_ascii=False),
        encoding="utf-8")
    for n in range(сколько):
        пары = [(1 + n * 12, 12 + n * 12)]
        куски = pick.by_ranges(laid, пары)
        pick.save(project, pick.describe(laid, куски, "фразы", 180.0))
    return project, laid


def поставщик(monkeypatch, ответ_модели: str):
    from vertcut import ai

    config.write({config.MODEL_KEY: "sk-test-0001"})
    сырое = json.dumps({
        "model": "какая-то",
        "content": [{"type": "text", "text": ответ_модели}],
        "usage": {"input_tokens": 800, "output_tokens": 90},
        "stop_reason": "end_turn"}).encode("utf-8")

    class Открывалка:
        def open(self, просьба, timeout=None):
            Открывалка.видел = просьба

            class Ответ:
                def read(self_): return сырое
                def __enter__(self_): return self_
                def __exit__(self_, *_): return False
            return Ответ()

    monkeypatch.setattr(ai.urllib.request, "build_opener",
                        lambda *_: Открывалка())
    return Открывалка


# ─── то же поле ──────────────────────────────────────────────────────

def test_модель_пишет_в_то_же_поле_и_метит_себя(песочница, monkeypatch):
    """Место готово с четвёртой сессии; модели остаётся его заполнять."""
    project, _ = видео(песочница)
    ключи = describe.все_ключи(project)
    поставщик(monkeypatch, json.dumps({"описания": [
        {"ключ": ключи[0], "текст": "Первая подпись"},
        {"ключ": ключи[1], "текст": "Вторая подпись"},
    ]}, ensure_ascii=False))

    вышло = describe.написать(project, ключи[:2])
    assert вышло["записано"] == ключи[:2]
    было = notes.прочитать(pick.load(project, ключи[0]))
    assert было["текст"] == "Первая подпись"
    assert было["кто"] == notes.МОДЕЛЬЮ


def test_описание_моделью_правится_рукой_как_и_всякое(песочница, monkeypatch):
    """Написанное моделью ничем не отличается: правится там же."""
    project, _ = видео(песочница, 1)
    ключ = describe.все_ключи(project)[0]
    поставщик(monkeypatch, json.dumps({"описания": [
        {"ключ": ключ, "текст": "Машинная подпись"}]}, ensure_ascii=False))
    describe.написать(project, [ключ])

    notes.записать(project, ключ, "Моя подпись")
    было = notes.прочитать(pick.load(project, ключ))
    assert было["текст"] == "Моя подпись"
    assert было["кто"] == notes.РУКОЙ


def test_описание_не_устаревает_собранный_ролик(песочница, monkeypatch):
    """Оно не попадает в файл ни одним пикселем.

    Пересобирать сорок секунд видео из-за исправленной запятой
    в подписи — это работа сервиса зря.
    """
    project, _ = видео(песочница, 1)
    ключ = describe.все_ключи(project)[0]
    cut = pick.load(project, ключ)
    cut["штамп"] = {"какой-то": "штамп"}
    pick.update(project, cut)
    поставщик(monkeypatch, json.dumps({"описания": [
        {"ключ": ключ, "текст": "Подпись"}]}, ensure_ascii=False))
    describe.написать(project, [ключ])
    assert pick.load(project, ключ)["штамп"] == {"какой-то": "штамп"}


# ─── одна просьба на все ─────────────────────────────────────────────

def test_все_вертикалки_уезжают_одной_просьбой(песочница, monkeypatch):
    """Модель, видящая все подписи сразу, не начнёт три из них
    словами «Как жить…»; спрошенная по одной — не знает про остальные
    ничего. Это единственное, что сервис вообще проверяет про подписи.
    """
    project, _ = видео(песочница, 3)
    ключи = describe.все_ключи(project)
    видел = поставщик(monkeypatch, json.dumps({"описания": []},
                                              ensure_ascii=False))
    describe.написать(project, ключи)
    ушло = json.loads(видел.видел.data.decode("utf-8"))
    текст = ушло["messages"][0]["content"]
    for ключ in ключи:
        assert f"KEY {ключ}" in текст


def test_модели_даётся_речь_а_не_название(песочница, monkeypatch):
    """Подпись, написанная по названию, пересказывала бы название."""
    project, _ = видео(песочница, 1)
    ключ = describe.все_ключи(project)[0]
    видел = поставщик(monkeypatch, json.dumps({"описания": []},
                                              ensure_ascii=False))
    describe.написать(project, [ключ])
    ушло = json.loads(видел.видел.data.decode("utf-8"))
    assert pick.load(project, ключ)["text"][:40] \
        in ушло["messages"][0]["content"]



def test_модели_даётся_начало_всего_видео(песочница, monkeypatch):
    """Без него модель не знает, о чём видео, и пересказывает ролик.

    Так и вышло на живом видео: подпись в 330 знаков — пересказ первых
    двух предложений ролика. Второй ролик начинается с тринадцатой фразы,
    а видео — с первой: первая обязана уехать, хотя в ролике её нет.
    """
    project, laid = видео(песочница, 2)
    ключ = describe.все_ключи(project)[1]
    assert "фраза номер 1 " not in pick.load(project, ключ)["text"] + " "
    видел = поставщик(monkeypatch, json.dumps({"описания": []},
                                              ensure_ascii=False))
    describe.написать(project, [ключ])
    текст = json.loads(видел.видел.data.decode("utf-8"))["messages"][0]["content"]
    assert laid["phrases"][0]["text"] in текст
    assert '"видео"' in текст          # имя файла: /где-то/видео.mp4


def test_своя_инструкция_по_прежнему_заменяет_поставляемую(песочница,
                                                          monkeypatch):
    """Поле в настройках правит инструкцию, и правка не теряется
    из-за того, что поставляемую переписали."""
    from vertcut import prompts

    project, _ = видео(песочница, 1)
    ключ = describe.все_ключи(project)[0]
    prompts.записать(prompts.ОПИСАНИЯ, "Пиши стихами, моя инструкция")
    prompts.записать_эталоны("Моя настоящая подпись")
    видел = поставщик(monkeypatch, json.dumps({"описания": []},
                                              ensure_ascii=False))
    describe.написать(project, [ключ])
    система = json.loads(видел.видел.data.decode("utf-8"))["system"]
    assert "Пиши стихами, моя инструкция" in система
    assert "Моя настоящая подпись" in система
    assert "40–90 знаков" not in система     # поставляемой там нет

# ─── чего сервис не делает ───────────────────────────────────────────

def test_чужой_ключ_не_записывается(песочница, monkeypatch):
    """Модель назвала ключ, которого не спрашивали.

    Молча записать его нельзя: это может быть чужая вертикалка,
    у которой человек уже написал подпись рукой.
    """
    project, _ = видео(песочница, 2)
    ключи = describe.все_ключи(project)
    notes.записать(project, ключи[1], "Моё, руками")
    поставщик(monkeypatch, json.dumps({"описания": [
        {"ключ": ключи[0], "текст": "Первая"},
        {"ключ": ключи[1], "текст": "Модель лезет не туда"},
    ]}, ensure_ascii=False))

    вышло = describe.написать(project, [ключи[0]])
    assert вышло["чужие_ключи"] == [ключи[1]]
    assert notes.прочитать(pick.load(project, ключи[1]))["текст"] == "Моё, руками"


def test_молчание_модели_видно(песочница, monkeypatch):
    """Запрос оплачен целиком — человек должен знать, за что."""
    project, _ = видео(песочница, 2)
    ключи = describe.все_ключи(project)
    поставщик(monkeypatch, json.dumps({"описания": [
        {"ключ": ключи[0], "текст": "Только одна"}]}, ensure_ascii=False))
    вышло = describe.написать(project, ключи)
    assert вышло["не_ответила"] == [ключи[1]]


def test_ответ_не_разобрался_говорит_где_он_лежит(песочница, monkeypatch):
    project, _ = видео(песочница, 1)
    поставщик(monkeypatch, "Извините, не могу.")
    with pytest.raises(VertcutError) as беда:
        describe.написать(project, describe.все_ключи(project))
    assert "descriptions.answer.txt" in (беда.value.hint or "")
    assert "paid for" in (беда.value.hint or "")


def test_одинаковые_начала_считаются_после_ответа(песочница, monkeypatch):
    """Единственное, что сервис может проверить про подписи, — счёт."""
    project, _ = видео(песочница, 2)
    ключи = describe.все_ключи(project)
    поставщик(monkeypatch, json.dumps({"описания": [
        {"ключ": ключи[0], "текст": "Как жить, когда мир катится"},
        {"ключ": ключи[1], "текст": "Как жить, когда всё случилось"},
    ]}, ensure_ascii=False))
    вышло = describe.написать(project, ключи)
    assert вышло["одинаковые"], "одинаковые начала не замечены"


def test_подписи_на_чужом_языке_видны(песочница, monkeypatch):
    project, _ = видео(песочница, 1)
    ключ = describe.все_ключи(project)[0]
    поставщик(monkeypatch, json.dumps({"описания": [
        {"ключ": ключ, "текст": "What this fragment is actually about"}]},
        ensure_ascii=False))
    assert describe.написать(project, [ключ])["язык_разошёлся"]


def test_эталонов_может_не_быть(песочница, monkeypatch):
    """У чужого человека их нет, и это не мешает кнопке работать."""
    from vertcut import prompts

    project, _ = видео(песочница, 1)
    ключ = describe.все_ключи(project)[0]
    assert prompts.эталоны() == []
    видел = поставщик(monkeypatch, json.dumps({"описания": [
        {"ключ": ключ, "текст": "Подпись"}]}, ensure_ascii=False))
    describe.написать(project, [ключ])
    ушло = json.loads(видел.видел.data.decode("utf-8"))
    assert "КАК ПИШЕТ САМ АВТОР" not in ушло["system"]


def test_эталоны_уезжают_вместе_с_инструкцией(песочница, monkeypatch):
    from vertcut import prompts

    project, _ = видео(песочница, 1)
    ключ = describe.все_ключи(project)[0]
    prompts.записать_эталоны("Первая моя подпись\nВторая моя подпись")
    видел = поставщик(monkeypatch, json.dumps({"описания": [
        {"ключ": ключ, "текст": "Подпись"}]}, ensure_ascii=False))
    describe.написать(project, [ключ])
    ушло = json.loads(видел.видел.data.decode("utf-8"))
    assert "Первая моя подпись" in ушло["system"]


def test_у_обращения_есть_хозяин(песочница, monkeypatch):
    """Двойное нажатие не оплачивается дважды."""
    from vertcut import works

    project, _ = видео(песочница, 1)
    # Номер СВОЕГО процесса, а не единица. Единица — живой процесс
    # только там, где есть система с таким номером: на macOS это её
    # начало, а на Windows такого процесса нет вовсе, и заглушка
    # оказывалась мёртвым хозяином — отказ приходил не тот.
    works.записать(layout.ai_work(project),
                   {"хозяин": {"pid": os.getpid(), "что": "описания",
                               "когда": "сейчас"}})
    with pytest.raises(VertcutError) as беда:
        describe.написать(project, describe.все_ключи(project))
    # Названо, что работа уже идёт, и чья.
    assert "Already running" in беда.value.message

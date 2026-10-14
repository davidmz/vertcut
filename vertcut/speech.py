"""Сценарий, положенный на звук: пословные времена и фразы.

Здесь же всё чтение `align.json` — чтобы «как устроен уложенный
сценарий» знало одно место.

**Читается голым json, без единой тяжёлой библиотеки** — нарочно.
Список фраз и выбор границ должны работать даже тогда, когда
с окружением что-то не так: это ровно тот момент, когда человеку надо
посмотреть, что у него вообще разобрано.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from . import align, layout, phrases as segmentation, report, tuning
from .errors import VertcutError


def _часы(что: str, оценка: float, говорить) -> threading.Event:
    """Показывать, что работа идёт. Долгая тишина неотличима
    от зависания, а распознавание идёт минутами."""
    стоп = threading.Event()

    def тикать() -> None:
        начало = time.time()
        while not стоп.wait(15):
            прошло = time.time() - начало
            осталось = max(оценка - прошло, 0)
            говорить(f"  {что}: {прошло/60:.0f} min so far, "
                     + (f"about {осталось/60:.0f} min left" if осталось >= 60
                        else "under a minute left"))

    threading.Thread(target=тикать, daemon=True).start()
    return стоп


def read(project: Path) -> dict:
    """Уложенный на звук сценарий с диска."""
    путь = layout.align(project)
    if not путь.exists():
        raise VertcutError(
            f"The video is not analyzed yet: {путь.name} is missing",
            hint="analyze it first: vertcut ingest {video} --script {text}",
        )
    return json.loads(путь.read_text(encoding="utf-8"))


def hear(audio_path: Path, duration: float,
         говорить=report.скажи, ход=None) -> tuple[list[dict], str, float]:
    """Услышанные слова с временами и текст, каким его услышала машина.

    Текст нужен тем, у кого сценария нет: он им и становится. У кого
    сценарий есть — не нужен вовсе, и туда не идёт.
    """
    # Оценка нужна не ради точности, а чтобы человек знал, уходить ему
    # пить чай или ждать. Множитель лежит в `tuning`, вместе с ценой
    # остальных стадий и вместе с их происхождением.
    #
    # Раньше он стоял тут числом 0.35 с припиской «замер: 19.5 минут
    # звука разобрались за 5.3 минуты». Пересчёт показал, что 5.3 —
    # это время СОСЕДА из таблицы сравнения, своё было 3.8; да и 5.3/19.5
    # это 0.27, а не 0.35. На чужой машине и на другом звуке будет иначе,
    # и это видно по часам, которые идут ниже.
    оценка = duration * tuning.ЦЕНА_СТАДИЙ["hear"]
    говорить(f"  transcribing: about {оценка/60:.0f} min" if оценка >= 60
             else "  transcribing: under a minute")
    стоп = _часы("transcribing", оценка, говорить)
    начало = time.time()
    try:
        heard, сырьё = align.transcribe(
            audio_path,
            on_progress=ход,
            on_download=lambda имя: говорить(
                f"  model “{имя}”: if it is not on this computer yet, "
                f"it downloads now — about 460 MB, only once"),
        )
    finally:
        стоп.set()
    потрачено = time.time() - начало
    if not heard:
        raise VertcutError(
            "Transcribing heard no words",
            hint="check that the video has speech, not just music",
        )
    return heard, сырьё, потрачено


СЦЕНАРИЙ = "сценарий"
РАСШИФРОВКА = "расшифровка"


def place(text: str, heard: list[dict], duration: float,
          источник: str = СЦЕНАРИЙ) -> dict:
    """Разложить слова текста по времени и нарезать на фразы.

    **Два входа, одна стадия.** Текст пришёл от человека сценарием или
    от машины расшифровкой — дальше он ведёт себя одинаково, и всё, что
    ниже по дороге, про разницу не знает вовсе. Знает только этот файл
    и список фраз, где надёжность называется своим именем.
    """
    свой = источник == СЦЕНАРИЙ
    timing = align.build_timing(text, heard, int(duration * 1000),
                                с_уверенностью=not свой)
    words = timing["words"]
    matched = timing["matched"]

    if not words:
        raise VertcutError(
            f"Could not sync the {'script' if свой else 'transcript'} "
            "to speech: " + (timing.get("note") or "no reason given"),
            hint=("check that the script belongs to this video" if свой else
                  "this is a bug in the analysis, not a problem with "
                  "the video"),
        )
    if свой and matched < tuning.MIN_MATCH:
        raise VertcutError(
            f"The script does not match the speech: {matched:.0%} of words "
            f"matched exactly, at least {tuning.MIN_MATCH:.0%} is needed.\n"
            "  Timings from this would be made up, and cuts would miss "
            "without a word.",
            hint="the script is most likely from a different video",
        )
    if not свой and matched < tuning.SELF_MATCH:
        # Текст и слова пришли из одного прогона распознавания.
        # Разойтись им не с чего, и если разошлись — сломан разбор,
        # а не материал.
        raise VertcutError(
            f"The transcript does not match itself: its text fits its "
            f"own words only {matched:.0%}.\n"
            "  This is a bug in the analysis: the text and the words come "
            "from the same run and must match.",
            hint="analyze again: vertcut ingest ... --again",
        )

    фразы = segmentation.split(words)
    if not фразы:
        raise VertcutError("The words were placed but could not be split into phrases")

    return {
        "источник": источник,
        "matched": matched,
        "words": words,
        "sentences": timing["timing"],
        "phrases": [
            {"idx": p.idx, "start": round(p.start, 3), "end": round(p.end, 3),
             "text": p.text, "words": p.words}
            for p in фразы
        ],
    }


def verify(script_text: str, laid: dict) -> dict:
    """Сошлось ли. Проверяется то, что можно проверить машинно.

    **Проверки одни и те же для обоих входов, а вот вес у них разный.**
    Со сценарием «услышано дословно 89%» — это про распознавание.
    Без сценария та же цифра всегда будет около сотни и не значит
    ничего: текст сам оттуда и взят. Поэтому рядом считается уверенность
    распознавания — единственное, что там вообще измерено про качество
    слов.

    Три вопроса, и все три про потери:

    1. все ли слова сценария получили время;
    2. складываются ли фразы обратно в тот же текст — слово в слово;
    3. попадает ли конец каждого предложения на конец какой-нибудь фразы.

    Третий и есть «фразы сошлись со сценарием». Фраз всегда больше, чем
    предложений: длинное предложение рвётся на несколько субтитров.
    Сходиться обязано другое — что ни одна фраза не сшита из конца
    одного предложения и начала следующего.
    """
    слова_сценария = align.words(script_text)
    слова_уложенные = [w["w"] for w in laid["words"]]
    столько_же = len(слова_сценария) == len(слова_уложенные)

    из_фраз = []
    for фраза in laid["phrases"]:
        из_фраз.extend(w["w"] for w in фраза["words"])
    собрано = align.words(" ".join(из_фраз))
    текст_держится = собрано == слова_сценария

    # Допуск 30 мс: конец предложения считается по временам до
    # округления, конец фразы — по тем же временам после. Сравнивать их
    # «в точку» значит мерить округление, а не совпадение швов.
    концы = [s["end_ms"] / 1000 for s in laid["sentences"]]
    концы_фраз = sorted(p["end"] for p in laid["phrases"])
    на_шве = sum(1 for e in концы
                 if any(abs(e - x) <= 0.03 for x in концы_фраз))

    измерено = sum(1 for w in laid["words"] if "a" not in w)
    return {
        "источник": laid.get("источник", СЦЕНАРИЙ),
        "уверенность": уверенность(laid),
        "words_script": len(слова_сценария),
        "words_laid": len(слова_уложенные),
        "words_match": столько_же,
        "text_holds": текст_держится,
        "sentences": len(концы),
        "sentence_ends_on_phrase": на_шве,
        "phrases": len(laid["phrases"]),
        "measured_words": измерено,
        "matched": laid["matched"],
    }


# ─── чтение уложенного: спаны фраз и надёжность краёв ────────────────

def spans(laid: dict) -> list[tuple[int, int]]:
    """Для каждой фразы — номера её первого и последнего слова.

    Держится на том, что слова фраз идут тем же порядком и тем же
    составом, что общий список слов. Это ПРОВЕРЯЕТСЯ, а не
    предполагается: разъехались — падаем. Молча посчитанные по кривому
    соответствию границы выглядят целыми и звучат не там.
    """
    words, out, курсор = laid["words"], [], 0
    for фраза in laid["phrases"]:
        сколько = len(фраза["words"])
        if сколько == 0:
            raise VertcutError(f"Phrase {фраза['idx']} has no words in the analysis")
        первое, последнее = курсор, курсор + сколько - 1
        if последнее >= len(words):
            raise VertcutError(
                "The phrase words do not match the analysis word list",
                hint="analyze again: vertcut ingest ... --again",
            )
        for сдвиг, своё in enumerate(фраза["words"]):
            if words[первое + сдвиг]["w"] != своё["w"]:
                raise VertcutError(
                    f"Phrase {фраза['idx']}: its words do not match the word list",
                    hint="analyze again: vertcut ingest ... --again",
                )
        out.append((первое, последнее))
        курсор += сколько
    return out


def anchor_distance(laid: dict) -> list[int]:
    """Для каждого слова — через сколько слов лежит ближайшее измеренное.

    Ноль значит, что у самого слова время измерено. Единица — что
    соседнее слово услышано, и промах здесь в сотые доли секунды.
    Всё, что больше трёх, стоит послушать ухом.

    **Число, а не флажок, и это решение с замером.** Из 72 прикидочных
    границ эссе 64 стоят в одном слове от опоры, и только четыре лежат
    глубже трёх слов. Одинаковый флажок утопил бы эти четыре в шуме.
    """
    words = laid["words"]
    далеко = len(words) + 1
    слева = [далеко] * len(words)
    видно = далеко
    for n, слово in enumerate(words):
        видно = 0 if "a" not in слово else (видно + 1 if видно < далеко else далеко)
        слева[n] = видно
    справа = [далеко] * len(words)
    видно = далеко
    for n in range(len(words) - 1, -1, -1):
        видно = 0 if "a" not in words[n] else (видно + 1 if видно < далеко else далеко)
        справа[n] = видно
    return [min(слева[n], справа[n]) for n in range(len(words))]


def чей_текст(laid: dict) -> str:
    """Откуда взялся текст этого разбора: сценарий или расшифровка.

    Живёт в `align.json`, а не в `meta.json`, и это решение: свойство
    описывает уложенный текст, а не ход разбора. Все, кто читает
    уложенное, читают и это — не заглядывая во второй файл.
    """
    return laid.get("источник", СЦЕНАРИЙ)


def confidence(laid: dict) -> list[float] | None:
    """Уверенность распознавания по каждому слову. None — её нет вовсе.

    Её нет у разбора со сценарием, и это не пропуск: там правильным
    считается сценарий, и мнение машины о слове ни на что не влияет.
    """
    words = laid.get("words") or []
    if not any("p" in w for w in words):
        return None
    return [float(w.get("p", 1.0)) for w in words]


def phrase_confidence(laid: dict) -> list[float] | None:
    """Для каждой фразы — самое сомнительное слово в ней.

    **Самое сомнительное, а не среднее.** Среднее по пятнадцати словам
    утопит одно неверное, а в субтитре видно именно его.
    """
    по_словам = confidence(laid)
    if по_словам is None:
        return None
    вышло = []
    for первое, последнее in spans(laid):
        вышло.append(round(min(по_словам[первое:последнее + 1]), 2))
    return вышло


def уверенность(laid: dict) -> dict | None:
    """Как распознавание уверено в словах — числами, без порога.

    **Порога здесь нарочно нет.** Назвать границу «плохого» слова можно
    только замером, а замера на разговорном материале ещё не было.
    Печатаются доли распределения: по ним видно, что нормально,
    а что нет, — и по ним же этот порог однажды и подберут.
    """
    по_словам = confidence(laid)
    if not по_словам:
        return None
    ряд = sorted(по_словам)

    def доля(часть: float) -> float:
        return round(ряд[min(int(часть * len(ряд)), len(ряд) - 1)], 3)

    return {"медиана": доля(0.5), "десятая": доля(0.1),
            "сотая": доля(0.01), "худшее": round(ряд[0], 3),
            "слов": len(ряд)}


def show_time(at: float) -> str:
    return f"{int(at // 60)}:{at % 60:04.1f}"


# ─────────────────────────────────────────────────────────────────────
# Список фраз — то, чем человек выбирает кусок руками
# ─────────────────────────────────────────────────────────────────────

ПРО_КРАЙ = ("The phrase text is from your script. The “edge” column says "
            "what a phrase's time stands on: ‹N on the left means the start "
            "is not on a heard word but estimated between them, and N is "
            "how many words away the nearest heard word is. N=1 means it's "
            "off by hundredths of a second; anything above 3 is worth "
            "listening to.")

ПРО_СЛУХ = ("This video has no script: the phrase text is what Vertcut "
            "heard, and it goes into the subtitles as is. Every word has a "
            "measured time. The “heard” column is how sure transcribing is "
            "about the least certain word of the phrase: 0.99 — sure, below "
            "0.5 — worth reading. It doesn't check the truth: Vertcut can be "
            "sure and wrong.")


# ── Перевод «фразы ↔ слова» ──────────────────────────────────────────
#
# Он нужен ОБЕИМ сторонам и в обе стороны. Человек называет номера
# фраз: в терминале словами, на экране щелчком по строке. На диск
# при этом ложатся номера СЛОВ — потому что перенарезка фраз
# перенумерует их целиком, а слова стоят на месте.
#
# Перевод живёт здесь, рядом со `spans`, и больше нигде. Своя копия
# в веб-слое уже успела ошибиться дважды подряд, причём одинаково:
# у фразы поле `words` — это список самих слов, а не пара номеров.
# Оба раза это выглядело как поломка сервиса, а не как опечатка.

def слова_фразы(laid: dict, номер: int) -> tuple[int, int]:
    """Первое и последнее слово этой фразы."""
    всего = len(laid["phrases"])
    if номер < 1 or номер > всего:
        raise VertcutError(f"There is no phrase {номер}: there are {всего}",
                           hint="to see the list: vertcut phrases VIDEO_ID")
    return spans(laid)[номер - 1]


def фразы_слов(laid: dict, первое: int, последнее: int) -> list[int]:
    """В какие фразы попадают эти слова. Пара «первая, последняя».

    Пустой список — законный ответ: кусок мог не задеть ни одной
    фразы целиком. Молча вернуть первую фразу было бы враньём.
    """
    свои = [n + 1 for n, (a, b) in enumerate(spans(laid))
            if b >= первое and a <= последнее]
    return [свои[0], свои[-1]] if свои else []


def с_начала_фразы(laid: dict, первое_слово: int) -> bool:
    """Стоит ли это слово в начале какой-нибудь фразы.

    **Посреди фразы начинать РАЗРЕШЕНО.** Сервис предупреждает, но
    не запрещает: начать ролик с середины фразы человек вправе, а вот
    посреди СЛОВА не режется никогда — обрубок звука слышен всегда.

    Одно место на весь проект. Своя копия в веб-слое уже успела
    ошибиться: у фразы поле `words` — это список самих слов, а
    не пара номеров, и «начала» из него так не достать.
    """
    return первое_слово in {первое for первое, _ in spans(laid)}


def список_фраз(laid: dict) -> dict:
    """Фразы с временами и надёжностью — одним куском.

    **Считается здесь, а не в команде и не на экране.** Пока это лежало
    в `cli.py`, у экрана был один способ показать тот же список —
    написать его во второй раз. Разошлись бы они на самом важном:
    надёжность тут — ОДИН столбец с ДВУМЯ смыслами, и какой из них
    сейчас, решает не показ, а то, откуда взялся текст.

    Со сценарием сомнение во времени: слово известно точно, а время
    у части слов прикинуто. Без сценария наоборот: время измерено
    у всех слов, под вопросом само слово. Показывается что-то одно,
    и подпись меняется вместе с ним — две надёжности разом означали бы,
    что человеку не сказали, какая из них про его беду.
    """
    фразы = laid["phrases"]
    места = spans(laid)
    далеко = anchor_distance(laid)
    слух = phrase_confidence(laid)

    вышло = []
    for фраза in фразы:
        это = {"idx": фраза["idx"], "start": фраза["start"],
               "end": фраза["end"],
               "duration": round(фраза["end"] - фраза["start"], 3),
               "text": фраза["text"]}
        if слух:
            это["слух"] = слух[фраза["idx"] - 1]
        else:
            первое, последнее = места[фраза["idx"] - 1]
            это["слева"] = далеко[первое]
            это["справа"] = далеко[последнее]
        вышло.append(это)

    return {
        "фразы": вышло,
        "надёжность": "слух" if слух else "край",
        "про": ПРО_СЛУХ if слух else ПРО_КРАЙ,
        "откуда": чей_текст(laid),
    }

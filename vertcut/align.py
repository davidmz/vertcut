"""Укладка известного текста на звук: пословные времена.

Задача не «распознать речь», а положить готовый текст на звук. Текст
известен заранее, и это делает результат заметно надёжнее распознавания
с нуля: при расхождении правильным считается сценарий, а не то, что
расслышала модель. Распознавание нужно здесь только ради времён.

**Провал укладки — это провал, а не повод выдумать времена.** Не
сошлось — падаем. По выдуманным временам нарежут и промахнутся молча,
а увидит это зритель.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path

from . import tuning
from .errors import VertcutError
from .text import WORD_RE

# Граница предложения: точка, восклицательный, вопросительный или
# многоточие, затем возможные кавычки-скобки и пробел.
_SENT_SPLIT = re.compile(r'(?<=[.!?…])["»”)\]]*\s+')

# Открывающие кавычки и скобки: они относятся к следующему слову, а не
# к предыдущему. Прямая кавычка не в списке — она и открывающая,
# и закрывающая, и угадывать тут хуже, чем оставить её слову слева.
_OPENERS = "«“„‘‹([{"

# Тире, которым в русском письме открывается реплика следующего
# говорящего.
#
# ЯЗЫЧНО-ЗАВИСИМОЕ МЕСТО: это русская и европейская привычка,
# у английского прямая речь размечается кавычками. Промах безвреден:
# если тире окажется не диалоговым, оно просто уедет к следующему
# слову, а времён это не двигает вовсе.
_ТИРЕ = "—–"

# Сокращения, после которых точка — не конец предложения.
#
# Список русский, и это ограничение раздачи, названное вслух: у
# английского свой список («Mr.», «e.g.»), и на английском сценарии
# предложения будут иногда рваться лишний раз. Цена промаха невелика —
# лишняя граница предложения не двигает ни одного времени, — но
# записана в TODO.md.
_ABBR = {
    "т", "д", "п", "г", "гг", "в", "вв", "им", "др", "проч", "тыс", "млн",
    "млрд", "руб", "стр", "рис", "см", "напр", "ок",
}


# ─── разбор текста ───────────────────────────────────────────────────

def sentences(text: str) -> list[str]:
    """Разбить сценарий на предложения.

    Абзац рвёт предложение всегда, точка — не всегда: «т. д.» и инициалы
    выглядят как конец фразы. Правило простое и предсказуемое, а не
    умное: промах видно глазами в списке фраз.
    """
    out: list[str] = []
    for block in re.split(r"\n\s*\n|\n", text or ""):
        block = block.strip()
        if not block:
            continue
        pieces = _SENT_SPLIT.split(block)
        buffer = ""
        for piece in pieces:
            buffer = f"{buffer} {piece}".strip() if buffer else piece.strip()
            if _ends_with_abbreviation(buffer):
                continue
            out.append(buffer)
            buffer = ""
        if buffer:
            out.append(buffer)
    return out


def _ends_with_abbreviation(piece: str) -> bool:
    if not piece.endswith("."):
        return False
    last = WORD_RE.findall(piece[:-1])
    if not last:
        return False
    tail = last[-1].lower()
    return len(tail) == 1 or tail in _ABBR


def words(text: str) -> list[str]:
    """Слова в нормальном виде: `ё` и `е` неразличимы, регистр не важен.

    Складывать их обязательно: распознавание `ё` не пишет никогда,
    и «ещё» из сценария иначе никогда не совпадёт с услышанным «еще».
    """
    return [w.lower().replace("ё", "е") for w in WORD_RE.findall(text or "")]


def surfaces(text: str) -> list[str]:
    """Те же слова, но как они написаны: со знаками и регистром.

    Список ровно той же длины и того же порядка, что у `words()`.

    **Знак препинания принадлежит слову, а не промежутку.** Сегментация
    фраз смотрит последний символ слова, и запятая, оставшаяся
    в промежутке, для неё всё равно что её нет. Поэтому к слову клеится
    хвост до начала следующего: `пресса,`, `правило.`, и отдельно
    стоящее тире — `слово —`, без него конец оборота не сработает
    ни разу.

    Открывающие кавычки и скобки из хвоста уходят вперёд, к следующему
    слову: иначе у `правило. «Новый` последним символом окажется `«`,
    и конец предложения пропадёт — ровно тот способ потерять
    пунктуацию, ради которого всё это и делается.
    """
    found = list(WORD_RE.finditer(text or ""))
    out: list[str] = []
    prefix = ""
    for i, match in enumerate(found):
        after = found[i + 1].start() if i + 1 < len(found) else len(text)
        gap = text[match.end():after]
        tail = gap.strip()
        carry = ""
        while tail and tail[-1] in _OPENERS:
            carry = tail[-1] + carry
            tail = tail[:-1].rstrip()
        # Тире после конца предложения — начало чужой реплики, и уходит
        # оно вперёд, как открывающая кавычка. Тире в середине
        # предложения остаётся слову слева: там оно конец оборота,
        # и без него этот конец не сработает ни разу.
        while (len(tail) > 1 and tail[-1] in _ТИРЕ
               and tail[:-1].rstrip()[-1:] in tuning.SENTENCE_END):
            # Пробел после тире свой: «— И», а не «—И». Кавычка
            # к слову прижимается, тире — нет.
            carry = tail[-1] + " " + carry
            tail = tail[:-1].rstrip()
        # Пробел сохраняется только там, где он был: «слово —», но «слово,».
        space = " " if tail and gap[:1].isspace() else ""
        out.append(prefix + match.group(0) + space + tail)
        prefix = carry
    return out


def отпечаток() -> str:
    """Отпечаток правил укладки: как текст ложится на услышанное.

    Рядом с таким же отпечатком правил нарезки фраз, и по той же
    причине: поменялось правило — посчитанное по прежнему устарело,
    и молчать об этом нельзя. Отдельно от него потому, что это разные
    работы: одна кладёт слова на время, другая режет их на фразы.

    Заведено не впрок: за одну сессию правила укладки поменялись
    дважды — раздача времён словам текста вместо кусков распознавания
    и сравнение по частям слова. Оба раза посчитанное раньше было
    устаревшим, а стадия считала себя сделанной.
    """
    import hashlib
    import inspect

    try:
        код = "".join(inspect.getsource(f) for f in (
            map_words, surfaces, sentences, words, _по_частям, _части,
            _spread, _interpolate, exchange))
    except Exception:
        # Подсказка не имеет права ронять то, что она стережёт.
        код = "без исходников"   # не для человека: кусок отпечатка
    return hashlib.sha1(код.encode()).hexdigest()[:16]


# ─── сопоставление ───────────────────────────────────────────────────

def map_words(script: list[str], heard: list[dict]) -> tuple[list[dict], float]:
    """Разложить времена услышанных слов по словам сценария.

    Совпавшие слова получают своё время. Расхождение — ошибка
    распознавания: правильным считается сценарий, а время на его слова
    растягивается по спорному участку пропорционально длине слов. Слова,
    которым не досталось ничего, получают время между соседями.

    **`kind` — откуда взялось время**, и без него не отличить измеренное
    от выдуманного. Заполнены всегда все слова, а измерены только
    `exact` — и весь список фраз потом честно показывает, где время
    стоит на услышанном слове, а где на прикидке.

    | `kind`   | когда | какое время |
    |---|---|---|
    | `exact`  | слово услышано дословно | своё |
    | `spread` | услышано другое | участок делится пропорционально длине слов |
    | `gap`    | слово проглочено | равные шаги между соседями |
    | `edge`   | до первого и после последнего услышанного | нулевой длины |

    **Дефис не участвует в споре, и это замер.** Распознавание рвёт
    «какой-то» на два куска, а иногда, наоборот, слепляет два слова
    в одно («мертвых-мертвых»). И то и другое — расхождение о том, где
    кончается слово, а не о том, какое оно. Пока сравнивались целые
    слова, каждый такой случай считался ошибкой распознавания и слово
    получало прикинутое время.

    Поэтому обе стороны разбираются на части по дефису, сравниваются
    части, а потом части собираются обратно в слова сценария. Слово
    точное, если точны ВСЕ его части.

    Замер на эссе: дословных совпадений 0.8965 против 0.8860 при
    сравнении слитых слов и 0.8919 при сравнении разорванных. То есть
    лучше обоих способов, между которыми иначе пришлось бы выбирать.
    """
    if not script or not heard:
        return [], 0.0

    плоские = _по_частям(heard)
    части_сц: list[str] = []
    хозяин: list[int] = []
    for j, слово in enumerate(script):
        for кусок in _части(слово):
            части_сц.append(кусок)
            хозяин.append(j)

    куски: list[dict | None] = [None] * len(части_сц)
    for tag, i1, i2, j1, j2 in SequenceMatcher(
            None, [h["word"] for h in плоские], части_сц,
            autojunk=False).get_opcodes():
        if tag == "equal":
            for offset in range(j2 - j1):
                source = плоские[i1 + offset]
                куски[j1 + offset] = {"start": source["start"],
                                      "end": source["end"], "kind": "exact",
                                      "p": source.get("p")}
        elif tag == "replace":
            _spread(куски, части_сц, j1, j2,
                    плоские[i1]["start"], плоские[i2 - 1]["end"])
        # delete — услышано лишнее, сценарию это ничего не даёт
        # insert — слова сценария без звука, время им дадут соседи ниже

    spans: list[dict | None] = [None] * len(script)
    свои: list[list[dict]] = [[] for _ in script]
    точные = [True] * len(script)
    for k, j in enumerate(хозяин):
        if куски[k] is None:
            точные[j] = False
            continue
        свои[j].append(куски[k])
        точные[j] = точные[j] and куски[k]["kind"] == "exact"

    exact = 0
    for j, части_слова in enumerate(свои):
        if not части_слова:
            continue
        p = [ч.get("p") for ч in части_слова if ч.get("p") is not None]
        spans[j] = {"start": min(ч["start"] for ч in части_слова),
                    "end": max(ч["end"] for ч in части_слова),
                    "kind": "exact" if точные[j] else "spread",
                    "p": min(p) if p else None}
        exact += 1 if точные[j] else 0

    _interpolate(spans)
    if any(span is None for span in spans):   # заполняются все или ни одного
        return [], 0.0
    return list(spans), exact / len(script)


# Знаки, внутри слова не рвущие его для человека, но рвущие для
# распознавания: дефис и апостроф. Ровно те же, что в определении слова.
_ЧАСТИ = re.compile(r"[-'’]")


def _части(слово: str) -> list[str]:
    куски = [ч for ч in _ЧАСТИ.split(слово) if ч]
    return куски or [слово]


def _по_частям(heard: list[dict]) -> list[dict]:
    """Услышанные слова, разобранные по дефису.

    Время куска делится между частями пропорционально длине: у слова,
    слепленного распознаванием из двух («мертвых-мертвых»), каждая
    половина получает свою половину времени, а не всё окно целиком.
    """
    вышло = []
    for w in heard:
        куски = _части(w["word"])
        if len(куски) == 1:
            вышло.append(w)
            continue
        всего = sum(len(ч) for ч in куски)
        при = float(w["start"])
        длина = float(w["end"]) - при
        for ч in куски:
            шаг = длина * len(ч) / всего if всего else 0.0
            вышло.append({"word": ч, "start": при, "end": при + шаг,
                          "p": w.get("p")})
            при += шаг
    return вышло


def _spread(spans, script, j1: int, j2: int, start: float, end: float) -> None:
    """Растянуть спорный участок по словам пропорционально их длине."""
    weights = [max(len(script[j]), 1) for j in range(j1, j2)]
    total = sum(weights)
    at = start
    for offset, weight in enumerate(weights):
        step = (end - start) * weight / total
        spans[j1 + offset] = {"start": at, "end": at + step, "kind": "spread"}
        at += step


def _interpolate(spans: list[dict | None]) -> None:
    """Заполнить дыры: слева, справа и между известными точками."""
    known = [i for i, s in enumerate(spans) if s is not None]
    if not known:
        return
    first, last = known[0], known[-1]
    for i in range(first):
        at = spans[first]["start"]
        spans[i] = {"start": at, "end": at, "kind": "edge"}
    for i in range(last + 1, len(spans)):
        at = spans[last]["end"]
        spans[i] = {"start": at, "end": at, "kind": "edge"}
    for left, right in zip(known, known[1:]):
        gap = right - left - 1
        if gap <= 0:
            continue
        start, end = spans[left]["end"], spans[right]["start"]
        step = (end - start) / (gap + 1)
        for k in range(gap):
            at = start + step * k
            spans[left + 1 + k] = {"start": at, "end": at + step, "kind": "gap"}


def exchange(script_text: str, spans: list[dict], duration_ms: int,
             *, с_уверенностью: bool = False) -> list[dict]:
    """Слова в том виде, в каком они лягут на диск: `{"w", "s", "e", "a"}`.

    `a` стоит **только у слов, время которых не измерено**. Нет ключа —
    время своё; так файл остаётся коротким, а «измеренное» видно сразу,
    без сравнения с чем-либо.

    `p` — уверенность распознавания, и она пишется ТОЛЬКО когда текст
    взят из расшифровки. Со сценарием сомнение другое: слово известно
    точно, неизвестно его время, и про это говорит `a`. Без сценария
    наоборот: время измерено у каждого слова, а вот то ли это слово —
    неизвестно. **Одна колонка, два смысла, и смысл называется вслух**
    списком фраз; писать оба сразу значит показать человеку две
    надёжности и не сказать, какая из них про его беду.

    Форма берётся из сценария, а не из распознавания: имена
    и пунктуация авторские. Не сошлось число слов с числом времён —
    форму не выдумываем и отдаём пусто: молча подставить не то слово
    хуже, чем не отдать ничего.
    """
    surface = surfaces(script_text)
    if len(surface) != len(spans):
        return []
    limit = duration_ms / 1000 if duration_ms else None
    out = []
    for word, span in zip(surface, spans):
        start = max(span["start"], 0.0)
        end = max(span["end"], start)
        if limit is not None:
            start, end = min(start, limit), min(end, limit)
        item = {"w": word, "s": round(start, 3), "e": round(end, 3)}
        if span.get("kind") != "exact":
            item["a"] = span.get("kind") or "gap"
        if с_уверенностью and span.get("p") is not None:
            item["p"] = round(float(span["p"]), 2)
        out.append(item)
    return out


def build_timing(script_text: str, heard: list[dict], duration_ms: int,
                 *, с_уверенностью: bool = False) -> dict:
    """Карта предложений по времени, пословные времена и доля совпавших.

    Два продукта из одного счёта, и считаются они по одним и тем же
    временам — поэтому разъехаться не могут.
    """
    lines = sentences(script_text)
    per_sentence = [words(line) for line in lines]
    flat = [w for line in per_sentence for w in line]
    if not flat:
        return {"timing": [], "words": [], "matched": 0.0,
                "note": "the text has no words"}

    spans, matched = map_words(flat, heard)
    if not spans:
        return {"timing": [], "words": [], "matched": 0.0,
                "note": "transcribing heard no words"}

    timing = []
    at = 0
    previous_end = 0
    for index, (line, line_words) in enumerate(zip(lines, per_sentence)):
        if not line_words:
            continue
        chunk = spans[at:at + len(line_words)]
        at += len(line_words)
        start = int(round(chunk[0]["start"] * 1000))
        end = int(round(chunk[-1]["end"] * 1000))
        # Границы не идут назад и не вылезают за длительность.
        start = max(start, previous_end)
        end = max(end, start)
        if duration_ms:
            start, end = min(start, duration_ms), min(end, duration_ms)
        previous_end = end
        timing.append({"index": index, "text": line,
                       "start_ms": start, "end_ms": end})

    spoken = exchange(script_text, spans, duration_ms,
                      с_уверенностью=с_уверенностью)
    note = "" if spoken else "word forms did not match their timings — not returned"
    return {"timing": timing, "words": spoken,
            "matched": round(matched, 3), "note": note}


# ─── распознавание ───────────────────────────────────────────────────

def transcribe(path: Path, *, on_download=None,
               on_progress=None) -> tuple[list[dict], str]:
    """Услышанные слова с временами и текст, каким его услышала машина.

    **Текст отдаётся вторым значением, а не выбрасывается.** У кого есть
    сценарий, тому этот текст не нужен: правильным считается сценарий.
    У кого сценария нет — этот текст И ЕСТЬ сценарий, другого взять
    неоткуда.

    Складывается он из тех же самых слов, которые отдаются первым
    значением, — не из отдельного «текста отрезка», который
    распознавание тоже умеет отдавать. Причина простая: тогда текст
    и слова приходят из одного источника и разойтись не могут.
    Разошлись бы — укладка легла бы на текст, которого в списке слов
    нет, и промах прошёл бы молча.

    **Модель качается при первом запуске**, и об этом говорится ДО, а
    не во время: `small` весит около 460 МБ, и молчащая программа
    в этот момент выглядит зависшей. «Из коробки» честно значит
    «из коробки, но первый раз подождите».

    Видеоядро Apple движок распознавания не умеет, поэтому `cpu`.
    На машине с видеокартой NVIDIA правильный ответ другой — записано
    в TODO.md, чтобы его не решали походя.
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise VertcutError(
            "faster-whisper is not installed — cannot transcribe",
            hint="install the dependencies: pip install -e . -c constraints.txt",
        ) from None

    # Сперва — только из кэша. Без этого huggingface_hub при КАЖДОМ
    # разборе спрашивает сайт, не вышла ли модель новее (замер 27-й
    # сессии: одно соединение с huggingface.co на разбор), а README
    # обещает, что после первого раза разбор в сеть не ходит. Модели
    # в кэше нет — тогда обычная загрузка, и о ней сказано заранее.
    try:
        model = WhisperModel(tuning.WHISPER_MODEL, device="cpu",
                             compute_type=tuning.WHISPER_COMPUTE,
                             local_files_only=True)
    except Exception:              # noqa: BLE001 — нет в кэше: качаем
        if on_download:
            on_download(tuning.WHISPER_MODEL)
        model = WhisperModel(tuning.WHISPER_MODEL, device="cpu",
                             compute_type=tuning.WHISPER_COMPUTE)
    segments, _ = model.transcribe(
        str(path),
        language=tuning.WHISPER_LANGUAGE or None,
        beam_size=tuning.WHISPER_BEAM,
        word_timestamps=True,
        # Тишину режем сами и по своим правилам: автоматика вырезает
        # куски звука и двигает времена, а времена здесь — главное.
        vad_filter=False,
    )
    # Куски приходят по мере того, как движок их слышит: `segments` —
    # это не список, а поток. Отсюда единственный честный процент
    # во всём разборе — время конца последнего услышанного куска.
    куски = []
    for segment in segments:
        for word in segment.words or []:
            куски.append((word.word, float(word.start), float(word.end),
                          round(float(word.probability), 3)))
        if on_progress:
            on_progress(float(segment.end))
    текст, места = _собрать_текст(куски)
    return _услышанные_слова(текст, места), текст


def _собрать_текст(куски: list[tuple]) -> tuple[str, list[tuple]]:
    """Слова распознавания обратно в текст — и где какое в нём лежит.

    Слово приходит вместе с ведущим пробелом и прилипшим знаком
    препинания, то есть текст складывается простой склейкой, без
    догадок о том, где ставить пробел.

    Переносов строк не ставится ни одного, и это решение. Абзац здесь
    взять неоткуда: пауза в разговоре бывает и посреди предложения,
    и рвать по ней значит выдумывать границу, которой человек
    не делал. Границы предложений остаются на знаках препинания —
    ровно там, где их расслышала машина.

    Места нужны, чтобы времена потом раздались словам ТЕКСТА, а не
    кускам, на которые его покрошило распознавание.
    """
    текст = ""
    места = []
    for сырое, начало, конец, p in куски:
        кусок = re.sub(r"\s+", " ", сырое)
        if not текст or текст.endswith(" "):
            кусок = кусок.lstrip()
        if not кусок:
            continue
        места.append((len(текст), len(текст) + len(кусок), начало, конец, p))
        текст += кусок
    return текст.rstrip(), места


def _услышанные_слова(текст: str, места: list[tuple]) -> list[dict]:
    """Слова текста с временами. Слово здесь — то же, что и везде.

    **Времена раздаются словам ТЕКСТА, а не кускам распознавания,
    и это починка настоящей ошибки.** Распознавание отдаёт «какая»
    и «-то» двумя кусками, а человек и весь остальной проект считают
    это одним словом. Пока времена лежали на кусках, такое слово
    не совпадало само с собой: текст говорил одно слово, список времён
    — два, и укладка отдавала ему ПРИКИНУТОЕ время вместо измеренного.

    Замер на интервью: 53 слова из 2215 — все дефисные. Мелочь
    по числу, но она превращала строчку «времена измерены у всех слов»
    во враньё, а таких строчек в сервисе быть не должно.

    Слово, собранное из нескольких кусков, берёт начало первого
    и конец последнего. Уверенность — САМОГО СОМНИТЕЛЬНОГО из них:
    в «какая-то» ошибиться можно любой половиной.
    """
    вышло = []
    курсор = 0
    for match in WORD_RE.finditer(текст):
        # Места идут по тексту слева направо, и слова тоже: курсор
        # не отматывается назад. Иначе два часа подкаста считались бы
        # перебором каждого слова по всем кускам.
        while курсор < len(места) and места[курсор][1] <= match.start():
            курсор += 1
        свои = []
        n = курсор
        while n < len(места) and места[n][0] < match.end():
            свои.append(места[n])
            n += 1
        имя = words(match.group(0))
        if not свои or not имя:
            continue
        вышло.append({"word": имя[0],
                      "start": min(м[2] for м in свои),
                      "end": max(м[3] for м in свои),
                      "p": min(м[4] for м in свои)})
    return вышло

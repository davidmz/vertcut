"""Вызов ffmpeg: хвост stderr при падении и ручка на отмену.

Своя дорога к внешней команде, а не чужая. У Нарезатора её не было
вовсе — он звал `run` из соседнего проекта, и это одна из тех ниток,
из-за которых его сегодня нельзя раздать.

**Почему `Popen`, а не `subprocess.run`.** Ручка процесса нужна снаружи:
«Отменить» обязано погасить ffmpeg СВОЕЙ работы, а не любой. Живые
процессы разложены по потокам — у каждой фоновой работы поток свой,
и `stop_thread()` гасит ровно её. `subprocess.run` ручку наружу
не отдаёт.

**Почему не `pkill ffmpeg`.** На машине человека может идти чужой
ffmpeg — своя запись экрана, чужая программа. Гасить надо своих детей
по номеру, а не всех по имени.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
from contextlib import contextmanager

from .errors import VertcutError

# Живые подпроцессы, разложенные по потокам.
_live: dict[int, set] = {}
_live_lock = threading.Lock()


@contextmanager
def tracked(proc: subprocess.Popen):
    """Пока команда работает, её видно снаружи — и можно погасить."""
    ident = threading.get_ident()
    with _live_lock:
        _live.setdefault(ident, set()).add(proc)
    try:
        yield proc
    finally:
        with _live_lock:
            live = _live.get(ident)
            if live is not None:
                live.discard(proc)
                if not live:
                    _live.pop(ident, None)


def stop_thread(ident: int) -> int:
    """Погасить подпроцессы этого потока. Возвращает сколько.

    По SIGTERM ffmpeg сворачивается сам. Недописанный файл остаётся
    на диске куском — по нему и видно, что сборку прервали; штамп
    «готово» при этом не выставлен, потому что он пишется только после
    проверки, и следующий запуск соберёт заново, а не переступит битое.
    """
    with _live_lock:
        procs = list(_live.get(ident) or ())
    for proc in procs:
        try:
            proc.terminate()
        except OSError:
            pass                # уже умер сам, пока мы сюда шли
    return len(procs)


# Имя программы ищется в PATH, а не пишется путём.
#
# Нарезатор жил на одной машине, и там ffmpeg всегда лежал в одном
# месте. Здесь машина чужая: у одного он от Homebrew, у другого
# от MacPorts, у третьего в папке рядом с программой, а на Windows
# в `Program Files`. Абсолютный путь в коде означал бы, что сервис
# не работает у всех, кроме автора.
FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"


def _start(cmd: list[str], text: bool) -> subprocess.Popen:
    # Имя программы превращается в путь ЗДЕСЬ, в одном месте.
    #
    # Иначе выходит половина починки: `where` знает, что своя копия
    # ffmpeg лежит рядом с сервисом, а десяток мест по всему коду
    # запускают голое слово «ffmpeg», которого в PATH нет. Проверка
    # окружения при этом говорит «всё на месте» — она спрашивает
    # `where`, — а первая же настоящая команда падает.
    #
    # Поймано сквозным прогоном на чистой учётной записи, вторым
    # заходом: первый нашёл, что путь не ищется вовсе.
    cmd = [where(cmd[0]) or cmd[0], *cmd[1:]]
    try:
        return subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=text)
    except FileNotFoundError:
        raise VertcutError(
            f"Could not find the program {cmd[0]}",
            hint=need_hint(cmd[0]),
        ) from None


def need_hint(binary: str) -> str:
    """Что сказать человеку, у которого нет ffmpeg.

    Подсказка разная на разных системах: одна и та же строчка
    «brew install ffmpeg» на Windows выглядит издевательством.
    """
    import sys
    if sys.platform == "darwin":
        return f"install it with: brew install {binary.split('/')[-1]}"
    if sys.platform.startswith("win"):
        return ("download ffmpeg from https://ffmpeg.org/download.html "
                "and add its folder to PATH")
    return "install the ffmpeg package with your system's package manager"


def открыть_поток(cmd: list[str]) -> subprocess.Popen:
    """Запустить команду и читать её вывод по ходу, а не целиком.

    Заведено для метрики склеек: развернуть двадцатиминутную копию
    в память — это двадцать гигабайт, а нужен всегда один кадр.

    Отличие от `run` в одном: ответа никто не ждёт. Значит и падение
    ловится не здесь, а тем, кто читает: у него по короткому чтению
    видно, что кадры кончились.
    """
    return _start(cmd, text=False)


def run_с_ходом(cmd: list[str], всего: float, ход,
                *, считать: str = "секунды") -> None:
    """Тот же запуск, но ffmpeg по дороге рассказывает, сколько сделал.

    **Число здесь настоящее, а не прикидка от времени.** Правило пакета
    дизайна — полоса рисуется только там, где процент известен
    по-настоящему, — и у кодирования он известен: ffmpeg сам говорит,
    до какой секунды ролика дошёл. Считать долю от ожидаемого времени
    значило бы показывать 90% у сборки, которая идёт вторую минуту
    сверх плана.

    `считать` — чем меряем: «секунды» (сколько ролика закодировано)
    или «кадры» (сколько кадров записано). Слой субтитров меряется
    кадрами: секунд у него столько же, сколько у ролика, а вот кадр —
    это ровно то, что он в этот момент пишет.

    **stderr вычерпывается своим потоком, и это не осторожность.**
    Труба у него не бездонная: наполнилась — и ffmpeg встаёт на записи,
    а мы стоим на чтении его stdout. Оба ждут друг друга, и сборка
    висит навсегда.
    """
    ключ = "out_time_us" if считать == "секунды" else "frame"
    делить = 1_000_000.0 if считать == "секунды" else 1.0
    # `-progress` и `-nostats` — общие слова, и стоят они сразу после
    # имени программы. Дописать их в конец нельзя: там живёт выходной
    # файл, а у ffmpeg порядок слов — часть смысла.
    proc = _start([cmd[0], "-progress", "pipe:1", "-nostats", *cmd[1:]],
                  text=True)
    хвост: list[str] = []
    качалка = threading.Thread(target=_вычерпать, args=(proc.stderr, хвост),
                               daemon=True)
    качалка.start()
    with tracked(proc):
        for строка in proc.stdout:
            имя, _, значение = строка.strip().partition("=")
            if имя != ключ:
                continue
            значение = значение.strip()
            if not значение.isdigit():
                continue        # «N/A» — ffmpeg ещё не начал считать
            ход(min(int(значение) / делить, всего), всего)
        proc.wait()
    качалка.join(timeout=2)
    if proc.returncode != 0:
        tail = "\n".join("".join(хвост).strip().splitlines()[-12:])
        raise VertcutError(
            f"A command failed:\n  {' '.join(cmd[:6])} ...\n\n{tail}")


def _вычерпать(поток, куда: list[str]) -> None:
    """Читать трубу до конца, чтобы пишущий в неё не встал."""
    try:
        for строка in поток:
            куда.append(строка)
    except (ValueError, OSError):
        pass                    # труба закрыта — процесса больше нет


def run(cmd: list[str], want_stderr: bool = False) -> str:
    """Запуск команды. При падении показывает хвост stderr.

    Хвост, а не всё: ffmpeg на падении печатает сотни строк про потоки,
    и нужное лежит в последних. Показать всё — то же самое, что
    не показать ничего.
    """
    proc = _start(cmd, text=True)
    with tracked(proc):
        out, err = proc.communicate()
    if proc.returncode != 0:
        tail = "\n".join(err.strip().splitlines()[-12:])
        raise VertcutError(
            f"A command failed:\n  {' '.join(cmd[:6])} ...\n\n{tail}")
    return err if want_stderr else out


def run_bytes(cmd: list[str]) -> bytes:
    """То же, но вывод забирается байтами.

    Нужно там, где ffmpeg отдаёт в трубу не текст, а кадры.
    """
    proc = _start(cmd, text=False)
    with tracked(proc):
        out, err = proc.communicate()
    if proc.returncode != 0:
        tail = "\n".join(err.decode("utf-8", "replace")
                         .strip().splitlines()[-12:])
        raise VertcutError(
            f"A command failed:\n  {' '.join(cmd[:6])} ...\n\n{tail}")
    return out


def where(binary: str) -> str | None:
    """Где лежит программа. None — значит нет.

    **Сперва PATH, потом своя копия рядом с сервисом.** Правило «ffmpeg
    ищется в PATH, а не пишется путём» в силе: абсолютного пути здесь
    по-прежнему нет ни одного, а «рядом с собой» — это то же самое
    правило, по которому сервис находит свой обвес.

    Порядок именно такой, а не обратный: установка качает свою копию
    ТОЛЬКО тогда, когда в системе ffmpeg не нашлось. Поставил человек
    свой позже — пусть работает его.

    **Поймано сквозным прогоном на чистой учётной записи.** Установка
    честно скачала ffmpeg рядом с сервисом, а сервис его не видел:
    в PATH его нет и быть не может. Разбор упал бы на первой стадии
    словами «не нашёл программу ffmpeg» — у человека, у которого она
    только что скачалась.
    """
    нашлось = shutil.which(binary)
    if нашлось:
        return нашлось
    from . import layout
    своя = layout.программа()
    if своя:
        рядом = своя / "ffmpeg" / binary
        if рядом.exists() and os.access(рядом, os.X_OK):
            return str(рядом)
        рядом = рядом.with_suffix(".exe")
        if рядом.exists():
            return str(рядом)
    return None


def need(binary: str) -> None:
    if shutil.which(binary) is None:
        raise VertcutError(f"Could not find the program {binary}",
                           hint=need_hint(binary))

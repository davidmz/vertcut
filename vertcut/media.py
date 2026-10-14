"""Видео: замер, отпечаток, снятая дорожка, уменьшенная копия, кадры.

**Отпечаток — весь файл, а не кусок.** Замер: 3.4 ГБ считаются
за 10 секунд. Отпечаток по началу и концу был бы быстрее, но
пересведённое видео той же длины отличается серединой, и такой
отпечаток не отличил бы его.

**Дорожка и копия снимаются одним проходом.** Декодирование —
самая дорогая часть, и делать его дважды незачем: замер показал
2 мин 41 с на проход, второй стоил бы столько же.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from . import tuning
from .errors import VertcutError
from .run import FFMPEG, FFPROBE, run, tracked, открыть_поток

# Частота, на которой обучены модели распознавания. Не калибровка —
# требование модели.
WHISPER_RATE = 16000

# Сколько читать за раз при подсчёте отпечатка. 8 МБ: меньше — лишние
# обращения к диску, больше — лишняя память ни за чем.
_CHUNK = 8 * 1024 * 1024


def _ffprobe(path: Path) -> dict:
    try:
        out = run([
            FFPROBE, "-v", "error", "-print_format", "json",
            "-show_format", "-show_streams", str(path),
        ])
    except VertcutError as exc:
        raise VertcutError(
            f"Could not read the video: {path}\n\n{exc.message}",
            hint=exc.hint,
        ) from None
    return json.loads(out)


def probe(path: Path) -> dict:
    """Длительность, размер кадра, частота кадров, кодек."""
    if not path.exists():
        raise VertcutError(f"No such file: {path}")
    data = _ffprobe(path)
    video = next((s for s in data.get("streams", ())
                  if s.get("codec_type") == "video"), None)
    audio = next((s for s in data.get("streams", ())
                  if s.get("codec_type") == "audio"), None)
    if video is None:
        raise VertcutError(f"The file has no video track: {path}")
    if audio is None:
        raise VertcutError(
            f"The file has no audio track: {path}",
            hint="analysis matches words to the sound — without sound "
                 "there is nothing to do",
        )
    duration = float(data.get("format", {}).get("duration") or 0.0)
    if duration <= 0:
        raise VertcutError(f"The file is zero seconds long: {path}")
    num, _, den = (video.get("r_frame_rate") or "25/1").partition("/")
    fps = float(num) / float(den or 1)
    return {
        "duration": round(duration, 3),
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "fps": round(fps, 4),
        "codec": video.get("codec_name") or "",
    }


def размер_кадра(path: Path) -> tuple[int, int]:
    """Ширина и высота. Отдельно от `probe`, и не для порядка.

    `probe` требует звуковой дорожки — и правильно делает: разбор
    кладёт слова на звук. А уменьшенная копия снимается БЕЗ звука
    (`-an`), и спросить у неё размер кадра через `probe` нельзя вовсе.
    """
    видео = next((s for s in _ffprobe(path).get("streams", ())
                  if s.get("codec_type") == "video"), None)
    if видео is None:
        raise VertcutError(f"The file has no video track: {path}")
    return int(видео.get("width") or 0), int(видео.get("height") or 0)


# Как просить у ffmpeg кадры для метрики склеек.
#
# **Эти слова — замер, а не вкус.** Метрика склеек раньше считалась
# библиотекой поверх opencv, и порог 35 замерен ИМЕННО на её числах.
# Уходя от opencv, надо было получить те же числа, а один и тот же файл
# ffmpeg и opencv разбирают по-разному: у них разный перевод из
# телевизионного цвета в экранный.
#
# Перебор: как есть — расхождение 1.88 из 255 в среднем; матрица 601 —
# 1.23; она же с точным округлением — **0.085**. Дальше не идёт: opencv
# переводит цвет своим кодом, а не средствами ffmpeg. Проверено и то,
# что дальше не помогает: сглаживание, побитовая точность, полный
# и узкий диапазон — ни одно из них числа не двигает.
#
# Остаточные 0.085 закрыты не подгонкой, а замером результата: границы
# планов сошлись все до одной на четырёх видео, 70 тысяч кадров.
_ЦВЕТ_ДЛЯ_СКЛЕЕК = "scale=in_color_matrix=bt601:flags=bicubic+accurate_rnd"


def поток_кадров(path: Path, ш: int, в: int):
    """Кадры подряд, сырыми байтами: три байта на точку.

    Отдаются БАЙТАМИ, а не числовыми таблицами: разбор чисел — работа
    метрики, а здесь живёт разговор с ffmpeg.

    Читается ровно по кадру за раз. Целиком в память такое не берут:
    двадцать минут копии — это двадцать гигабайт, если развернуть.
    """
    сколько = ш * в * 3
    процесс = открыть_поток([
        FFMPEG, "-v", "error", "-i", str(path),
        "-vf", _ЦВЕТ_ДЛЯ_СКЛЕЕК,
        "-f", "rawvideo", "-pix_fmt", "bgr24", "-",
    ])
    try:
        with tracked(процесс):
            while True:
                сырьё = процесс.stdout.read(сколько)
                if len(сырьё) < сколько:
                    break
                yield сырьё
    finally:
        процесс.stdout.close()
        if процесс.poll() is None:
            процесс.terminate()
        процесс.wait()


def fingerprint(path: Path) -> str:
    """Отпечаток файла целиком. Подменили видео под тем же именем — видно."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def extract(source: Path, audio_dst: Path, proxy_dst: Path) -> None:
    """Снять дорожку и уменьшенную копию — одним проходом.

    Дорожка кладётся моно 16 кГц: на этой частоте обучено распознавание,
    и отдавать ему больше значит заставить его пересчитывать самому.
    Для сборки роликов эта дорожка не используется — там звук берётся
    из исходника, где он не тронут.

    Ширина копии считается ЧЁТНОЙ автоматически (`-2`): у h264 размер
    обязан делиться на два, а исходники бывают любой высоты.
    """
    audio_dst.parent.mkdir(parents=True, exist_ok=True)
    run([
        FFMPEG, "-v", "error", "-y", "-i", str(source),
        "-map", "0:v:0",
        "-vf", f"scale={tuning.PROXY_WIDTH}:-2",
        "-c:v", "libx264", "-crf", str(tuning.PROXY_CRF),
        "-preset", "veryfast", "-pix_fmt", "yuv420p", "-an",
        str(proxy_dst),
        "-map", "0:a:0", "-ac", "1", "-ar", str(WHISPER_RATE),
        "-c:a", "pcm_s16le", str(audio_dst),
    ])


# Четверть кадра назад — столько отступаем, прося кадр по номеру.
#
# `-ss` отдаёт ПЕРВЫЙ кадр, чьё время не меньше заданного. Значит просить
# надо чуть раньше самого кадра, но заметно позже предыдущего. Ровно
# на времени кадра просить нельзя: это сравнение двух чисел с плавающей
# точкой на точное равенство, то есть монетка.
#
# Половина была бы серединой между кадрами и давала бы СЛЕДУЮЩИЙ кадр.
# В Нарезаторе так и было пять сессий подряд: обе стороны сверки
# промахивались одинаково, и потому это было не видно — пока у самой
# склейки лишний кадр не оказался другой сценой, и сверка не начала
# ругаться на исправные файлы.
#
# Правило одно на всех, и это главное в нём. Два места, считающие время
# кадра по-своему, разъедутся молча.
ЧЕТВЕРТЬ = 0.25


def frame_time(n: int, fps: float, смещение: float = 0.0) -> float:
    """Какое время просить, чтобы получить кадр номер `n`."""
    return round(смещение + (n - ЧЕТВЕРТЬ) / fps, 4)


_ПОСЛЕДНИЙ: dict[tuple, float | None] = {}


def последний_кадр(path: Path) -> float | None:
    """Время, которое просить, чтобы получить ПОСЛЕДНИЙ кадр картинки.

    **Картинка бывает короче файла, и это не поломка файла.** Длина
    файла — это длина самой долгой дорожки, а звук часто тянется чуть
    дольше видео. Замер на живом видео: картинка 802.720 с, звук
    и файл 802.783. Последний план кончается на длине файла, и просьба
    о кадре на 802.690 приходит туда, где кадров нет вовсе: ffmpeg
    не отдаёт ничего и падает словами про кодировщик jpeg — «Non
    full-range YUV is non-standard», — то есть ровно не про то.

    Нет длины у самой дорожки (у mkv её кладут тегом, а бывает,
    что никуда) — `None`: обрезать тогда нечем, и просьба уходит как есть.

    Помнится вместе с отметкой файла: экран живёт часами.
    """
    try:
        отметка = path.stat()
    except OSError:
        return None
    ключ = (str(path), отметка.st_mtime_ns, отметка.st_size)
    if ключ in _ПОСЛЕДНИЙ:
        return _ПОСЛЕДНИЙ[ключ]
    видео = next((s for s in _ffprobe(path).get("streams", ())
                  if s.get("codec_type") == "video"), None)
    ответ = None
    if видео is not None:
        длина = видео.get("duration")
        if not длина:
            # mkv: «00:13:22.720000000» тегом
            тег = (видео.get("tags") or {}).get("DURATION", "")
            ч, _, остаток = тег.partition(":")
            м, _, с = остаток.partition(":")
            try:
                длина = int(ч) * 3600 + int(м) * 60 + float(с)
            except ValueError:
                длина = None
        num, _, den = (видео.get("r_frame_rate") or "").partition("/")
        try:
            fps = float(num) / float(den or 1)
            начало = float(видео.get("start_time") or 0)
            длина = float(длина)
        except (TypeError, ValueError, ZeroDivisionError):
            длина = None
        if длина and fps > 0:
            последний = max(0, round(длина * fps) - 1)
            ответ = frame_time(последний, fps, начало)
    _ПОСЛЕДНИЙ[ключ] = ответ
    return ответ


def _не_дальше_картинки(source: Path, at: float) -> float:
    предел = последний_кадр(source)
    return min(at, предел) if предел is not None else at


def grab_run(source: Path, at: float, count: int, into: Path,
             width: int) -> list[Path]:
    """Подряд идущие кадры с одного места. Один поиск на всю ленту.

    Нужно сверке: кадр из готового файла и кадр из исходника на той же
    секунде ложатся на соседние кадры — поиск по сжатому видео встаёт
    на ближайший, а «ближайший» у HEVC и у H.264 разный. На плане
    с быстрым движением соседние кадры непохожи, и сверка ругалась бы
    на исправный файл.
    """
    into.mkdir(parents=True, exist_ok=True)
    at = _не_дальше_картинки(source, at)
    run([
        FFMPEG, "-v", "error", "-y",
        "-ss", f"{max(at, 0):.3f}", "-i", str(source),
        "-frames:v", str(count), "-q:v", "2",
        "-vf", f"scale={width}:-2", str(into / "%03d.jpg"),
    ])
    out = sorted(into.glob("*.jpg"))
    if not out:
        raise VertcutError(
            f"ffmpeg returned no frames from {at:.2f} s of {source.name}")
    return out


def grab_frames(source: Path, times: list[float], into: Path,
                width: int, on_tick=None) -> list[Path]:
    """Вынуть кадры в перечисленные моменты. Возвращает пути по порядку.

    **Поиск на каждый кадр, а не один проход с отбором.** Отбор одним
    выражением был бы дешевле, но выражение на четыреста моментов ffmpeg
    уже не разбирает — падает на нехватке памяти при сборке фильтра.
    Резать его на куски значит городить подпроходы с пересчётом времён,
    и всё это ради экономии, которой нет: замер — 0.28 с на кадр.

    Кадр, который ffmpeg не отдал, — это ошибка, а не пропуск: дальше
    кадры разбираются по планам по порядку, и один недостающий сдвинул
    бы все остальные на чужие планы.
    """
    into.mkdir(parents=True, exist_ok=True)
    out: list[Path] = []
    for n, at in enumerate(times):
        at = _не_дальше_картинки(source, at)
        dst = into / f"{n:05d}.jpg"
        run([
            FFMPEG, "-v", "error", "-y",
            "-ss", f"{max(at, 0):.3f}", "-i", str(source),
            "-frames:v", "1", "-q:v", "2",
            "-vf", f"scale={width}:-2", str(dst),
        ])
        if not dst.exists() or not dst.stat().st_size:
            raise VertcutError(
                f"ffmpeg returned no frame at {at:.2f} s of {source.name}",
                hint="check that the file is not cut short",
            )
        out.append(dst)
        if on_tick and (n + 1) % 50 == 0:
            on_tick(n + 1, len(times))
    return out


def кадр_в_файл(source: Path, при: float, куда: Path,
                ширина: int) -> Path:
    """Один кадр — готовым файлом по имени `куда`. Своя времянка на вызов.

    **Времянка тут не мелочь исполнения, а заслон от гонки.** Экран
    многопоточный: браузер, открыв список планов, просит десяток кадров
    разом. Пока каждый вызов вынимал кадр в общую папку под именем,
    которое `grab_frames` даёт первому кадру (`00000.jpg`), десяток
    одновременных ffmpeg писали в ОДИН файл и затирали друг друга —
    и под номером плана оказывалась картинка соседа. Поймано живьём:
    у четырёх планов из шестнадцати кадр был чужой, а три файла
    (`big-0005`, `big-0006`, `big-0009`) оказались побайтово одним.

    **Времянка делается РЯДОМ с целью, а не в системной папке.**
    Переименование внутри одной файловой системы мгновенно и не
    оставляет полуфайла; через границу файловых систем оно падает
    вовсе, а разбор человек вправе держать на внешнем диске.
    """
    import tempfile

    куда.parent.mkdir(parents=True, exist_ok=True)
    работа = Path(tempfile.mkdtemp(prefix=".frame-", dir=куда.parent))
    try:
        вышло = grab_frames(source, [при], работа, ширина)
        if not вышло:
            raise VertcutError(
                f"ffmpeg returned no frame at {при:.2f} s of {source.name}")
        вышло[0].replace(куда)
        return куда
    finally:
        shutil.rmtree(работа, ignore_errors=True)


def кусок_звука(source: Path, при: float, сколько: float,
                частота: int = 22050) -> bytes:
    """Звук отрезка — послушать край куска до сборки.

    **WAV, а не сжатое, и это решение.** Сжимать нечем наверняка:
    `libmp3lame` есть не во всякой сборке ffmpeg — половину собирают
    без него из-за лицензии, — а сырой AAC потоком понимают не все
    браузеры. WAV играет везде и не требует от ffmpeg ничего, кроме
    того, что в нём есть всегда.

    Платим размером: восемьдесят секунд это около трёх мегабайт. Для
    сервиса, который живёт на этой же машине, это не цена вовсе —
    байты не идут никуда дальше памяти.

    **Моно и 22 кГц** — на слух это радио, и его хватает: слушают
    здесь не качество, а то, не обрублено ли слово на краю.

    `-ss` ПЕРЕД входом, а не после: так ffmpeg перематывает, а не
    декодирует всё до нужной секунды. На трёхгигабайтном файле разница
    между мгновенно и минутой.
    """
    import tempfile

    source = Path(source)
    if not source.exists():
        raise VertcutError(
            f"The file to listen to is missing: {source.name}",
            hint="the original was probably moved or renamed")
    работа = Path(tempfile.mkdtemp(prefix="vertcut-audio-"))
    куда = работа / "chunk.wav"   # не для человека: времянка
    try:
        run([FFMPEG, "-v", "error", "-y",
             "-ss", f"{max(при, 0):.3f}", "-t", f"{max(сколько, 0.05):.3f}",
             "-i", str(source), "-vn",
             "-ac", "1", "-ar", str(частота), "-c:a", "pcm_s16le",
             str(куда)])
        if not куда.exists() or not куда.stat().st_size:
            raise VertcutError("ffmpeg finished but returned no sound")
        return куда.read_bytes()
    finally:
        shutil.rmtree(работа, ignore_errors=True)

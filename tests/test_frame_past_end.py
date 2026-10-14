"""Кадр у самого конца файла, где картинка уже кончилась, а звук нет.

Найдено на живом видео автора: картинка 802.720 с, звук и файл 802.783.
Последний план кончается на длине файла, стадия рамок попросила кадр
на 802.690 — а кадров там нет вовсе. ffmpeg не отдал ничего и упал
словами про кодировщик jpeg («Non full-range YUV is non-standard»),
то есть совсем не про то. Девятиминутный разбор встал на последнем
из 897 кадров.
"""

from __future__ import annotations

import subprocess

from vertcut import media
from tests.test_shot_frames import ффмпег


def test_кадр_после_конца_картинки_берётся_последним(песочница):
    файл = песочница / "звук-длиннее.mp4"
    # Картинка 2 с, звук 2.5 с: файл длиннее картинки на полсекунды.
    subprocess.run([
        ффмпег(), "-v", "error", "-y",
        "-f", "lavfi", "-i", "color=c=blue:size=320x240:rate=25:duration=2",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=2.5",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        str(файл),
    ], check=True)

    assert media.probe(файл)["duration"] > 2.3
    последний = media.последний_кадр(файл)
    assert 1.9 < последний < 2.0

    вышло = media.grab_frames(файл, [1.0, 2.2, 2.45],
                              песочница / "кадры", 160)
    assert len(вышло) == 3
    assert all(p.stat().st_size for p in вышло)

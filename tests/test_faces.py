"""Детектор лиц и рамка кадра.

Качество самого детектора проверками не мерится — оно меряется прогоном
на настоящем материале, и замер записан в private/docs/sessions.md. Здесь
проверяется то, что можно проверить: арифметика окна, отсев повторов,
поставка модели и то, что мы не вернулись к тяжёлым чужим библиотекам.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

from vertcut import crop, faces, layout, tuning


# ─── модель в поставке ───────────────────────────────────────────────

def test_веса_лежат_в_поставке_и_с_лицензией():
    """230 КБ — качать их при первом запуске значит завести отказ
    «нет сети» там, где его могло не быть вовсе.

    Лицензия рядом обязательна: MIT разрешает раздачу и требует одного —
    приложить текст.
    """
    веса = layout.assets() / "models" / "yunet.onnx"
    лицензия = layout.assets() / "models" / "yunet-LICENSE.txt"
    assert веса.exists() and веса.stat().st_size > 100_000
    assert лицензия.exists()
    assert "MIT" in лицензия.read_text(encoding="utf-8")


def test_agpl_детектора_больше_нет_нигде():
    """Ради этого замена и делалась: AGPL заразна, и раздача с ней,
    скорее всего, обязывает открыть под той же лицензией всё остальное.
    """
    корень = layout.assets().parent / "vertcut"
    for файл in корень.glob("*.py"):
        текст = файл.read_text(encoding="utf-8").lower()
        строки = [с for с in текст.splitlines()
                  if "import" in с and not с.strip().startswith("#")]
        assert not any("ultralytics" in с or "torch" in с for с in строки), файл


def test_opencv_не_вернулся():
    """Убран замером, а не вкусом: 120 МБ поставки и два предупреждения
    при каждом запуске, которые чужой человек читает как поломку.
    Свой разбор ответа модели сошёлся с его разбором до 0.00 пикселя.
    """
    корень = layout.assets().parent / "vertcut"
    for файл in корень.glob("*.py"):
        строки = [с.strip() for с in файл.read_text(encoding="utf-8").splitlines()]
        assert not any(с.startswith("import cv2") or с.startswith("from cv2")
                       for с in строки), файл


# ─── арифметика окна ─────────────────────────────────────────────────

def test_окно_не_свисает_за_край_кадра():
    """Лицо у самого края даёт окно, прижатое к краю, и это правильно:
    оно всё равно попадёт в вертикаль, просто не по центру."""
    половина = crop.половина_окна(1920, 1080)
    assert crop.прижать(0.0, 1920, 1080) == pytest.approx(половина, abs=1e-4)
    assert crop.прижать(1.0, 1920, 1080) == pytest.approx(1 - половина, abs=1e-4)
    assert crop.прижать(0.5, 1920, 1080) == 0.5


def test_окно_считается_от_формы_кадра_а_не_от_1920():
    """Кадр однажды приедет 4K или 4:3, и подгонка под один размер даст
    кривое окно молча."""
    широкий = crop.половина_окна(3840, 2160)
    квадратный = crop.половина_окна(1440, 1080)
    assert широкий == pytest.approx(0.5625 / 2 * 2160 / 3840 * 3840 / 3840, abs=1e-6)
    assert квадратный > широкий


def test_берётся_самое_крупное_лицо():
    """Крупное лицо — это ближний план и, как правило, тот, кто говорит.
    Мелкие в глубине кадра тянуть окно на себя не должны."""
    лица = [{"x": 0, "y": 0, "w": 10, "h": 10, "балл": 0.9},
            {"x": 900, "y": 0, "w": 100, "h": 100, "балл": 0.7}]
    assert faces.самое_крупное(лица, 1000) == pytest.approx(0.95)


def test_лиц_нет_значит_центр():
    assert faces.самое_крупное([], 1000) is None


# ─── отсев повторов ──────────────────────────────────────────────────

def test_одно_лицо_не_считается_за_пять():
    """Модель находит одно лицо несколькими рамками сразу. Без отсева
    «самое крупное лицо» выбиралось бы из повторов одного и того же."""
    рамки = np.array([[100, 100, 50, 50], [102, 101, 49, 51], [700, 100, 60, 60]],
                     np.float32)
    баллы = np.array([0.9, 0.85, 0.8], np.float32)
    осталось = faces._отсеять_повторы(рамки, баллы, faces.НМС)
    assert len(осталось) == 2


# ─── детектор на настоящем кадре ─────────────────────────────────────

def test_детектор_отвечает_на_настоящем_кадре(tmp_path):
    """Проверка не про качество, а про то, что дорога цела: картинка
    читается, модель считается, ответ разбирается.

    Кадр рисуется здесь же — на нём лиц нет, и правильный ответ «пусто».
    Пустой ответ на пустой картинке это не заглушка: он проходит ровно
    тот же путь, что и настоящий.
    """
    from PIL import Image
    путь = tmp_path / "ровное.png"
    Image.new("RGB", (640, 360), (30, 30, 30)).save(путь)
    кадр = faces.прочитать(путь)
    assert кадр.shape == (360, 640, 3)
    assert faces.найти(кадр, tuning.FACE_CONF) == []


def test_кадр_любой_высоты_не_роняет_модель(tmp_path):
    """Сетка модели делится на 32, а кадры бывают любой высоты: 720
    на 32 не делится. Кадр добивается нулями справа и снизу — тогда
    координаты рамок остаются координатами исходного кадра."""
    from PIL import Image
    путь = tmp_path / "нечётное.png"
    Image.new("RGB", (1281, 721), (40, 50, 60)).save(путь)
    кадр = faces.прочитать(путь)
    faces.найти(кадр, tuning.FACE_CONF)   # не должно упасть


def test_порог_детектора_записан_с_замером():
    """Спека запрещает выдавать унаследованные числа за замеры.
    У этого числа замер свой, и он в файле."""
    from pathlib import Path
    текст = Path(tuning.__file__).read_text(encoding="utf-8")
    кусок = текст[текст.index("Порог уверенности детектора лиц"):]
    assert "382" in кусок, "не сказано, на чём мерялось"
    assert "РИСОВАННЫХ" in кусок, "не сказано, что живые лица не проверены"


def test_телеметрия_onnxruntime_выключена_до_импорта(tmp_path):
    """onnxruntime на macOS при импорте пишет событие для Microsoft
    и отправляет его (26-я сессия, `vertcut/__init__.py`). Проверяется
    настоящим процессом с чистым домом: после работы детектора папки
    телеметрии там быть не должно. Без выключателя она появляется
    уже от `import onnxruntime`."""
    import os
    import subprocess

    from vertcut import layout
    веса = next((Path(layout.__file__).parent / "assets" / "models").glob("*.onnx"))
    среда = dict(os.environ, HOME=str(tmp_path))
    среда.pop("ORT_DISABLE_TELEMETRY", None)
    код = ("import vertcut, os, onnxruntime as o;"
           f"o.InferenceSession(r'{веса}');"
           "print(os.environ['ORT_DISABLE_TELEMETRY'])")
    вышло = subprocess.run([sys.executable, "-c", код], env=среда,
                           capture_output=True, text=True)
    assert вышло.returncode == 0, вышло.stderr[-400:]
    assert вышло.stdout.strip() == "1"
    папка = tmp_path / "Library" / "Application Support" / "Microsoft"
    assert not папка.exists(), "onnxruntime завёл папку телеметрии"


def test_установщик_выключает_телеметрию_и_у_себя():
    """Установщик зовёт питон без пакета — загрузка модели импортирует
    onnxruntime мимо `vertcut/__init__.py`."""
    текст = (Path(__file__).resolve().parent.parent / "install"
             / "installer.py").read_text(encoding="utf-8")
    кусок = текст[текст.index("def download_model"):]
    кусок = кусок[:кусок.index("\ndef ")]
    assert 'ORT_DISABLE_TELEMETRY="1"' in кусок
    assert 'HF_HUB_DISABLE_TELEMETRY="1"' in кусок
    assert "env=environment" in кусок


def test_телеметрия_hugging_face_выключена():
    """Замер 27-й сессии: huggingface_hub раз в сутки шлёт свою
    телеметрию. Выключатель — в пакете, до всякого импорта."""
    import os
    import subprocess

    среда = dict(os.environ)
    среда.pop("HF_HUB_DISABLE_TELEMETRY", None)
    вышло = subprocess.run(
        [sys.executable, "-c",
         "import vertcut, os; print(os.environ['HF_HUB_DISABLE_TELEMETRY'])"],
        env=среда, capture_output=True, text=True)
    assert вышло.stdout.strip() == "1", вышло.stderr[-300:]

"""Иконка, которая запускает сервис ИЗ ЭТОЙ ПАПКИ, а не из установки.

    python install/build-dev-launcher.py            — «Vertcut (dev)», для того, кто правит
    python install/build-dev-launcher.py --plain    — «Vertcut», для того, кто поставил
                                                      из исходников и просто работает

## Два имени, одна иконка

Человек, поставивший сервис из клона по `INSTALL.md`, тоже получает
иконку отсюда: это та же задача — поднять ЭТУ папку, ничего не ставя.
Ему слово «dev» ничего не говорит, и с 26-й сессии есть `--plain`:
имя «Vertcut», свой идентификатор свёртка. Разница только в имени
и идентификаторе — исполняемый файл один на оба, второго не заводится.

**Собранная на месте иконка открывается без предупреждений.** Метку
«скачано из интернета» ставит скачавшая программа (браузер, почта),
а не система; иконку, написанную на диск этим файлом, никто не скачивал.
Проверено в 26-й: у собранной нет атрибута `com.apple.quarantine`,
а Gatekeeper спрашивает только о помеченных им файлах.

## Зачем она отдельно от раздачи

Раздача (`build-release.py`) даёт человеку иконку, которая при первом
щелчке СТАВИТ программу: скачивает питон, ffmpeg и модель, кладёт всё
в «Application Support». Это верно для того, кому сервис отдали.

Тому, кто сервис ПРАВИТ, нужно обратное: щелчок должен поднимать
ту самую рабочую копию, которую он только что менял. Поставленная
программа этого не умеет и не должна — её код заморожен на дне сборки,
и правки в неё не доезжают. Две иконки живут рядом мирно: настройки
(`~/.vertcut`) и разборы (`~/vertcut`) у них общие, а код разный,
и разница видна по имени.

## Чего здесь нет

**Установки.** Если окружения в папке нет, иконка говорит об этом
словами и не начинает ничего скачивать: рабочую копию человек собирает
сам, и делать это за него молча — значит однажды переписать ему то,
над чем он работал.

**Своего механизма «сервис уже работает».** Он один на весь проект
и живёт в `vertcut screen --exit-with-icon`: тот сам находит хозяина,
открывает его вкладку и уходит. Второй такой разъехался бы с первым
молча.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ЗДЕСЬ = Path(__file__).resolve().parent
КОРЕНЬ = ЗДЕСЬ.parent

# «Проект» в имени свёртка видит только система; поменять его —
# и macOS сочтёт иконку автора новой программой. не для человека
#
# У `--plain` идентификатор свой и латиницей: это другая программа для
# системы, и у человека она может жить рядом с иконкой из архива
# (`net.vertcut.app`), не путаясь с ней.
ИМЯ_ДЛЯ_ПРАВКИ = ("Vertcut (dev)", "net.vertcut.app.проект")
ИМЯ_ПРОСТОЕ = ("Vertcut", "net.vertcut.app.source")

INFO_PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>@NAME@</string>
  <key>CFBundleDisplayName</key><string>@NAME@</string>
  <key>CFBundleIdentifier</key><string>@ID@</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>CFBundleExecutable</key><string>Vertcut</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>LSUIElement</key><true/>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
</dict></plist>
"""

# Что написано в исполняемом файле иконки, и почему примечания —
# здесь, а не в нём.
#
# **Примечания здесь, а слова в нём — английские.** Файл лежит внутри
# свёртка, его видно через «Показать содержимое пакета», а слова из
# него приходят окном и журналом — то есть человеку. Объяснения
# остаются здесь, по-русски, тем же правилом, что у `Vertcut.cmd`.
#
# ИМЕНА ПЕРЕМЕННЫХ ЛАТИНИЦЕЙ: bash 3.2 в macOS русских имён не понимает
# и падает на первой же строке. То же правило, что в `launcher.sh`.
#
# **Окружения нет — говорим словами и НЕ ставим ничего сами**:
# рабочую копию человек собирает сам.
#
# **PATH и архитектура — то, чего у двойного щелчка нет**, и обе
# разницы стоили сервису лица; объяснено в `launcher.sh` и
# `docs/decisions.md` («Мир двойного щелчка не тот, что мир терминала»).
# PATH берётся у логин-оболочки (ввод ей закрыт, чтобы она не повисла
# на вопросе в чьём-то профиле) и подставляется, только если похож
# на настоящий: без перевода строки и с `/usr/bin`. Архитектура —
# попыткой поднять numpy под arm64.
#
# **Всю работу делает сам сервис**: если он уже работает,
# `--exit-with-icon` найдёт хозяина, откроет его вкладку и уйдёт
# с нулём. Ноль — не падение. Не поднялся — экрана нет вовсе, и журнал
# открывается текстом: он и есть всё, что о беде известно.
ПУСК = """#!/bin/bash
# Vertcut from the working folder. Built by install/build-dev-launcher.py;
# the reasons behind each step are written there.
set -u

PROJECT="@PROJECT@"
PY="$PROJECT/.venv/bin/python"
SETTINGS="${VERTCUT_HOME:+$VERTCUT_HOME/.settings}"
SETTINGS="${SETTINGS:-$HOME/.vertcut}"
LOGS="$SETTINGS/logs"
mkdir -p "$LOGS"
LOG="$LOGS/launch-$(date +%Y-%m-%d-%H%M%S).log"
exec >>"$LOG" 2>&1
echo "── launch from the working folder $(date '+%Y-%m-%d %H:%M:%S') ──"
echo "folder: $PROJECT"

# No environment: say so, install nothing.
if [ ! -x "$PY" ]; then
  echo "no environment: $PY"
  osascript -e 'display alert "Vertcut didn'"'"'t start" message "The folder \\
it runs from has no Python environment (.venv). Set it up again by \\
following INSTALL.md in that folder — this icon never installs \\
anything itself." as critical' >/dev/null 2>&1
  exit 1
fi

# The login shell's PATH, if it looks like a real one.
LOGIN_PATH="$(/bin/zsh -lc 'printf %s "$PATH"' </dev/null 2>/dev/null || true)"
if [ -z "$LOGIN_PATH" ]; then
  LOGIN_PATH="$(/bin/bash -lc 'printf %s "$PATH"' </dev/null 2>/dev/null || true)"
fi
case "$LOGIN_PATH" in
  *"
"*) LOGIN_PATH="" ;;
esac
case ":$LOGIN_PATH:" in
  *":/usr/bin:"*) PATH="$LOGIN_PATH" ;;
esac
export PATH

# Run as arm64 if the environment is arm64.
ARCH=""
if [ "$(uname -s)" = "Darwin" ] \\
   && /usr/bin/arch -arm64 "$PY" -c "import numpy" >/dev/null 2>&1; then
  ARCH="/usr/bin/arch -arm64"
fi

$ARCH "$PY" -m vertcut screen --exit-with-icon &
SERVER=$!
sleep 3
if ! kill -0 $SERVER 2>/dev/null; then
  wait $SERVER
  CODE=$?
  if [ "$CODE" -eq 0 ]; then
    echo "Vertcut was already running — it opened its own tab; exiting"
    exit 0
  fi
  echo "Vertcut didn't start, exit code $CODE"
  open -t "$LOG"
  exit $CODE
fi
wait $SERVER
echo "── Vertcut stopped $(date '+%Y-%m-%d %H:%M:%S') ──"
"""


def собрать(куда: Path, проект: Path, простое: bool = False) -> Path:
    имя, опознание = ИМЯ_ПРОСТОЕ if простое else ИМЯ_ДЛЯ_ПРАВКИ
    приложение = куда / f"{имя}.app"
    # Чужой свёрток с тем же именем не сносится. На Рабочем столе
    # человека уже может лежать «Vertcut.app» из архива — у неё другой
    # идентификатор, и молча заменить её значило бы отнять у человека
    # то, что он поставил другой дорогой.
    прежний = приложение / "Contents" / "Info.plist"
    if прежний.exists() and f"<string>{опознание}</string>" not in \
            прежний.read_text(encoding="utf-8", errors="replace"):
        raise SystemExit(
            f"{приложение} already exists and isn't an icon built here "
            "— left it alone. Move it away first, or build into another "
            "folder with --out.")
    shutil.rmtree(приложение, ignore_errors=True)
    (приложение / "Contents" / "MacOS").mkdir(parents=True)
    (приложение / "Contents" / "Info.plist").write_text(
        INFO_PLIST.replace("@NAME@", имя).replace("@ID@", опознание),
        encoding="utf-8")
    пуск = приложение / "Contents" / "MacOS" / "Vertcut"
    пуск.write_text(ПУСК.replace("@PROJECT@", str(проект)), encoding="utf-8")
    пуск.chmod(0o755)
    return приложение


def main(аргументы=None) -> int:
    разбор = argparse.ArgumentParser(
        description="An icon that runs Vertcut from this working copy")
    разбор.add_argument("--out", dest="куда", type=Path, default=None,
                        help="where to put it; the Desktop by default")
    разбор.add_argument("--plain", dest="простое", action="store_true",
                        help='name it "Vertcut" instead of "Vertcut (dev)" '
                             "— for running Vertcut, not changing it")
    это = разбор.parse_args(аргументы)
    if sys.platform != "darwin":
        raise SystemExit("App bundles exist only on macOS.")
    if not (КОРЕНЬ / ".venv" / "bin" / "python").exists():
        print("WARNING: there's no .venv in the working folder — the icon "
              "will be built, but will say so on the first click.",
              file=sys.stderr)
    куда = это.куда or (Path.home() / "Desktop")
    вышло = собрать(куда, КОРЕНЬ, это.простое)
    print(f"built: {вышло}")
    print(f"runs: {КОРЕНЬ}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

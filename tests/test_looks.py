"""Готовые виды субтитров.

Вид — это несколько чисел поверх профиля, а не четвёртый уровень стиля.
Главное здесь — то, что у каждого вида записана его ЦЕНА: доля фраз,
которые начинают перелистываться посреди себя. Вид, у которого
перелистывается половина, поставлять нельзя, и узнать это должен тот,
кто вид кладёт, а не человек на своём первом видео.
"""

from __future__ import annotations

import pytest

from vertcut import cli, layout, subs
from vertcut.errors import VertcutError

# Выше этой доли вид не поставляется. Не замер, а решение: половина
# фраз с перелистыванием — это субтитр, который дёргается посреди
# каждой второй фразы, и человек справедливо решит, что сервис сломан.
ПРЕДЕЛ_ПЕРЕЛИСТЫВАНИЙ = 0.45


@pytest.fixture(autouse=True)
def чистый_кэш():
    subs.сбросить_кэш()
    yield
    subs.сбросить_кэш()


def test_виды_читаются_и_у_каждого_есть_зачем():
    все = subs.виды()
    assert "standard" in все
    for имя, вид in все.items():
        assert вид["зачем"], f"у вида «{имя}» не сказано, зачем он"


def test_обычный_вид_ничего_не_меняет():
    """Он и есть поставляемый образец: вид «standard» — способ вернуться
    к нему, не вспоминая ни одного числа."""
    assert subs.виды()["standard"]["числа"] == {}


@pytest.mark.parametrize("имя", list(subs.виды()))
def test_у_каждого_вида_записана_его_цена(имя):
    вид = subs.виды()[имя]
    assert вид["цена"], "цена вида не записана"
    assert all(0.0 <= з <= 1.0 for з in вид["цена"].values())


@pytest.mark.parametrize("имя", list(subs.виды()))
def test_ни_один_вид_не_перелистывает_половину_фраз(имя):
    """Замер третьей сессии отбросил первый вариант «крупного»: при
    кегле 0.058 (второй эталон предка) перелистывалась половина фраз
    эссе и английского видео."""
    худшая = max(subs.виды()[имя]["цена"].values())
    assert худшая <= ПРЕДЕЛ_ПЕРЕЛИСТЫВАНИЙ, (
        f"вид «{имя}» перелистывает {худшая:.0%} фраз — такой "
        "поставлять нельзя")


@pytest.mark.parametrize("имя", list(subs.виды()))
def test_каждый_вид_ложится_на_профиль_и_читается(имя):
    """Вид, который не даёт собрать профиль, хуже, чем никакого."""
    числа = subs.образец()
    for ключ, значение in subs.виды()[имя]["числа"].items():
        где, части = числа, ключ.split(".")
        for часть in части[:-1]:
            где[часть] = dict(где[часть])
            где = где[часть]
        где[части[-1]] = значение
    prof = subs.к_пикселям(числа)
    assert subs.font_of(prof) is not None
    assert prof["предел_текста"] > 0


def test_вид_с_незнакомым_ключом_это_отказ(monkeypatch, tmp_path):
    """Опечатка в имени числа иначе прошла бы тихо: вид ляжет,
    а число не доедет."""
    подделка = tmp_path / "looks.yaml"
    подделка.write_text(
        "odd:\n  about: test\n  cost: {essay: 0.1}\n"
        "  settings: {sise: 0.05}\n", encoding="utf-8")
    monkeypatch.setattr(layout, "looks", lambda: подделка)
    with pytest.raises(VertcutError) as беда:
        subs.виды()
    assert "sise" in беда.value.message


def test_вид_без_цены_это_отказ(monkeypatch, tmp_path):
    подделка = tmp_path / "looks.yaml"
    подделка.write_text("odd:\n  about: test\n  settings: {}\n",
                        encoding="utf-8")
    monkeypatch.setattr(layout, "looks", lambda: подделка)
    with pytest.raises(VertcutError) as беда:
        subs.виды()
    assert "cost" in беда.value.message


def test_нет_такого_вида_отказ_словами():
    with pytest.raises(VertcutError) as беда:
        subs.взять_вид("сиреневый")
    assert "vertcut looks" in (беда.value.hint or "")


# ─── вид ложится в профиль видео ─────────────────────────────────────

def завести_видео(слаг: str):
    папка = layout.project(слаг)
    папка.mkdir(parents=True, exist_ok=True)
    subs.завести(папка)
    return папка


def test_вид_ложится_в_копию_видео_и_не_трогает_поставляемый():
    было = layout.subs_yaml().read_bytes()
    завести_видео("одно")
    assert cli.main(["style", "одно", "--preset", "narrow"]) == 0
    subs.сбросить_кэш()
    assert subs.settings(layout.project("одно"))["font"] == "Oswald.ttf"
    assert layout.subs_yaml().read_bytes() == было


def test_рядом_с_видом_можно_поправить_число():
    """Вид ложится первым, всё названное рядом правит его поверх."""
    завести_видео("одно")
    assert cli.main(["style", "одно", "--preset", "narrow",
                     "--set", "size=0.06"]) == 0
    subs.сбросить_кэш()
    данные = subs.settings(layout.project("одно"))
    assert данные["font"] == "Oswald.ttf"
    assert данные["size"] == 0.06


def test_вид_не_стирает_примечаний_профиля():
    папка = завести_видео("одно")
    путь = layout.project_subs(папка)
    примечаний = путь.read_text(encoding="utf-8").count("#")
    assert cli.main(["style", "одно", "--preset", "large"]) == 0
    assert путь.read_text(encoding="utf-8").count("#") == примечаний


def test_цена_видов_перемеряется_командой():
    """Второй раз подряд записанное однажды число не сошлось
    с пересчётом — сперва у предка, потом у нас. Число, которое нельзя
    перемерить одной командой, через полгода становится преданием."""
    prof = subs.к_пикселям(subs.образец())
    шрифт = subs.font_of(prof)
    laid = {"phrases": [
        {"words": [{"w": w, "s": 0.0, "e": 0.3} for w in "раз два".split()]},
        {"words": [{"w": w, "s": 0.0, "e": 0.3}
                   for w in ("длинная фраза, которая никак не влезает "
                             "в одну страницу субтитра, потому что слов "
                             "в ней очень много и они длинные").split()]},
    ]}
    итог = subs.перелистывания(laid, prof, шрифт)
    assert итог["фраз"] == 2
    assert итог["не_влезли"] == 1
    assert итог["доля"] == 0.5


def test_вид_кладётся_поверх_поставляемого_а_не_поверх_прежнего():
    """Иначе «взять готовый вид» значило бы разное в зависимости от
    того, что человек трогал раньше, и вид «standard» (чисел в нём нет
    вовсе) не возвращал бы ничего."""
    завести_видео("одно")
    assert cli.main(["style", "одно", "--preset", "narrow",
                     "--set", "size=0.07"]) == 0
    subs.сбросить_кэш()
    assert subs.settings(layout.project("одно"))["size"] == 0.07

    assert cli.main(["style", "одно", "--preset", "standard"]) == 0
    subs.сбросить_кэш()
    assert subs.settings(layout.project("одно")) == subs.образец()

#!/usr/bin/env python3
"""Реестр обязательных проверок выпуска и журнал их прогонов.

    python3 proverki.py spisok  <папка> --faza <имя>   что обязано быть проведено
    python3 proverki.py mark    <папка> <имя> --sled "…" [--verdikt зелёный|красный]
    python3 proverki.py gate    <папка> --faza <имя>   всё ли проведено, и по текущей ли версии
    python3 proverki.py fazy                           порядок фаз конвейера

Зачем это существует. Исполнитель не врёт про проделанную работу — он ЗАБЫВАЕТ под
длинной инструкцией. Поэтому память о проверках вынесена из головы в файл, а сам
факт прогона привязан к **хешу проверявшегося файла**: правка после проверки молча
обнуляет её, и гейт краснеет. Без этого «я прогнал русский редактор» означает
«прогнал когда-то, возможно, по другой редакции текста».

СОСТАВ И ПОРЯДОК ФАЗ ЖИВУТ ЗДЕСЬ, а не в прозе протокола. Причина — та же, по которой
здесь живёт журнал: порядок, вынесенный из текста в код, единственный не зависит от
того, что исполнитель вспомнит. `docs/PROTOKOL-VYPUSKA.md` на этот словарь ссылается и
его не дублирует; расхождение чинится правкой протокола, а не кода.

ФАЗЫ НАЗВАНЫ ИМЕНАМИ, А НЕ НОМЕРАМИ (решение владельца 16.08). Номер съезжает в тот
день, когда между двумя фазами вставляют третью, и съезжает молча: гейт продолжает
работать, проверяя не ту фазу.

ПОРЯДОК ponyatnost → stil ВЫВЕДЕН ИЗ ХЕША, а не выбран. Всё, что МЕНЯЕТ содержание,
идёт раньше того, что содержание менять не имеет права: ponyatnost дописывает
определения, stil не имеет права трогать смысл. Обратный порядок физически не
работает — каждая правка понятности обнуляла бы стилевую отметку.

Журнал — `<папка>/.proverki.json`. Гейт зовётся из check_*.py; скрипты отмечаются в нём
сами, ручные проверки и верификаторы отмечаются командой `mark` со следом.
"""
# 🔴 ОБЯЗАТЕЛЬНО, НЕ КОСМЕТИКА: без этой строки аннотация `str | None` в mark()
# ВЫЧИСЛЯЕТСЯ при импорте и требует Python 3.10+, а системный python3 на машине
# владельца — 3.9.6. Импорт падал с `TypeError: unsupported operand type(s) for |`
# ещё до первой строки работы, то есть гейт фазы `stil` не запускался ТОЙ САМОЙ
# командой, которая написана в его собственной докстринге. Найдено исполнителем
# захода kod_rucola-probe 2026-08-16. Проверка: `python3.9 -c "import proverki"`.
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

# Порядок фаз конвейера. Фаза не стартует, пока предыдущая не принята строкой
# `ПРИНЯТО <имя>:` в своём артефакте приёмки.
PORYADOK = ['razvedka', 'raskladka', 'karta', 'tekst', 'ponyatnost', 'stil']

FAZA_IMYA = {
    'razvedka':  'разведка — всё математическое содержание темы',
    'raskladka': 'раскладка — разделы, утверждения, бюджеты',
    'karta':     'карта — блоки, опоры, места ввода понятий',
    'tekst':     'текст — проза по блокам',
    'ponyatnost': 'понятность — понятие введено там, где употреблено',
    'stil':      'стиль — регистр и идиома; содержание не трогается',
}

# где лежит строка `ПРИНЯТО <имя>:` этой фазы.
# У `razvedka` приёмки нет: она вне протокола, это вход.
PRIYOMKA = {
    'raskladka':  'RASKLADKA.md',
    'karta':      'PONYATIYA.md',
    'tekst':      'OTCHET.md',
    'ponyatnost': 'PONYATIYA.md',
    'stil':       'OTCHET.md',
}

# имя · чем проводится · какой файл проверяет
REESTR = {
    'razvedka': [],          # носителей нет, объявленная слепая зона: docs/fazy/razvedka.md
    'raskladka': [
        ('check_raskladka',           'скрипт',   'RASKLADKA.md'),
        ('verifikator-raskladki',     'субагент', 'RASKLADKA.md'),
    ],
    'karta': [
        ('bloki',                     'скрипт',   'vypusk.md'),
        # Носитель условия 3 гейта карты — «граф опор непуст». До 16.08 условие
        # стояло в docs/fazy/karta.md с маркером [У4], а проверки не было ни в
        # одном скрипте: в check_bloki слово «опирается» встречалось один раз, в
        # проверке непустоты поля, а прочерк поле не опустошает. Цена: у ВСЕХ 23
        # блоков выпуска 04 стояло `опирается: —`, гейт был зелёный, замер по
        # корпусу показывал 0,00 опор на блок при 1,23 в выпуске 02.
        ('opory',                     'скрипт',   'vypusk.md'),
        ('verifikator-karty',         'субагент', 'vypusk.md'),
    ],
    'tekst': [
        # `bloki` стоит здесь ВТОРЫМ ДОМОМ — тем же приёмом, что `check_ponyatiya`
        # в фазе `stil`. Условие 3 гейта фазы `tekst` — «слова-пустышки в строгом
        # блоке красное» — носитель имеет ([К9 пустышка]), но живёт он в
        # `check_bloki.py`, а тот до 16.08 стоял только в реестре `karta`. То есть
        # на фазе, где пишут прозу и где пустышки и заводятся, условие не
        # проверялось ничем: карту-то закрыли раньше, чем появился текст.
        # Перегон дёшев — файл тот же, скрипт тот же.
        ('bloki',                     'скрипт',   'vypusk.md'),
        ('check_vypusk',              'скрипт',   'vypusk.md'),
        ('istochniki',                'скрипт',   'vypusk.md'),
        ('verifikator-teksta',        'субагент', 'vypusk.md'),
    ],
    'ponyatnost': [
        ('check_ponyatiya',           'скрипт',   'vypusk.md'),
        ('verifikator-ponyatnosti',   'субагент', 'vypusk.md'),
    ],
    'stil': [
        # check_ponyatiya стоит здесь НАРОЧНО, вторым домом: стилевая правка меняет файл,
        # хеш расходится, и порядок ввода понятий приходится перегнать по НОВОЙ редакции.
        # Скрипт дёшев, перегон бесплатен. Верификатор понятности сюда НЕ дублируется —
        # он дорог, и требовать его после каждой запятой значит не гонять его вовсе.
        ('check_ponyatiya',           'скрипт',   'vypusk.md'),
        ('check_vypusk',              'скрипт',   'vypusk.md'),
        ('check_stil',                'скрипт',   'vypusk.md'),
        ('math-russian-terminology',  'скилл',    'vypusk.md'),
        ('russian-editor',            'скилл',    'vypusk.md'),
        ('verifikator-stilya',        'субагент', 'vypusk.md'),
    ],
}

VERDIKTNYE = {'verifikator-raskladki', 'verifikator-karty', 'verifikator-teksta',
              'verifikator-ponyatnosti', 'verifikator-stilya'}

# ⚠ ОБЪЯВЛЕННАЯ СЛЕПАЯ ЗОНА. Главное правило фазы `stil` — «здесь не меняется
# содержание» — машинного носителя НЕ имеет и иметь не может: отличить стилевую правку
# от смысловой машине нечем. Первая редакция сравнивала хеш с зафиксированным на выходе
# `ponyatnost` и краснела — но краснела она на ЛЮБОЙ правке, то есть на всякой законной
# работе фазы. Гейт, красный при здоровой работе, отключают целиком, и вместе с ним
# отключается всё остальное. Механизм снят намеренно.
# Что осталось: обнуление по хешу гонит заново дешёвый check_ponyatiya (он в реестре
# выше), а смысловую правку под видом стилевой ловит только владелец на показе.
# [ДОЛГ: docs/DOLGI.md#Д22]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16] if p.exists() else '—'


def zhurnal(d: Path) -> dict:
    f = d / '.proverki.json'
    return json.loads(f.read_text(encoding='utf-8')) if f.exists() else {}


def zapisat(d: Path, j: dict):
    (d / '.proverki.json').write_text(
        json.dumps(j, ensure_ascii=False, indent=2), encoding='utf-8')


def mark(d: Path, imya: str, sled: str, verdikt: str | None):
    vse = {n: f for faza in REESTR.values() for n, _, f in faza}
    if imya not in vse:
        print(f'✗ нет такой проверки: {imya}. Известные: {", ".join(sorted(vse))}')
        return 1
    if imya in VERDIKTNYE and not verdikt:
        print(f'✗ {imya} — верификатор, ему нужен --verdikt зелёный|красный')
        return 1
    if not sled or len(sled) < 20:
        print('✗ след обязателен и не короче 20 знаков: что искал, что нашёл, что исправил. '
              'Пустой след равен непроведённой проверке')
        return 1
    j = zhurnal(d)
    j[imya] = {'kogda': str(date.today()), 'fajl': vse[imya],
               'hash': sha(d / vse[imya]), 'verdikt': verdikt or '—', 'sled': sled}
    zapisat(d, j)
    print(f'✓ отмечено: {imya} по {vse[imya]} @{j[imya]["hash"]}')
    return 0


def avtomark(papka, imya: str, sled: str):
    """Скрипт отмечает сам себя, когда прошёл зелёным. Вызывается из check_*.py."""
    d = Path(papka)
    d = d if d.is_dir() else d.parent
    vse = {n: f for faza in REESTR.values() for n, _, f in faza}
    j = zhurnal(d)
    j[imya] = {'kogda': str(date.today()), 'fajl': vse[imya],
               'hash': sha(d / vse[imya]), 'verdikt': '—', 'sled': sled}
    zapisat(d, j)


def snyat(papka, imya: str) -> bool:
    """Скрипт УПАЛ — снимает собственную отметку. Возвращает, была ли она.

    🔴 Зачем это нужно, хотя выглядит избыточным. Отметка привязана к хешу
    ПРОВЕРЯЕМОГО ФАЙЛА, но не к версии самой проверки. Значит починка скрипта не
    обнуляет старые зелёные: файл не менялся, хеш совпадает, и `gate` продолжает
    печатать ✓ по отметке, которую поставила ПРЕЖНЯЯ, дырявая версия.
    `avtomark` пишет отметку только при успехе и упавший прогон не трогает, а
    вердикт «красный» `gate` учитывает ТОЛЬКО у ВЕРИФИКАТОРОВ — у скриптов
    игнорирует (см. ветку `imya in VERDIKTNYE`). Поэтому снимать отметку скрипт
    обязан сам, и делать это должен один общий инструмент, а не копия в каждом
    check_*.py.

    *Цена, 2026-08-16: `check_vypusk` научили краснеть на превышении потолка
    объёма, он покраснел шестью ошибками — а лист проверок фазы `tekst` в ту же
    минуту показывал `✓ check_vypusk`, потому что в журнале лежала отметка от
    версии, которая объём не проверяла. Выпуск ушёл бы к владельцу с зелёным
    листом при красном скрипте.*
    """
    d = Path(papka)
    d = d if d.is_dir() else d.parent
    try:
        j = zhurnal(d)
        if j.pop(imya, None) is None:
            return False
        zapisat(d, j)
        print(f'⚠ снята прежняя отметка `{imya}` в .proverki.json: '
              f'проверка не пройдена, гейт обязан это видеть')
        return True
    except Exception as e:                      # журнал недоступен — сказать вслух
        print(f'⚠ отметку `{imya}` снять не удалось ({e}) — '
              f'в журнале может остаться зелёный от прежнего прогона')
        return False


def prinyata(d: Path, faza: str) -> bool:
    """Принята ли фаза — строкой `ПРИНЯТО <имя>:` в её артефакте приёмки (Н4)."""
    f = d / PRIYOMKA.get(faza, '')
    if faza not in PRIYOMKA or not f.exists():
        return False
    return any(l.startswith(f'ПРИНЯТО {faza}:') for l in f.read_text(encoding='utf-8').split('\n'))


def gate(d: Path, faza: str, tiho=False):
    if faza not in REESTR:
        print(f'✗ нет такой фазы: {faza}. Известные по порядку: {" → ".join(PORYADOK)}')
        return 1
    j, bed = zhurnal(d), []
    stroki = []

    # предыдущая фаза обязана быть принята: фаза судит работу предыдущей, а не свою
    i = PORYADOK.index(faza)
    if i > 0:
        pred = PORYADOK[i - 1]
        if pred not in PRIYOMKA:
            # ⚠ У `razvedka` приёмки нет, и потому вход `raskladka` не проверяется НИЧЕМ.
            # Молчать об этом нельзя: молчание неотличимо от проверенного входа.
            stroki.append(f'   ⚠ вход: у предыдущей фазы «{pred}» приёмки нет вовсе — '
                          f'вход этой фазы не проверяется ничем [ДОЛГ: docs/DOLGI.md#Д23]')
        elif not prinyata(d, pred):
            stroki.append(f'   ✗ вход: предыдущая фаза «{pred}» не принята — нет строки '
                          f'`ПРИНЯТО {pred}:` в {PRIYOMKA[pred]}')
            bed.append(f'вход-{pred}')

    for imya, chem, fajl in REESTR[faza]:
        tek = sha(d / fajl)
        z = j.get(imya)
        if not z:
            stroki.append(f'   ✗ {imya:<26} {chem:<9} не проводилась')
            bed.append(imya)
        elif z['hash'] != tek:
            stroki.append(f'   ✗ {imya:<26} {chem:<9} проведена {z["kogda"]} по ДРУГОЙ '
                          f'редакции {fajl} (@{z["hash"]} ≠ @{tek}) — прогнать заново')
            bed.append(imya)
        elif imya in VERDIKTNYE and z['verdikt'] != 'зелёный':
            stroki.append(f'   ✗ {imya:<26} {chem:<9} вердикт «{z["verdikt"]}» — '
                          f'красный вердикт дальше не пропускается')
            bed.append(imya)
        else:
            stroki.append(f'   ✓ {imya:<26} {chem:<9} {z["kogda"]} @{z["hash"]} · {z["sled"][:60]}')
    if not tiho:
        print(f'Лист проверок фазы «{faza}» · {FAZA_IMYA.get(faza, "")}:')
        print('\n'.join(stroki) if stroki else
              '   ⚠ носителей нет вовсе — объявленная слепая зона, см. docs/fazy/'
              f'{faza}.md')
        print()
    if bed:
        if not tiho:
            print(f'✗ гейт проверок фазы «{faza}» красный: не закрыто {len(bed)} — '
                  f'{", ".join(bed)}')
        return 1
    if not tiho:
        if not REESTR[faza]:
            # Пустой реестр НЕ печатается словом «зелёный»: зелёный цвет при отсутствии
            # проверок и есть тот самый дефект, ради которого заведён этот протокол.
            print(f'⚠ у фазы «{faza}» гейта НЕТ — проверять нечем, а не «всё в порядке»')
        else:
            print(f'✓ гейт проверок фазы «{faza}» зелёный: '
                  f'закрыто {len(REESTR[faza])} из {len(REESTR[faza])}')
    return 0


def main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument('cmd', choices=['spisok', 'mark', 'gate', 'fazy'])
    ap.add_argument('papka', nargs='?')
    ap.add_argument('imya', nargs='?')
    ap.add_argument('--faza', default='tekst')
    ap.add_argument('--sled', default='')
    ap.add_argument('--verdikt')
    a = ap.parse_args()
    if a.cmd == 'fazy':
        for n, f in enumerate(PORYADOK, 1):
            nositeli = ', '.join(i for i, _, _ in REESTR[f]) or '— носителей нет'
            print(f'{n}. {f:<11} {FAZA_IMYA[f]}\n   {nositeli}')
        return 0
    d = Path(a.papka)
    if not d.is_dir():
        d = Path(__file__).parent / a.papka
    if not d.is_dir():
        print(f'✗ нет папки {a.papka}')
        return 1
    if a.cmd == 'spisok':
        for imya, chem, fajl in REESTR[a.faza]:
            print(f'{imya:<26} {chem:<9} по {fajl}')
        return 0
    if a.cmd == 'mark':
        return mark(d, a.imya, a.sled, a.verdikt)
    return gate(d, a.faza)


if __name__ == '__main__':
    sys.exit(main())

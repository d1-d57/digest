#!/usr/bin/env python3
"""Реестр обязательных проверок выпуска и журнал их прогонов.

    python3 proverki.py spisok  <папка> --faza N       что обязано быть проведено
    python3 proverki.py mark    <папка> <имя> --sled "…" [--verdikt зелёный|красный]
    python3 proverki.py gate    <папка> --faza N       всё ли проведено, и по текущей ли версии

Зачем это существует. Исполнитель не врёт про проделанную работу — он ЗАБЫВАЕТ под
длинной инструкцией. Поэтому память о проверках вынесена из головы в файл, а сам
факт прогона привязан к **хешу проверявшегося файла**: правка после проверки молча
обнуляет её, и гейт краснеет. Без этого «я прогнал русский редактор» означает
«прогнал когда-то, возможно, по другой редакции текста».

Журнал — `<папка>/.proverki.json`. Гейт зовётся из check_raskladka.py (фаза 1) и
check_vypusk.py (фаза 2); скрипты отмечаются в нём сами, ручные проверки и
верификаторы отмечаются командой `mark` со следом.
"""
import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

# имя · чем проводится · какой файл проверяет
# Проверки разделены по приоритету (решение владельца 16.08): ДО показа владельцу
# закрывается стиль — плохой стиль обесценивает показ; терминология и сверка
# источников доделываются ПОСЛЕ, они показу не мешают.
REESTR = {
    1: [
        ('check_raskladka',        'скрипт',   'RASKLADKA.md'),
        ('verifikator-raskladki',  'субагент', 'RASKLADKA.md'),
    ],
    2: [
        ('check_vypusk',              'скрипт',   'vypusk.md'),
        ('bloki',                     'скрипт',   'vypusk.md'),
        ('russian-editor',            'скилл',    'vypusk.md'),
        ('verifikator-teksta',        'субагент', 'vypusk.md'),
    ],
    3: [
        ('istochniki',                'скрипт',   'vypusk.md'),
        ('math-russian-terminology',  'скилл',    'vypusk.md'),
    ],
}
FAZA_IMYA = {1: 'раскладка', 2: 'стиль — до показа владельцу', 3: 'сверка — после показа'}

VERDIKTNYE = {'verifikator-raskladki', 'verifikator-teksta'}


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


def gate(d: Path, faza: int, tiho=False):
    j, bed = zhurnal(d), []
    stroki = []
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
        print(f'Лист проверок фазы {faza} · {FAZA_IMYA.get(faza, "")}:')
        print('\n'.join(stroki))
        print()
    if bed:
        if not tiho:
            print(f'✗ гейт проверок фазы {faza} красный: не закрыто {len(bed)} — '
                  f'{", ".join(bed)}')
        return 1
    if not tiho:
        print(f'✓ гейт проверок фазы {faza} зелёный')
    return 0


def main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument('cmd', choices=['spisok', 'mark', 'gate'])
    ap.add_argument('papka')
    ap.add_argument('imya', nargs='?')
    ap.add_argument('--faza', type=int, default=2)
    ap.add_argument('--sled', default='')
    ap.add_argument('--verdikt')
    a = ap.parse_args()
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

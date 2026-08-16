#!/usr/bin/env python3
"""Замер хроникальной нагрузки и сцепки по всем выпускам — К16.

    python3 zamer_korpusa.py            все выпуски таблицей
    python3 zamer_korpusa.py <папка>    один выпуск

Зачем. 16.08.2026 замер показал, что выпуск 4 отличается от принятых 02 и 03 не языком (по
лексическим признакам он даже суше), а тремя вещами: хроникальной нагрузкой, порванной сцепкой
блоков и числом несущих объектов. Владелец: «числа сильные, для четвёртого выбиваются. Очень
хорошо, когда можно что-то померить — давай превратим это в команды, которые это меряют, и в
гейты».

Н3 говорит: величину, которую можно посчитать командой, руками не вписывают. Поэтому числа К16
живут здесь, а канон на них ссылается.

⚠ ЧЕГО ЗДЕСЬ НЕТ. Плотность образного предиката («гипотеза стояла», «цепочка бьёт по
размерностям») — 25 на 1000 слов в 02, 23 в 03, 16 в 04 — снята РУЧНЫМ разбором субагента, и
машинного счёта у неё нет: чтобы отличить образный предикат от обычного, надо знать, стёрта ли
метафора. Это тот же класс, что К14. Число дано в каноне с датой и пометкой «ручной счёт», а не
командой. [ДОЛГ: docs/DOLGI.md#Д28]

⚠ Анафора считается по СПИСКУ зачинов и потому занижает: отсылка назад бывает и без них
(«Вязовская тогда предложила…»). Число годится для сравнения выпусков между собой, а не как
абсолютная доля.
"""
import glob
import re
import sys
from pathlib import Path

KOREN = Path(__file__).parent

# зачины, которыми блок отсылает к предыдущему. Список выведен просмотром зачинов 02 и 03.
ANAFORA = re.compile(
    r'^(У (этого|этой|него|неё)|Дальше|Рядом|Обе|Оба|Тот же|Та же|То же|Этот|Эта|Это|Эти|'
    r'Вторую|Вторая|Второй|Первую|Первый|Здесь|Отсюда|Именно|При этом|Теперь|Из этого|'
    r'В той же|Та самая|Тем же|Так же|Такой же|И вот|А вот|Поэтому|Значит)\b', re.I)
GOD = re.compile(r'\b(1[5-9]\d\d|20[0-4]\d)\b')
CHISLO = re.compile(r'\b\d[\d\s.,]*\b')
STROGIE = {'utverzhdenie', 'opredelenie', 'vyvod', 'ogovorka'}
# Вводные и хеджи общего русского. Замер 16.08: на весь корпус 02–04 ОДНО вхождение.
# То есть у выпуска их не бывает, и это факт корпуса, а не пожелание.
VVODNYE = re.compile(
    r'\b(вообще говоря|на самом деле|по сути|строго говоря|разумеется|как известно|'
    r'нетрудно (видеть|заметить)|легко видеть|заметим|отметим|впрочем|пожалуй)\b', re.I)


def bloki(src):
    out = []
    for kus in re.split(r'^%% ', src, flags=re.M)[1:]:
        m = re.match(r'([\w.]+)\s*·\s*(\w+)', kus.split('\n', 1)[0])
        if not m:
            continue
        zamysel = kus.split('====')[0]
        proza = re.split(r'^# ', kus.split('====', 1)[1] if '====' in kus else '', flags=re.M)[0]
        opir = re.search(r'^опирается:\s*(.+)$', zamysel, flags=re.M)
        out.append((m.group(1), m.group(2), proza.strip(),
                    (opir.group(1).strip() if opir else '—')))
    return out


def zamer(p: Path):
    src = p.read_text(encoding='utf-8')
    bl = bloki(src)
    if not bl:
        return None
    proza = '\n'.join(b[2] for b in bl)
    tokeny = re.findall(r'\S+', proza)
    dat = len(GOD.findall(proza))
    chisel = len(CHISLO.findall(proza))
    # анафорический зачин: первое предложение блока начинается с отсылки назад
    anafor = sum(1 for _n, _s, pr, _o in bl if pr and ANAFORA.match(pr.lstrip()))
    # рёбра дерева опор
    rebra = sum(len([x for x in o.replace('·', ',').split(',') if x.strip() not in ('—', '')])
                for _n, _s, _p, o in bl)
    razdelov = len(re.findall(r'^# \d', src, flags=re.M))
    # имена собственные — со spaCy, если он есть
    imena = None
    try:
        import spacy
        nlp = spacy.load('ru_core_news_sm')
        imena = len({t.lemma_ for t in nlp(proza) if t.pos_ == 'PROPN'})
    except Exception:
        pass
    st = {}
    for _n, s, _p, _o in bl:
        st[s] = st.get(s, 0) + 1
    strogih = sum(v for k, v in st.items() if k in STROGIE)
    dliny = {}
    for _n, s, pr, _o in bl:
        dliny.setdefault(s, []).append(len(pr))
    return {
        'блоков': len(bl), 'разделов': razdelov, 'знаков': len(proza), 'слов': len(tokeny),
        'дат/блок': dat / len(bl),
        'чисел %': 100 * chisel / max(len(tokeny), 1),
        'имён': imena,
        'имён/1000': (1000 * imena / len(tokeny)) if imena else None,
        'анафора %': 100 * anafor / len(bl),
        'опор/блок': rebra / len(bl),
        'строгих %': 100 * strogih / len(bl),
        'вводных': len(VVODNYE.findall(proza)),
        'статусы': st,
        'длины': {k: sum(v) // len(v) for k, v in dliny.items()},
    }


def main(arg=None):
    if arg:
        p0 = Path(arg) if Path(arg).exists() else KOREN / arg
        puti = [p0 / 'vypusk.md' if p0.is_dir() else p0]
    else:
        # по одному файлу на папку: у выпусков 02 и 03 разметка живёт в vypusk.razmechen.md,
        # у 04 — прямо в vypusk.md. Берём тот, где есть маркеры.
        puti = []
        for d in sorted(KOREN.glob('*/')):
            r, v = d / 'vypusk.razmechen.md', d / 'vypusk.md'
            puti.append(r if r.exists() else v)
    stroki = []
    for p in puti:
        if not p.exists():
            continue
        z = zamer(p)
        if z:
            stroki.append((p.parent.name[-9:], z))
    if not stroki:
        print('✗ ни одного размеченного выпуска не найдено. Разметка — маркеры %% в vypusk.md')
        return 1
    kol = ['блоков', 'разделов', 'знаков', 'дат/блок', 'чисел %', 'имён/1000',
           'анафора %', 'опор/блок', 'строгих %', 'вводных']
    print(f'{"выпуск":<11}' + ''.join(f'{k:>11}' for k in kol))
    for ime, z in stroki:
        def f(k):
            v = z[k]
            if v is None:
                return '—'
            return f'{v:.2f}' if isinstance(v, float) else str(v)
        print(f'{ime:<11}' + ''.join(f'{f(k):>11}' for k in kol))

    print('\nСТАТУСЫ БЛОКОВ')
    vse_st = sorted({k for _i, z in stroki for k in z['статусы']})
    print(f'{"выпуск":<11}' + ''.join(f'{s[:11]:>13}' for s in vse_st))
    for ime, z in stroki:
        print(f'{ime:<11}' + ''.join(f'{z["статусы"].get(s, 0):>13}' for s in vse_st))
    pusty = [s for s in ('ogovorka', 'otsylka')
             if sum(z['статусы'].get(s, 0) for _i, z in stroki) == 0]
    if pusty:
        print(f'⚠ статусов НЕ ВСТРЕЧАЕТСЯ ни разу: {", ".join(pusty)} — К9 их описывает, '
              f'а корпус не подтверждает. Отсутствие `otsylka` подозрительно особо: блок, не дающий '
              f'содержания, обязан помечаться ею, иначе он притворяется утверждением (Д8).')

    print('\nСРЕДНЯЯ ПРОЗА БЛОКА, знаков')
    print(f'{"выпуск":<11}' + ''.join(f'{s[:11]:>13}' for s in vse_st))
    for ime, z in stroki:
        print(f'{ime:<11}' + ''.join(f'{z["длины"].get(s, 0):>13}' for s in vse_st))

    print()
    print('⚠ Плотность ОБРАЗНОГО предиката здесь не считается — только ручным разбором (К16).')
    print('⚠ Анафора считается по списку зачинов и занижена; годится для сравнения выпусков.')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))

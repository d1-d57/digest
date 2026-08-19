#!/usr/bin/env python3
"""Замер УТЕЧКИ: сколько сигнала check_idioma.py на ленте обеспечено самой лентой.

Повод. `reestr_korpusa.tsv` строки 788 и 791: `materials/teorkat-vvedenie/LENTA-L2.md` и
`LENTA-L2/lenta.md` — оба по 93085 знаков, один и тот же текст — лежат в корпусе в слое
`nejroset`. То есть таблица сочетаемости, которой инструмент судит ленту, СОДЕРЖИТ эту ленту,
причём дважды. Сигнал «пара живёт только в нейросетевом слое» в такой конфигурации может быть
целиком самоподтверждением: текст подтверждает сам себя.

Что скрипт делает: берёт пары из ленты кодом самого check_idioma.py (тот же OKNO, те же
STOP_OBJEKT, та же proza/chistka), и для каждой пары из ведра «только в нейросетевом слое»
кладёт рядом два числа — частоту в нейрослое таблицы и число вхождений в самой ленте × 2.
Отношение и есть доля утечки.

Вывод НЕ доказывает, что инструмент плох: он показывает, какая часть его сигнала на этом
материале непроверяема.
"""
import collections
import gzip
import json
import sys
from pathlib import Path

VYPUSKI = Path('/sessions/funny-affectionate-fermi/mnt/matemdigest-map/vypuski')
LENTA = Path('/sessions/funny-affectionate-fermi/mnt/GitHub/materials/teorkat-vvedenie/LENTA-L2.md')
sys.path.insert(0, str(VYPUSKI))

import check_idioma as ci  # noqa: E402

# Лента лежит в корпусе ДВАЖДЫ (LENTA-L2.md и LENTA-L2/lenta.md, побайтово одинаковые).
KRATNOST = 2


def main():
    with gzip.open(ci.TABLICA, 'rt', encoding='utf-8') as f:
        T = json.load(f)
    kniga = {tuple(k.split('|')): v for k, v in T['kniga'].items()}
    chelovek = {tuple(k.split('|')): v for k, v in T['chelovek'].items()}
    nejro = {tuple(k.split('|')): v for k, v in T['nejroset'].items()}

    mat_chastota = collections.Counter()
    for (s, g), v in kniga.items():
        mat_chastota[s] += v

    import spacy
    nlp = spacy.load('ru_core_news_sm', disable=['ner', 'parser'])
    if 'sentencizer' not in nlp.pipe_names:
        nlp.add_pipe('sentencizer')

    tekst = ci.proza(LENTA.read_text(encoding='utf-8'))

    # ВСЕ вхождения пар в ленте, с повторами — именно они уехали в корпус
    v_lente = collections.Counter()
    for kus in [tekst[i:i + 40000] for i in range(0, len(tekst), 40000)]:
        for s, g, _sent in ci.pary_iz(nlp(kus)):
            v_lente[(s, g)] += 1

    # ведро «только в нейросетевом слое» при математическом объекте — то, что инструмент печатает
    tolko_nejro = [
        (s, g) for (s, g) in set(v_lente)
        if mat_chastota[s] >= ci.PORQG_MAT
        and (s, g) not in kniga and (s, g) not in chelovek
        and (s, g) in nejro
    ]

    polnaya, chastichnaya, chistaya = [], [], []
    for para in tolko_nejro:
        n = nejro[para]
        svoy = v_lente[para] * KRATNOST
        dolya = min(1.0, svoy / n) if n else 0.0
        row = (para, n, svoy, dolya)
        if dolya >= 0.95:
            polnaya.append(row)
        elif dolya >= 0.30:
            chastichnaya.append(row)
        else:
            chistaya.append(row)

    vsego = len(tolko_nejro)
    print(f'ВЕДРО «только в нейросетевом слое» при математическом объекте: {vsego} пар')
    print(f'Лента входит в корпус {KRATNOST} раза (реестр, строки 788 и 791).\n')
    print(f'  утечка ПОЛНАЯ   (свой вклад ≥95 % частоты): {len(polnaya):4d} — '
          f'{100 * len(polnaya) // max(1, vsego)} %')
    print(f'  утечка ЧАСТИЧНАЯ (30–95 %)                : {len(chastichnaya):4d} — '
          f'{100 * len(chastichnaya) // max(1, vsego)} %')
    print(f'  сигнал ЧИСТЫЙ    (<30 %, есть чужие тексты): {len(chistaya):4d} — '
          f'{100 * len(chistaya) // max(1, vsego)} %\n')

    print('ЧИСТЫЙ СИГНАЛ — пары, которые НЕ объясняются самой лентой (топ 25 по частоте):')
    for (s, g), n, svoy, dolya in sorted(chistaya, key=lambda r: -r[1])[:25]:
        print(f'  «{s} + {g}» · в нейрослое {n}, из них своих {svoy} ({100 * dolya:.0f} %)')

    print('\nПОЛНАЯ УТЕЧКА — пары, которых в корпусе нет НИГДЕ, кроме этой ленты (топ 15):')
    for (s, g), n, svoy, dolya in sorted(polnaya, key=lambda r: -r[1])[:15]:
        print(f'  «{s} + {g}» · в нейрослое {n}, своих {svoy}')
    return 0


if __name__ == '__main__':
    sys.exit(main())

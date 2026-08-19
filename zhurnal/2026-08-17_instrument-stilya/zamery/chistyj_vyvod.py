#!/usr/bin/env python3
"""Что остаётся от вывода check_idioma.py на ленте после двух поправок — с местами, для владельца.

Поправки, каждая замерена отдельно:
  1. вычесть вклад самой ленты из нейрослоя (она лежит в корпусе дважды, md5 совпадает) —
     `zamer_utechki2.py`: 159 пар из 378 держатся только на этом;
  2. судить только публикуемую прозу лекции, без режиссёрских блоков `> поле:` —
     `zamer_marginalij.py`: 145 пар из 378 приходят только оттуда.

Печатается пересечение: пара из публикуемой прозы, чья частота в нейрослое НЕ объясняется этой же
лентой. Это и есть список, который имеет смысл показывать человеку.
"""
import collections
import gzip
import json
import re
import sys
from pathlib import Path

VYPUSKI = Path('/sessions/funny-affectionate-fermi/mnt/matemdigest-map/vypuski')
LENTA = Path('/sessions/funny-affectionate-fermi/mnt/GitHub/materials/teorkat-vvedenie/LENTA-L2.md')
sys.path.insert(0, str(VYPUSKI))

import check_idioma as ci  # noqa: E402
sys.path.insert(0, str(Path(__file__).parent))
from zamer_marginalij import razdelit  # noqa: E402

KRATNOST = 2
PORQG_CHISTOTY = 0.30   # доля своего вклада, выше которой сигнал считается самоподтверждением


def main():
    T = json.load(gzip.open(ci.TABLICA, 'rt', encoding='utf-8'))
    kniga = {tuple(k.split('|')): v for k, v in T['kniga'].items()}
    chelovek = {tuple(k.split('|')): v for k, v in T['chelovek'].items()}
    nejro = {tuple(k.split('|')): v for k, v in T['nejroset'].items()}
    mat = collections.Counter()
    for (s, _g), v in kniga.items():
        mat[s] += v
    po_objektu = collections.defaultdict(collections.Counter)
    for (s, g), v in list(kniga.items()) + list(chelovek.items()):
        po_objektu[s][g] += v

    import spacy
    nlp = spacy.load('ru_core_news_sm', disable=['ner', 'parser'])
    if 'sentencizer' not in nlp.pipe_names:
        nlp.add_pipe('sentencizer')

    syroj = LENTA.read_text(encoding='utf-8')
    p_syroj, _s = razdelit(syroj)
    tekst = ci.proza(p_syroj)

    vse = collections.Counter()
    mesto = {}
    for kus in [tekst[i:i + 40000] for i in range(0, len(tekst), 40000)]:
        for s, g, sent in ci.pary_iz(nlp(kus)):
            vse[(s, g)] += 1
            mesto.setdefault((s, g), ' '.join(sent.split())[:150])

    itog = []
    for para, _n_v_tekste in vse.items():
        s, g = para
        if mat[s] < ci.PORQG_MAT:
            continue
        if para in kniga or para in chelovek:
            continue
        n = nejro.get(para, 0)
        if n == 0:
            continue
        dolya = min(1.0, vse[para] * KRATNOST / n)
        if dolya >= PORQG_CHISTOTY:
            continue
        itog.append((para, n, dolya))

    itog.sort(key=lambda r: -r[1])
    print(f'ПОСЛЕ ОБЕИХ ПОПРАВОК ОСТАЛОСЬ: {len(itog)} пар (было 378)\n')
    for (s, g), n, dolya in itog:
        glagoly = ', '.join(f'{gl}' for gl, _ in po_objektu[s].most_common(6))
        print(f'«{s} + {g}» · в нейрослое {n}, свой вклад {100 * dolya:.0f} %')
        print(f'   место: {mesto[(s, g)]}')
        print(f'   а в корпусе «{s}» бывает: {glagoly}\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())

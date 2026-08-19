#!/usr/bin/env python3
"""Третий замер: какую долю находок на ленте инструмент берёт из НЕПУБЛИКУЕМОГО текста.

`check_idioma.proza()` умеет отделять служебную разметку ФОРМАТА ВЫПУСКА: шапку, таблицу карты,
строки `зачем:/мысль:/опирается:` до `====`. Формат ленты она не знает. В ленте служебный слой
устроен иначе — это блоки `> поле:mn`: режиссёрские заметки лектору («Так и произносится»,
«Про естественное преобразование во входе не говорим вовсе», «Картинок у слайда нет»). Их 55.
Публиковаться они не будут ни в каком виде: это не проза лекции, а инструкция к ней.

`chistka()` вычищает символ `>` из текста наравне с прочей разметкой — то есть маргиналии не
отбрасываются, а вливаются в прозу, потеряв единственный признак, по которому их можно отличить.

Скрипт считает пары отдельно по двум слоям и печатает, сколько находок ведра «только в
нейросетевом слое» приходит из непубликуемого.
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


def razdelit(syroj):
    """Делит ленту на публикуемую прозу и режиссёрский слой `> поле:*`.

    Блок маргиналии начинается строкой `> поле:<что>` и продолжается строками `>` до пустой.
    """
    proza_l, sluzhba_l = [], []
    v_marginalii = False
    for ln in syroj.split('\n'):
        s = ln.strip()
        if re.match(r'^>\s*поле:', s):
            v_marginalii = True
            sluzhba_l.append(ln)
            continue
        if v_marginalii:
            if s.startswith('>'):
                sluzhba_l.append(ln)
                continue
            v_marginalii = False
        proza_l.append(ln)
    return '\n'.join(proza_l), '\n'.join(sluzhba_l)


def pary(nlp, tekst):
    out = collections.Counter()
    for kus in [tekst[i:i + 40000] for i in range(0, len(tekst), 40000)]:
        for s, g, _sent in ci.pary_iz(nlp(kus)):
            out[(s, g)] += 1
    return out


def main():
    T = json.load(gzip.open(ci.TABLICA, 'rt', encoding='utf-8'))
    kniga = {tuple(k.split('|')): v for k, v in T['kniga'].items()}
    chelovek = {tuple(k.split('|')): v for k, v in T['chelovek'].items()}
    nejro = {tuple(k.split('|')): v for k, v in T['nejroset'].items()}
    mat = collections.Counter()
    for (s, _g), v in kniga.items():
        mat[s] += v

    import spacy
    nlp = spacy.load('ru_core_news_sm', disable=['ner', 'parser'])
    if 'sentencizer' not in nlp.pipe_names:
        nlp.add_pipe('sentencizer')

    syroj = LENTA.read_text(encoding='utf-8')
    p_syroj, s_syroj = razdelit(syroj)
    print(f'ФАЙЛ: {len(syroj)} знаков')
    print(f'  публикуемая проза лекции : {len(p_syroj)} — {100 * len(p_syroj) // len(syroj)} %')
    print(f'  режиссёрский слой «поле:»: {len(s_syroj)} — {100 * len(s_syroj) // len(syroj)} %')
    n_blokov = len(re.findall(r'^>\s*поле:', syroj, re.M))
    print(f'  блоков маргиналий: {n_blokov}\n')

    p_pary = pary(nlp, ci.proza(p_syroj))
    s_pary = pary(nlp, ci.chistka(s_syroj))

    def tolko_nejro(pp):
        return {k for k in pp if mat[k[0]] >= ci.PORQG_MAT
                and k not in kniga and k not in chelovek and k in nejro}

    tp, ts = tolko_nejro(p_pary), tolko_nejro(s_pary)
    tolko_v_sluzhbe = ts - tp
    print(f'ВЕДРО «только в нейросетевом слое»:')
    print(f'  всего на объединённом тексте (как судит инструмент сейчас): {len(tp | ts)}')
    print(f'  из публикуемой прозы лекции                               : {len(tp)}')
    print(f'  находки, которых в прозе НЕТ — только в режиссёрском слое : {len(tolko_v_sluzhbe)}'
          f' ({100 * len(tolko_v_sluzhbe) // max(1, len(tp | ts))} % вывода)\n')

    print('НАХОДКИ ИЗ НЕПУБЛИКУЕМОГО (топ 20 по частоте в нейрослое):')
    for k in sorted(tolko_v_sluzhbe, key=lambda k: -nejro[k])[:20]:
        print(f'  «{k[0]} + {k[1]}» · в нейрослое {nejro[k]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())

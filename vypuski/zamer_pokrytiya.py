#!/usr/bin/env python3
"""Замер: какая доля пар выпуска подтверждается корпусом — и что даёт добавка Википедии.

    python3 zamer_pokrytiya.py <папка выпуска> [--wiki vypuski/.korpus/wiki_teksty.json]

🔴 ЗАЧЕМ ЭТОТ ЗАМЕР СУЩЕСТВУЕТ. Владелец 17.08 назвал главное число линии: сколько существующей
лексики выпуска попало в корпус. Цель — чтобы всё НЕ попавшее оказывалось реально странным. Пока
покрытие 46 %, «пары нет в таблице» не значит ничего, и весь инструмент висит в воздухе
[ДОЛГ: docs/DOLGI.md#Д27]. Развилка, которую видно только замером: может, корпуса уже достаточно;
может, его нужно в сто раз больше — и тогда путь бессмыслен.

🔴 ПОЧЕМУ ВИКИПЕДИЯ СЧИТАЕТСЯ ОТДЕЛЬНО, А НЕ ВЛИВАЕТСЯ В ТАБЛИЦУ. Решение владельца 16.08: вики —
источник ЛЕКСИКИ, а не эталон стиля; замер показал «является» 229 против наших 55 на миллион знаков.
Поэтому вики отвечает только на вопрос «оборот вообще засвидетельствован в русской математической
прозе» — то есть ровно на вопрос покрытия — и НЕ даёт права считать оборот принятым.

КАК СЧИТАЕТСЯ. Пары выпуска берутся тем же кодом, что в check_idioma.py (один разбор — одна правда).
Корпус вики НЕ лемматизируется целиком: это 88 млн знаков и часы работы. Вместо этого для лемм,
которые реально встретились в выпуске, порождаются все словоформы (pymorphy3), и корпус проходится
один раз токенайзером по словам — окно то же, OKNO из check_idioma.

⚠ ЧЕГО ЗАМЕР НЕ ДЕЛАЕТ. Он не судит обороты и не различает subj/dobj: считается со-встречаемость в
окне, как в check_idioma. Значит, он завышает подтверждения шумом вида «речь ИДЁТ о ГРАНИЦЕ» — и это
осознанный размен: шум работает в безопасную сторону, добавляя подтверждений, а не подозрений.
"""
import argparse
import collections
import gzip
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from check_idioma import OKNO, PORQG_MAT, STOP_OBJEKT, proza, pary_iz  # noqa: E402

SLOVO = re.compile(r'[А-Яа-яЁёA-Za-z-]+')


def formy(lemmy, morph):
    """лемма → все словоформы. Обратный словарь форма → множество лемм."""
    obratno = collections.defaultdict(set)
    for l in lemmy:
        razbor = morph.parse(l)
        if not razbor:
            continue
        for f in razbor[0].lexeme:
            obratno[f.word.replace('ё', 'е')].add(l)
        obratno[l.replace('ё', 'е')].add(l)
    return obratno


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('put')
    ap.add_argument('--wiki', default=str(Path(__file__).parent / '.korpus/wiki_teksty.json'))
    a = ap.parse_args()

    import spacy
    import pymorphy3
    nlp = spacy.load('ru_core_news_sm', disable=['ner', 'parser'])
    if 'sentencizer' not in nlp.pipe_names:
        nlp.add_pipe('sentencizer')
    morph = pymorphy3.MorphAnalyzer()

    p = Path(a.put)
    fajl = p / 'vypusk.md' if p.is_dir() else p
    tekst = proza(fajl.read_text(encoding='utf-8'))

    tab = Path(__file__).parent / 'tablica_sochetaemosti.json.gz'
    with gzip.open(tab, 'rt', encoding='utf-8') as f:
        T = json.load(f)
    kniga = {tuple(k.split('|')): v for k, v in T['kniga'].items()}
    chelovek = {tuple(k.split('|')): v for k, v in T['chelovek'].items()}
    etalon = collections.Counter()
    for d in (kniga, chelovek):
        for k, v in d.items():
            etalon[k] += v
    mat = collections.Counter()
    for (s, g), v in kniga.items():
        mat[s] += v

    pary = set()
    for kus in [tekst[i:i + 40000] for i in range(0, len(tekst), 40000)]:
        for s, g, _ in pary_iz(nlp(kus)):
            pary.add((s, g))
    mat_pary = {(s, g) for s, g in pary if mat[s] >= PORQG_MAT}
    print(f'ПАРЫ ВЫПУСКА: всего разных {len(pary)}, из них при математических объектах '
          f'{len(mat_pary)} (порог книжного слоя ≥ {PORQG_MAT})')
    bylo = {pr for pr in mat_pary if etalon.get(pr, 0) > 0}
    print(f'ПОКРЫТИЕ ЭТАЛОНОМ (книги + человек, {len(etalon)} пар): '
          f'{len(bylo)}/{len(mat_pary)} = {100 * len(bylo) / max(1, len(mat_pary)):.0f} %')

    lemmy = {s for s, _ in mat_pary} | {g for _, g in mat_pary}
    obratno = formy(lemmy, morph)
    obj_lemmy = {s for s, _ in mat_pary}
    gl_lemmy = {g for _, g in mat_pary}
    print(f'РАЗВЁРНУТО СЛОВОФОРМ: {len(obratno)} на {len(lemmy)} лемм — корпус проходится по ним')

    w = Path(a.wiki)
    if not w.exists():
        print(f'✗ нет корпуса {w}')
        return 1
    korpus = json.load(open(w, encoding='utf-8'))
    statej = len(korpus)
    najdeno = collections.Counter()
    # 🔴 КРИВАЯ РОСТА — ради неё замер и написан. Для каждой пары запоминается, на какой статье она
    # встретилась ВПЕРВЫЕ; отсюда покрытие как функция размера корпуса. Развилка «корпуса уже хватает
    # / нужно в сто раз больше» решается формой этой кривой, а не мнением: если она вышла на плато,
    # добор статей не поможет и надо менять инструмент, а не растить корпус.
    vpervye = {}
    krivaya = []
    znakov = 0
    for n, tekst_st in enumerate(korpus.values(), 1):
        znakov += len(tekst_st)
        toks = SLOVO.findall(tekst_st.lower().replace('ё', 'е'))
        lem = [obratno.get(t) for t in toks]
        for i, li in enumerate(lem):
            if not li:
                continue
            gl = li & gl_lemmy
            if not gl:
                continue
            for j in range(max(0, i - OKNO), min(len(lem), i + OKNO + 1)):
                if j == i or not lem[j]:
                    continue
                for s in lem[j] & obj_lemmy:
                    for g in gl:
                        if (s, g) in mat_pary:
                            najdeno[(s, g)] += 1
                            vpervye.setdefault((s, g), n)
        if n % 500 == 0:
            krivaya.append((n, znakov, len(najdeno), len(bylo | set(najdeno))))
        if n % 1000 == 0:
            print(f'   … {n}/{statej} статей, найдено пар {len(najdeno)}', flush=True)

    stalo = bylo | {pr for pr, v in najdeno.items() if v > 0}
    print(f'\nКОРПУС ВИКИ: {statej} статей, {znakov / 1e6:.1f} млн знаков')
    print(f'ПОКРЫТИЕ ВИКИ ОТДЕЛЬНО: {len(najdeno)}/{len(mat_pary)} = '
          f'{100 * len(najdeno) / max(1, len(mat_pary)):.0f} %')
    print(f'🔴 ПОКРЫТИЕ ВМЕСТЕ (эталон + вики): {len(stalo)}/{len(mat_pary)} = '
          f'{100 * len(stalo) / max(1, len(mat_pary)):.0f} % (было {100 * len(bylo) / max(1, len(mat_pary)):.0f} %)')
    print('\n🔴 КРИВАЯ РОСТА ПОКРЫТИЯ — плато или нет:')
    print('   статей   млн знаков   вики   вместе с эталоном')
    for n, zn, w_, v_ in krivaya[::max(1, len(krivaya) // 12)] + krivaya[-1:]:
        print(f'   {n:6}   {zn / 1e6:9.1f}   {100 * w_ / len(mat_pary):4.0f}%   '
              f'{100 * v_ / len(mat_pary):4.0f}%')
    if len(krivaya) >= 4:
        chetvert = len(krivaya) // 4
        d1 = krivaya[chetvert][3] - krivaya[0][3]
        d4 = krivaya[-1][3] - krivaya[-1 - chetvert][3]
        print(f'   прирост пар за первую четверть прогона {d1}, за последнюю {d4} — '
              f'{"выходит на плато" if d4 * 3 < d1 else "ещё растёт"}')
    ne = sorted(mat_pary - stalo)
    print(f'\nНЕ ПОДТВЕРЖДЕНО НИЧЕМ — {len(ne)} пар. Цель владельца: чтобы каждая была реально странной')
    for s, g in ne:
        print(f'  {s} + {g}')
    out = Path(__file__).parent / '.korpus/zamer_pokrytiya.json'
    out.write_text(json.dumps({
        'statej': statej, 'znakov': znakov, 'par_mat': len(mat_pary),
        'etalon': len(bylo), 'wiki': len(najdeno), 'vmeste': len(stalo),
        'ne_podtverzhdeno': [list(x) for x in ne],
        'wiki_chastoty': {f'{s}|{g}': v for (s, g), v in najdeno.most_common()},
    }, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'\nчисла сохранены: {out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())

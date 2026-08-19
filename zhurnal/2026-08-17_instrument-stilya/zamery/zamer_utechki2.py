#!/usr/bin/env python3
"""Контрольный замер: что напечатал бы check_idioma.py, если бы ленты не было в корпусе.

Первый замер (`zamer_utechki.py`) показал долю утечки. Он НЕ отвечает на главный вопрос: меняет ли
утечка ВЫВОД инструмента или только его громкость. Здесь пары пересчитываются по вёдрам дважды —
как есть и с вычтенным вкладом ленты, — и вёдра сравниваются.

Заодно проверяется слой `wiki`: `T['meta']['kak_chitat']` объявляет его доказательством принятости
наравне с книгой и человеком («наличие в kniga/chelovek/wiki доказывает принятость»), а
`check_idioma.py` в свой набор подтверждений его НЕ берёт — читает только kniga и chelovek.
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

KRATNOST = 2  # md5 совпадает: LENTA-L2.md и LENTA-L2/lenta.md — один текст, оба в реестре


def vedro(para, kniga, chelovek, nejro, mat, wiki=None):
    s, _g = para
    if mat[s] < ci.PORQG_MAT:
        return 'бытовое'
    if para in kniga or para in chelovek or (wiki is not None and para in wiki):
        return 'ПОДТВЕРЖДЕНО'
    if para in nejro:
        return 'только-нейро'
    if mat[s] > 0:
        return 'НЕИЗВЕСТНО'
    return 'вне охвата'


def main():
    T = json.load(gzip.open(ci.TABLICA, 'rt', encoding='utf-8'))
    kniga = {tuple(k.split('|')): v for k, v in T['kniga'].items()}
    chelovek = {tuple(k.split('|')): v for k, v in T['chelovek'].items()}
    nejro = {tuple(k.split('|')): v for k, v in T['nejroset'].items()}
    wiki = {tuple(k.split('|')): v for k, v in T.get('wiki', {}).items()}

    mat = collections.Counter()
    for (s, _g), v in kniga.items():
        mat[s] += v

    import spacy
    nlp = spacy.load('ru_core_news_sm', disable=['ner', 'parser'])
    if 'sentencizer' not in nlp.pipe_names:
        nlp.add_pipe('sentencizer')

    tekst = ci.proza(LENTA.read_text(encoding='utf-8'))
    v_lente = collections.Counter()
    for kus in [tekst[i:i + 40000] for i in range(0, len(tekst), 40000)]:
        for s, g, _sent in ci.pary_iz(nlp(kus)):
            v_lente[(s, g)] += 1

    # корпус БЕЗ ленты: вычитаем её вклад из нейрослоя
    nejro_bez = {}
    for para, n in nejro.items():
        ost = n - v_lente.get(para, 0) * KRATNOST
        if ost > 0:
            nejro_bez[para] = ost

    kak_est = collections.Counter()
    bez_lenty = collections.Counter()
    s_wiki = collections.Counter()
    perehody = collections.Counter()
    for para in set(v_lente):
        a = vedro(para, kniga, chelovek, nejro, mat)
        b = vedro(para, kniga, chelovek, nejro_bez, mat)
        c = vedro(para, kniga, chelovek, nejro, mat, wiki=wiki)
        kak_est[a] += 1
        bez_lenty[b] += 1
        s_wiki[c] += 1
        if a != b:
            perehody[(a, b)] += 1

    print('РАЗНЫХ ПАР В ЛЕНТЕ:', len(v_lente), '\n')
    print(f'{"ведро":16} {"как есть":>10} {"без ленты в корпусе":>21} {"+ слой wiki":>13}')
    for v in ('ПОДТВЕРЖДЕНО', 'только-нейро', 'НЕИЗВЕСТНО', 'вне охвата', 'бытовое'):
        print(f'{v:16} {kak_est[v]:>10} {bez_lenty[v]:>21} {s_wiki[v]:>13}')

    print('\nПЕРЕХОДЫ вёдер при вычитании ленты из корпуса:')
    for (a, b), n in perehody.most_common():
        print(f'  {a} → {b}: {n} пар')

    d = s_wiki['ПОДТВЕРЖДЕНО'] - kak_est['ПОДТВЕРЖДЕНО']
    print(f'\nВКЛАД СЛОЯ wiki, который инструмент не читает: +{d} пар ушло бы в ПОДТВЕРЖДЕНО')
    print(f'  (в таблице слой wiki: {len(wiki)} пар; meta объявляет его доказательством принятости)')
    return 0


if __name__ == '__main__':
    sys.exit(main())

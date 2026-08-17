#!/usr/bin/env python3
"""Подозрения на незаконный оборот — по таблице сочетаемости, собранной из принятых текстов.

    python3 check_idioma.py <папка выпуска|файл.md> [--top 30] [--vse]

🔴 ПРЕДМЕТ — МАТЕМАТИЧЕСКАЯ РЕЧЬ, А НЕ РУССКИЙ ЯЗЫК ВООБЩЕ. Решение владельца 2026-08-16: боремся
с нейрослопом в МАТЕМАТИЧЕСКОЙ терминологии. По умолчанию скрипт печатает только пары, где объект —
математический (частота в книжном слое ≥ PORQG_MAT); бытовые обороты вроде «впечатляющее открытие»
он не судит, это класс общего редактора русского. Замер, на котором стоит это решение: покрытие
корпусом при математических объектах 46 %, при бытовых словах 1 % — судить бытовое корпусом
математической прозы нечем. `--vse` печатает и бытовые, отдельным разделом и с этой оговоркой.

🔴 ГЛАВНОЕ ПРАВИЛО, БЕЗ КОТОРОГО СКРИПТ ВРЁТ. Таблица `tablica_sochetaemosti.json.gz` доказывает
ПРИСУТСТВИЕ, а не отсутствие. Оборот есть в таблице — он принят, доказано корпусом из 15.6 МБ
принятых текстов. Оборота НЕТ — это не значит ничего: «граница сдвинулась» законна по прямому
вердикту владельца, а в корпусе её ноль. Поэтому скрипт НЕ КРАСНЕЕТ и не выносит вердиктов: он
снимает с проверки то, что корпус подтвердил, и печатает остальное — судье и человеку.
[ДОЛГ: docs/DOLGI.md#Д27]

ЧТО ОН ДЕЛАЕТ. Разбирает текст, вынимает пары «объект + предикат», делит их на три ведра:
  ✓ ПОДТВЕРЖДЕНО — пара есть в таблице (частота ≥ PORQG_PODTV). Смотреть не надо;
  ? НЕИЗВЕСТНО — пары нет, но объект в таблице есть. Печатается вместе со списком глаголов,
    которые с этим объектом в корпусе ВСТРЕЧАЮТСЯ, — это и есть опора для решения;
  · ВНЕ ОХВАТА — объекта нет в таблице вовсе (имя собственное, новый термин). Судить нечем.

ЧЕГО НЕ ДЕЛАЕТ: не判 не судит, не правит, не ловит регистр, самоповтор, понятность и математику.
Пары берутся окном в 4 токена, а не синтаксическим разбором, — поэтому среди них есть шум вида
«речь ИДЁТ о ГРАНИЦЕ» → (граница, идти). Шум работает в безопасную сторону: он добавляет
подтверждений, а не подозрений.

Требует spaCy: pip install spacy --break-system-packages && python3 -m spacy download ru_core_news_sm

🔴 ПОЛОСА А · ЯДРО — файл уедет в скилл финальной правки, который заменит `russian-editor`.
   Что мешает переносу: мешает одно: вход — папка выпуска, нужен параметр «просто текст».
   Граница скилла и вопросы владельцу — `zhurnal/2026-08-15_vypusk-04/KARTA-PERENOSA-v-skill.md`.
"""
import argparse
import collections
import gzip
import json
import re
import sys
from pathlib import Path

OKNO = 4
PORQG_PODTV = 1        # частота, начиная с которой пара считается подтверждённой корпусом
TABLICA = Path(__file__).parent / 'tablica_sochetaemosti.json.gz'

# 🔴 Две отсечки, обе выведены прогоном на выпуске 4, а не придуманы.
# «формула» — наша собственная заглушка вместо $…$: она встречается 18142 раза и одна забивала
# весь топ. Остальные — слова, к которым предикат не привязывается осмысленно.
STOP_OBJEKT = {'формула', 'год', 'раз', 'случай', 'пример', 'ссылка', 'страница', 'слово', 'текст',
               '·', '—', '-', 'мысль', 'зачем', 'блок', 'объём', 'link', 'areas'}
# 🔴 Порог «математичности» объекта: сколько раз книжный слой видел его при глаголе.
# 20 — не подобранное число, а отсечка, на которой посчитан замер 46 % / 1 % (см. докстроку).
PORQG_MAT = 20
# spaCy без синтаксического парсера принимает за VERB причастия и прилагательные
# («ортогональных», «замечательные», «неположительная»). Лемма настоящего глагола — инфинитив.
INFINITIV = re.compile(r'(ть|ться|ти|тись|чь|чься)$')


def chistka(t):
    t = re.sub(r'```.*?```', ' ', t, flags=re.S)
    t = re.sub(r'<[^>]+>', ' ', t)
    t = re.sub(r'\$\$.*?\$\$', ' формула ', t, flags=re.S)
    t = re.sub(r'\$[^$]*\$', ' формула ', t)
    t = re.sub(r'https?://\S+', ' ', t)
    t = re.sub(r'[#*`>|\[\]{}\\&~^_]', ' ', t)
    return re.sub(r'\s+', ' ', t)


def pary_iz(doc):
    """Пары (объект, предикат) окном в OKNO токенов. Возвращает и само предложение."""
    toks = [t for t in doc if not t.is_space]
    for i, t in enumerate(toks):
        if t.pos_ != 'VERB' or not INFINITIV.search(t.lemma_.lower()):
            continue
        for j in range(max(0, i - OKNO), min(len(toks), i + OKNO + 1)):
            if j != i and toks[j].pos_ == 'NOUN' and toks[j].lemma_.lower() not in STOP_OBJEKT:
                yield (toks[j].lemma_.lower(), t.lemma_.lower(), toks[j].sent.text.strip())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('put', help='папка выпуска или .md файл')
    ap.add_argument('--top', type=int, default=30, help='сколько неизвестных пар печатать')
    ap.add_argument('--vse', action='store_true',
                    help='печатать и пары при НЕматематических словах — другой класс, см. докстроку')
    a = ap.parse_args()

    if not TABLICA.exists():
        print(f'✗ нет таблицы {TABLICA} — собери её заново либо возьми из git')
        return 1
    with gzip.open(TABLICA, 'rt', encoding='utf-8') as f:
        T = json.load(f)
    # 🔴 ТРИ СЛОЯ ПО СТАТУСУ ИСТОЧНИКА, И ЭТО НЕСУЩЕЕ РАЗЛИЧЕНИЕ, А НЕ УЧЁТ.
    # kniga + chelovek — доказывают, что оборот принят. nejroset — тексты, написанные Claude
    # и НЕ вычитанные человеком: там живут ровно те обороты, которые мы ловим, и подтверждением
    # они не являются. Пара, встречающаяся ТОЛЬКО в нейросетевом слое, — усиленное подозрение.
    kniga = {tuple(k.split('|')): v for k, v in T['kniga'].items()}
    chelovek = {tuple(k.split('|')): v for k, v in T['chelovek'].items()}
    nejro = {tuple(k.split('|')): v for k, v in T['nejroset'].items()}
    pary = collections.Counter()
    for d in (kniga, chelovek):
        for k, v in d.items():
            pary[k] += v
    po_objektu = collections.defaultdict(collections.Counter)
    for (s, g), v in pary.items():
        po_objektu[s][g] += v
    # 🔴 Кто такой «математический объект» — считается по книжному слою, а не по списку слов.
    # Книги — чистая математика: слово, которое они знают как объект действия, и есть термин.
    mat_chastota = collections.Counter()
    for (s, g), v in kniga.items():
        mat_chastota[s] += v

    def matematicheskij(s):
        return mat_chastota[s] >= PORQG_MAT

    p = Path(a.put)
    fajl = p / 'vypusk.md' if p.is_dir() else p
    if not fajl.exists():
        print(f'✗ нет файла {fajl}')
        return 1

    try:
        import spacy
        nlp = spacy.load('ru_core_news_sm', disable=['ner', 'parser'])
        # границы предложений нужны, чтобы печатать МЕСТО находки; парсер для этого слишком дорог
        if 'sentencizer' not in nlp.pipe_names:
            nlp.add_pipe('sentencizer')
    except Exception as e:
        print(f'✗ нужен spaCy и модель ru_core_news_sm: {e}')
        return 1

    tekst = chistka(fajl.read_text(encoding='utf-8'))
    podtv, neizv, tolko_nejro, vne, bytovye = [], [], [], [], []
    vidano = set()
    for kus in [tekst[i:i + 40000] for i in range(0, len(tekst), 40000)]:
        for s, g, sent in pary_iz(nlp(kus)):
            if (s, g) in vidano:
                continue
            vidano.add((s, g))
            n = pary.get((s, g), 0)
            if not matematicheskij(s) and not a.vse:
                bytovye.append((s, g, sent))
                continue
            if n >= PORQG_PODTV:
                podtv.append((s, g, n))
            elif (s, g) in nejro:
                tolko_nejro.append((s, g, nejro[(s, g)], sent))
            elif s in po_objektu:
                neizv.append((s, g, sum(po_objektu[s].values()), sent))
            else:
                vne.append((s, g))

    vsego = len(podtv) + len(neizv) + len(tolko_nejro) + len(vne)
    m = T['meta']
    print(f'ФАЙЛ: {fajl}')
    print(f'ТАБЛИЦА собрана {m["sobrano"]}, три слоя по статусу источника:')
    print(f'   kniga    — {len(kniga):6} пар · {m["sloi"]["kniga"]["chto"]}')
    print(f'   chelovek — {len(chelovek):6} пар · {m["sloi"]["chelovek"]["chto"]}')
    print(f'   nejroset — {len(nejro):6} пар · {m["sloi"]["nejroset"]["chto"]}')
    print(f'ПРЕДМЕТ: обороты при МАТЕМАТИЧЕСКИХ объектах (частота в книжном слое ≥ {PORQG_MAT}). '
          f'Отложено как бытовое и не судится: {len(bytovye)} пар — это класс общего редактора '
          f'русского, не наш. Показать их: --vse')
    print(f'ОХВАТ: разных пар в тексте {vsego} — подтверждено человеком/книгой {len(podtv)}, '
          f'ТОЛЬКО в нейросетевом слое {len(tolko_nejro)}, неизвестно {len(neizv)}, '
          f'вне охвата {len(vne)}')
    print('⚠ ЧТО ЭТО НЕ ЗНАЧИТ: «неизвестно» — не приговор. Отсутствие пары не доказывает ничего: '
          '«граница сдвинулась» законна и её в корпусе нет. Смотреть глазами или отдавать судье '
          '(docs/verifikatory/idioma.md).')
    print()
    if tolko_nejro:
        print(f'🔴 ПАРЫ, ЖИВУЩИЕ ТОЛЬКО В НЕЙРОСЕТЕВОМ СЛОЕ — {len(tolko_nejro)}. Смотреть первыми:')
        print('   у этих оборотов нет ни одного подтверждения от человека или книги, зато они есть')
        print('   в невычитанных текстах Claude — то есть ровно там, откуда берётся ловимый класс.')
        for s, g, n, sent in sorted(tolko_nejro, key=lambda x: -x[2])[:a.top]:
            print(f'  «{s} + {g}» · в нейросетевых текстах {n}, у человека и в книгах 0')
            print(f'      место: {sent[:110]}')
        print()
    print(f'? НЕИЗВЕСТНЫЕ ПАРЫ — топ {a.top} по употребительности объекта '
          f'(чем чаще объект в корпусе, тем весомее, что этого глагола при нём нет):')
    for s, g, chastota_obj, sent in sorted(neizv, key=lambda x: -x[2])[:a.top]:
        est = ', '.join(f'{gl}·{n}' for gl, n in po_objektu[s].most_common(6))
        print(f'  «{s} + {g}» · объект встречается {chastota_obj} раз, но НЕ с этим глаголом')
        print(f'      в корпусе с ним: {est}')
        print(f'      место: {sent[:110]}')
    if not neizv:
        print('  нет')
    return 0


if __name__ == '__main__':
    sys.exit(main())

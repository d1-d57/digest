#!/usr/bin/env python3
"""Гейт статусов блоков — канон К9 `docs/PROTOKOL-VYPUSKA.md`.

    python3 check_bloki.py <дата>-vypusk-NN

Список статусов выведен ЗАМЕРОМ по выпускам 02–04 (87 блоков, 16 разделов), а не
придуман. Строгие статусы обязаны давать восстановимое содержание: математик с
PhD, не работающий в этой области, воспроизводит объект и утверждение по тексту,
не открывая ссылок.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import proverki  # noqa: E402
from build_vypusk import split_frontmatter, parse_body, bloki, display_math  # noqa: E402

STATUSY = {
    'utverzhdenie': ('строгий', 'что верно, о чём, при каких условиях; числа выписаны'),
    'opredelenie':  ('строгий', 'объект воспроизводится по тексту, все условия на месте'),
    'vyvod':        ('строгий', 'каждое звено названо; «отсюда следует» без звена — брак'),
    'narrativ':     ('вольный', 'люди, даты, обстоятельства; математического содержания не несёт'),
    'mostik':       ('вольный', 'переход или оглавление; не имеет права нести утверждение'),
    'otsylka':      ('вольный', 'адресовано специалисту, содержания не даёт — обязана быть ссылка'),
}
STROGIE = {k for k, v in STATUSY.items() if v[0] == 'строгий'}
# «нужным образом», «в некотором смысле» — слова, которыми строгий блок притворяется
# строгим. Взяты из приговора замера: ровно на них развалились несущие блоки 03-4.4 и 04-3.3.
PUSTYSHKI = r'нужным образом|нужных|нужными|в некотором смысле|определённым образом|соответствующим образом|некоторым образом'
ZNACH = re.compile(r'[а-яёa-z]{5,}', re.I)


def povtor(a, b):
    """Доля значимых слов второй фразы, уже бывших в первой. К11: соседнее
    предложение не пересказывает предыдущее другими словами."""
    x, y = set(w.lower()[:6] for w in ZNACH.findall(a)), [w.lower()[:6] for w in ZNACH.findall(b)]
    return len([w for w in y if w in x]) / len(y) if y else 0


BLIND = ['восстановимо ли содержание на самом деле — это верификатор текста',
         'верен ли статус по существу: строгий блок можно пометить narrativ и обмануть гейт']


def bloki_prozy(it):
    return [x for _b, _st, _po, ps in bloki(it['blurb']) for x in ps]


def karta_sverka(src, rubrics, lead):
    """К12: состав блоков объявлен дважды — в карте и маркерами. Расходятся — красное."""
    errs = []
    zayavl = {}
    for l in src.split('\n'):
        m = re.match(r'^\|\s*(лид|\d+)\s*\|\s*(.+?)\s*\|$', l)
        if m and '---' not in m.group(2):
            zayavl[m.group(1)] = [x.strip() for x in m.group(2).split('·')]
    fakt = {'лид': [b[0] for b in bloki(lead)]}
    for rn, its in rubrics:
        nom = rn.split(' ·')[0].strip()
        fakt[nom] = [b for it in its for b, *_ in bloki(it['blurb'])]
    for k in sorted(set(zayavl) | set(fakt)):
        a, b = zayavl.get(k, []), fakt.get(k, [])
        if a != b:
            errs.append(f'[К12 карта] раздел {k}: в карте {a or "нет строки"}, '
                        f'в тексте {b or "блоков нет"} — карта и текст разошлись')
    return errs


def main(name):
    d = Path(__file__).parent / name
    _meta, body = split_frontmatter((d / 'vypusk.md').read_text(encoding='utf-8'))
    lead, rubrics = parse_body(body)
    errs, warns, vsego, stat = [], [], 0, {}
    errs += karta_sverka((d / 'vypusk.md').read_text(encoding='utf-8'), rubrics, lead)

    for rn, its in [('ЛИД', [{'title': 'лид', 'blurb': lead, 'meta': {}}])] + \
                   [(rn, its) for rn, its in rubrics]:
        for it in its:
            loc = f'{rn} / {it["title"]}' if rn != 'ЛИД' else 'ЛИД'
            bl = [(st, po.get('зачем',''), ps, bid, po) for bid, st, po, ps in bloki(it['blurb'])]
            est_strogij = False
            for status, zachem, ps, bid, po in bl:
                vsego += 1
                if status is None:
                    errs.append(f'[К9] {loc}: абзацы без маркера блока → «{ps[0][:60]}…»')
                    continue
                if status not in STATUSY:
                    errs.append(f'[К9] {loc}: статус «{status}» вне закрытого списка '
                                f'({", ".join(STATUSY)})')
                    continue
                stat[status] = stat.get(status, 0) + 1
                for pole in ('мысль', 'опирается', 'объём'):
                    if not po.get(pole) or po.get(pole) == 'заполнить':
                        errs.append(f'[К12] {loc}: у блока {bid} не заполнено поле «{pole}»')
                if len(zachem) < 12:
                    errs.append(f'[К9] {loc}: у блока «{status}» не сказано, зачем он нужен')
                if status in STROGIE:
                    est_strogij = True
                    for p in ps:
                        if display_math(p):
                            continue
                        m = re.search(PUSTYSHKI, p, re.I)
                        if m:
                            errs.append(f'[К9 пустышка] {loc}: строгий блок «{status}» держится '
                                        f'на слове «{m.group(0)}» — оно замещает содержание')
                if status == 'otsylka' and not (it['meta'].get('links') or []):
                    errs.append(f'[К9] {loc}: блок otsylka есть, а ссылок в разделе нет — '
                                f'отсылка обязана вести наружу')
                if status == 'mostik':
                    for p in ps:
                        if re.search(r'\d{4}|\d+[,.]\d+', p):
                            warns.append(f'[К9] {loc}: mostik несёт число — похоже, это '
                                         f'utverzhdenie, а не переход')
            # Аксиомы, выведенные замером по выпускам 01–04 (см. PROTOKOL §Аксиомы)
            if rn != 'ЛИД':
                sts = [b[0] for b in bl if b[0]]
                if len(sts) > 4 or len(sts) < 2:
                    errs.append(f'[А1] {loc}: блоков {len(sts)} — норма 2–3, четыре это уже '
                                f'редкость для очень большого раздела (замер: 02 — 2,83, 03 — 3,25)')
                elif len(sts) == 4:
                    warns.append(f'[А1] {loc}: четыре блока — допустимо, но только для очень '
                                 f'большого раздела; норма 2–3')
                if sts and sts[-1] not in ('utverzhdenie', 'vyvod'):
                    errs.append(f'[А2] {loc}: раздел кончается блоком «{sts[-1]}» — '
                                f'кончать надо утверждением или выводом')
                if sts.count('narrativ') > 1:
                    errs.append(f'[А3] {loc}: нарративов {sts.count("narrativ")}, допустим один')
                for a, b2 in zip(sts, sts[1:]):
                    if a == b2 == 'narrativ':
                        errs.append(f'[А4] {loc}: два нарратива подряд')
                if sts.count('opredelenie') > 1:
                    errs.append(f'[А8] {loc}: определений {sts.count("opredelenie")}, допустимо одно')
                if sts.count('vyvod') > 1:
                    errs.append(f'[А8] {loc}: выводов {sts.count("vyvod")}, допустим один')
                if 'opredelenie' in sts and 'vyvod' in sts and \
                        sts.index('opredelenie') > sts.index('vyvod'):
                    errs.append(f'[А9] {loc}: определение стоит после вывода')
                for st, zach, ps, bid, po in bl:
                    proza = ' '.join(p for p in ps if not display_math(p))
                    frazy = [f.strip() for f in re.split(r'(?<=[.!?])\s+', proza) if len(f) > 25]
                    for f1, f2 in zip(frazy, frazy[1:]):
                        if povtor(f1, f2) > 0.6:
                            errs.append(f'[К11 повтор] {loc}: фраза пересказывает предыдущую → '
                                        f'«{f2[:70]}…»')
                    if st == 'narrativ' and re.search(r'\$[^$]+\$', proza):
                        errs.append(f'[К11] {loc}: формула в блоке narrativ')
                    n = sum(len(x) for x in ps)
                    if st and n and not 300 <= n <= 900:
                        warns.append(f'[А20] {loc}: блок «{st}» {n} знаков, норма 400–700')
            if rn != 'ЛИД' and not est_strogij:
                errs.append(f'[К9] {loc}: в разделе нет ни одного строгого блока — '
                            f'раздел ничего не даёт восстановить')

    # К13: ядро может быть длиннее, обычный раздел — нет
    dl = {rn: sum(len(x) for it in its for x in bloki_prozy(it)) for rn, its in rubrics}
    if dl:
        med = sorted(dl.values())[len(dl) // 2]
        s_form = {rn: any('$$' in x for it in its for x in bloki_prozy(it))
                  for rn, its in rubrics}
        yad = next((rn for rn, v in s_form.items() if v), max(dl, key=dl.get))
        for rn, n in dl.items():
            if rn != yad and n > med * 1.4:
                warns.append(f'[К13] {rn}: {n} знаков при медиане {med} — обычный раздел '
                             f'не должен тянуться к ядру ({yad}, {dl[yad]})')
        if dl[yad] > med * 2:
            warns.append(f'[К13] ядро {yad}: {dl[yad]} при медиане {med} — больше двух медиан')

    doly = {k: round(100 * v / max(1, vsego)) for k, v in sorted(stat.items())}
    if doly.get('narrativ', 0) > 20:
        errs.append(f'[А5] нарратива {doly["narrativ"]} % при норме не больше 20 '
                    f'(замер: 02 — 18 %, 03 — 15 %)')
    if doly.get('utverzhdenie', 0) < 40:
        errs.append(f'[А6] утверждений {doly.get("utverzhdenie", 0)} % при норме не меньше 40 '
                    f'(замер: 02 — 59 %, 03 — 46 %)')
    print(f'Блоков: {vsego}. Доли: ' + ', '.join(f'{k} {v}%' for k, v in doly.items()))
    volny = sum(v for k, v in stat.items() if k not in STROGIE)
    if volny > vsego * 0.5:
        warns.append(f'[К9] вольных блоков {volny} из {vsego} — больше половины выпуска '
                     f'ничего не даёт восстановить')
    print('\nНЕ проверяю:')
    for b in BLIND:
        print(f'   · {b}')
    print()
    for w in warns:
        print('⚠ ' + w)
    for e in errs:
        print('✗ ' + e)
    if errs:
        print(f'\n✗ гейт блоков красный: {len(errs)} ошибок, {len(warns)} подозрений')
        return 1
    print(f'\n✓ гейт блоков зелёный ({len(warns)} подозрений)')
    proverki.avtomark(d, 'bloki', f'{vsego} блоков размечены, доли {doly}')
    return 0


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))

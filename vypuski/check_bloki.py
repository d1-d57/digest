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


def proza_blokov(d: Path):
    """{идентификатор блока: его проза под ====} — для проверок, которым нужен текст."""
    src = (d / 'vypusk.md').read_text(encoding='utf-8')
    out, tek, vnutri = {}, None, False
    for l in src.split('\n'):
        m = re.match(r'^%%\s+(\S+)\s+·', l)
        if m:
            tek, vnutri = m.group(1), False
            out[tek] = []
            continue
        if l.startswith('===='):
            vnutri = True
            continue
        if l.startswith(('- link', '- areas', '# ', '## ')):
            vnutri = False
            continue
        if vnutri and tek and l.strip():
            out[tek].append(l)
    return {k: '\n'.join(v) for k, v in out.items()}


def bloki_teksta_ids(d: Path):
    """Множество идентификаторов блоков из маркеров `%%` — по нему судим место ввода."""
    src = (d / 'vypusk.md').read_text(encoding='utf-8')
    return {m.group(1) for m in re.finditer(r'^%%\s+(\S+)\s+·', src, re.M)}


def roli_inventarya(d: Path, est_bloki):
    """Носитель условия 4 гейта фазы `karta`: роли инвентаря и место ввода.

    🔴 Почему проверка живёт ЗДЕСЬ, а не в `check_ponyatiya.py`, где такой же
    разбор уже есть. Условие объявлено в `docs/fazy/karta.md` гейтом ФАЗЫ КАРТЫ,
    а `check_ponyatiya` стоит в реестре фаз `ponyatnost` и `stil` — то есть на
    фазе `karta` он не зовётся ни разу. Условие было, носитель был, но в другой
    фазе: карта закрывалась, ничего про роли не проверив, а ловилось это через
    две фазы, когда переназначать роль уже дорого. Аудит 16.08 насчитал два
    таких условия «носитель есть, но не на своей фазе».

    Решение (список ролей, какие роли обязаны называть блок) НЕ дублируется:
    оно импортируется из `check_ponyatiya`. Здесь только вызов на своей фазе.

    ⚠ Инвентарь может ещё не существовать: на фазе `karta` его пишут по ходу.
    Нет файла — это забота гейта фазы `ponyatnost`, здесь молчим.
    """
    pf = d / 'PONYATIYA.md'
    if not pf.exists():
        return []
    import check_ponyatiya as cp                                  # noqa: E402
    errs = []
    for ponyatie, rol, vvod, stroka in cp.inventar(pf.read_text(encoding='utf-8')):
        if rol not in cp.ROLI:
            errs.append(f'[К7 роль] PONYATIYA.md строка {stroka}: роль «{rol}» вне списка '
                        f'({" · ".join(sorted(cp.ROLI))}) — понятие без роли вырезается, '
                        f'а не остаётся необъяснённым')
        elif rol in cp.OBYAZANY and vvod not in est_bloki:
            errs.append(f'[К7 место] PONYATIYA.md строка {stroka}: «{ponyatie}» ({rol}) '
                        f'вводится в блоке {vvod}, а такого блока в карте нет')
    return errs


# Обороты, которыми РАЗВОРАЧИВАЮТ определение. Список узкий намеренно: широкий
# («это», «то есть») ловит половину текста — проверено, давал шесть ложных из шести.
OPREDELYAET = re.compile(r'—\s*тех,\s*(?:где|у)\b|—\s*те,\s*(?:где|у)\b'
                         r'|\bназыва(?:ют|ется|ем)\b|\bэто\s+(?:те|такие)\b')
OKNO = 140          # знаков после термина, в которых ищем разворачивающий оборот


def opredelenie_dvazhdy(d, tekst_blokov):
    """Понятие разворачивается ровно в одном месте — носитель класса 2 замечаний 16.08.

    🔴 ОТКУДА. Владелец, читая выпуск 4: «решётчатые упаковки» разворачиваются и в
    лиде (Л2), и в блоке 1.2 — «какая-то странная вещь, когда в двух местах даётся
    определение». Отдельно: «вводить такое в лиде, который могут не прочитать»,
    неправильно; там достаточно беглого описания без ввода термина.

    `check_ponyatiya.py` проверяет ПОРЯДОК (введено не позже, чем употреблено) и
    второе определение поймать не может: оно стоит ПОЗЖЕ первого и порядка не
    нарушает. Здесь считается другое — в скольких блоках термин стоит рядом с
    разворачивающим оборотом.

    🔴 ПОЧЕМУ ТАК УЗКО. Первая редакция искала обрубок корня первого слова термина
    в любом месте блока и дала шесть ложных срабатываний из шести: «решётка $E_8$»
    находилась в каждом блоке со словом «решётка», а «плотность упаковки» — всюду.
    Гейт, красный на здоровом, отключают целиком вместе со всем остальным. Поэтому:
    все значимые слова термина обязаны стоять В ОДНОМ ОКНЕ, и оборот ищется только
    внутри {OKNO} знаков после них.

    ⚠ Регрессии на принятых выпусках нет по построению: у 01–03 нет `PONYATIYA.md`,
    функция выходит сразу. То есть замер на них невозможен, а не пропущен.
    """
    pf = d / 'PONYATIYA.md'
    if not pf.exists():
        return []
    import check_ponyatiya as cp                                  # noqa: E402
    errs = []
    for ponyatie, rol, vvod, _s in cp.inventar(pf.read_text(encoding='utf-8')):
        if rol not in cp.OBYAZANY:
            continue
        slova = [w.lower()[:6] for w in re.findall(r'[А-Яа-яЁё]{6,}', ponyatie)]
        # 🔴 Однословные термины НЕ судим. «решётка $E_8$» даёт единственный корень
        # «решётк», который стоит в каждом блоке про решётки, — и детектор объявлял
        # определением любое соседство. Два слова минимум: тогда совпадение окна
        # означает термин, а не общее слово. Отличать «решётку E_8» от «решётки
        # Лича» надо по формуле, а её этот детектор не читает.
        if len(slova) < 2:
            continue
        gde = []
        for bid, proza in tekst_blokov.items():
            nz = proza.lower()
            poz0 = [m.start() for m in re.finditer(re.escape(slova[0]), nz)]
            nashli = False
            for p0 in poz0:
                okno = nz[p0:p0 + OKNO]
                if all(s in okno for s in slova[1:]) and OPREDELYAET.search(okno):
                    nashli = True
                    break
            if nashli:
                gde.append(bid)
        if len(gde) > 1:
            errs.append(f'[К7 дважды] «{ponyatie}» разворачивается определением в блоках '
                        f'{" · ".join(gde)} — место ввода одно, остальные пользуются термином '
                        f'голым. В лиде понятия не вводятся вовсе: его могут не прочитать')
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
            # Аксиомы раскладки. Дом формулировок — docs/kanony.md, раздел «Аксиомы
            # раскладки»: там же сказано, на каком замере выведена каждая и у каких
            # замера нет. Прежняя ссылка вела в `PROTOKOL §Аксиомы` — такого раздела
            # нет и не было, то есть носитель правила был нечитаем (найдено 16.08).
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
    errs += roli_inventarya(d, bloki_teksta_ids(d))
    errs += opredelenie_dvazhdy(d, proza_blokov(d))

    for e in errs:
        print('✗ ' + e)
    if errs:
        print(f'\n✗ гейт блоков красный: {len(errs)} ошибок, {len(warns)} подозрений')
        proverki.snyat(d, 'bloki')
        return 1
    print(f'\n✓ гейт блоков зелёный ({len(warns)} подозрений)')
    proverki.avtomark(d, 'bloki', f'{vsego} блоков размечены, доли {doly}')
    return 0


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))

#!/usr/bin/env python3
"""Сверка текста с раскладкой: доехало ли до текста то, что обещано на фазе 1.

    python3 istochniki.py <дата>-vypusk-NN

Проверяет три вещи, которые до сих пор держались вниманием:
  · каждое ЧИСЛО и ГОД из выписываемого утверждения раздела есть в тексте этого раздела
    (утверждение, обещанное раскладкой и не доехавшее в текст, — самая дорогая потеря фазы 2);
  · ссылки не дублируются по URL;
  · у каждого раздела число ссылок совпадает с назначенным в раскладке.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import proverki  # noqa: E402
from build_vypusk import split_frontmatter, parse_body  # noqa: E402

BLIND = ['доехало ли САМО утверждение, а не его числа — это верификатор текста',
         'верен ли источник по существу — это гейт 0 разведки, вход фазы 1']


def main(name):
    d = Path(__file__).parent / name
    rask = (d / 'RASKLADKA.md').read_text(encoding='utf-8')
    _meta, body = split_frontmatter((d / 'vypusk.md').read_text(encoding='utf-8'))
    _lead, rubrics = parse_body(body)
    items = [it for _rn, its in rubrics for it in its]

    rows = {}
    for l in rask.split('\n'):
        m = re.match(r'^\|\s*(\d+)\s*\|', l)
        if m:
            c = [x.strip() for x in l.strip('|').split('|')]
            rows[int(m.group(1))] = c

    errs, urls = [], {}
    for i, it in enumerate(items, 1):
        c = rows.get(i)
        if not c:
            errs.append(f'раздел {i}: нет строки в раскладке')
            continue
        utv, ssy = c[3], c[5]
        tekst = it['blurb'].replace('{,}', ',').replace('{.}', '.')
        # числа утверждения: годы и величины, кроме одиночных цифр-порядков
        nums = [n for n in re.findall(r'\d[\d  ,.]*\d|\d', utv) if len(n) > 1]
        poteryano = [n for n in nums if n.replace(' ', '') not in tekst.replace(' ', '')]
        if poteryano:
            errs.append(f'раздел {i}: числа из выписываемого утверждения не найдены в тексте — '
                        f'{", ".join(poteryano)}')
        want = int(re.findall(r'\d+', ssy)[0])
        got = len(it['meta'].get('links') or [])
        if want != got:
            errs.append(f'раздел {i}: ссылок {got}, раскладка назначала {want}')
        for ln in (it['meta'].get('links') or []):
            urls.setdefault(ln['url'], []).append(i)

    for u, gde in urls.items():
        if len(gde) > 1:
            errs.append(f'ссылка повторяется в разделах {gde}: {u}')

    print('НЕ проверяю:')
    for b in BLIND:
        print(f'   · {b}')
    print()
    for e in errs:
        print('✗ ' + e)
    if errs:
        print(f'\n✗ сверка с раскладкой красная: {len(errs)}')
        return 1
    print('✓ сверка с раскладкой сошлась: числа утверждений доехали, ссылки без дублей\n')
    proverki.avtomark(d, 'istochniki',
                      'числа выписываемых утверждений найдены в своих разделах, ссылки без дублей, '
                      'число ссылок совпадает с раскладкой')
    return proverki.gate(d, 2)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))

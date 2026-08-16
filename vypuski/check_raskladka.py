#!/usr/bin/env python3
"""Гейт выхода фазы 1 — счётное по раскладке.

    python3 check_raskladka.py <дата>-vypusk-NN

Стилевое (пересказывается ли логика тремя фразами) — не сюда, это верификатор-субагент.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import proverki  # noqa: E402

BLIND = [
    'пересказывается ли логика разделов тремя фразами (верификатор)',
    'отличается ли утверждение раздела от соседних (верификатор)',
    'есть ли раздел, на который не опирается ни один другой (верификатор)',
]


def main(name):
    f = Path(__file__).parent / name / 'RASKLADKA.md'
    if not f.exists():
        print(f'✗ нет {f} — породи bootstrap_vypuska.py')
        return 1
    t = f.read_text(encoding='utf-8')
    errs = []

    n = t.count('заполнить')
    if n:
        errs.append(f'{n} незаполненных полей')

    rows = [l for l in t.split('\n') if re.match(r'^\|\s*\d+\s*\|', l)]
    if not rows:
        errs.append('таблица разделов пуста')
    total = 0
    for l in rows:
        c = [x.strip() for x in l.strip('|').split('|')]
        if len(c) < 6:
            errs.append(f'строка раздела неполная: {l.strip()}')
            continue
        num, _name, _pro, utv, byu, ssy = c[:6]
        if not utv or utv == '—':
            errs.append(f'раздел {num}: пустое выписываемое утверждение')
        if byu.isdigit():
            total += int(byu)
        else:
            errs.append(f'раздел {num}: бюджет не число → «{byu}»')
        k = len(re.findall(r'\d+', ssy)) and int(re.findall(r'\d+', ssy)[0])
        if not 2 <= (k or 0) <= 3:
            errs.append(f'раздел {num}: ссылок {ssy} — надо 2–3, и ни одного раздела без ссылки')

    m = re.search(r'^potolok_prozy:\s*(\d+)', t, re.M)
    if m and total > int(m.group(1)):
        errs.append(f'сумма бюджетов {total} больше потолка {m.group(1)} — режь структуру, '
                    f'а не текст: текста ещё нет, в этом весь смысл раннего реза')

    if not re.search(r'^formula_v_razdele:\s*\d+', t, re.M):
        errs.append('не назван раздел с единственной выключной формулой')
    if not re.search(r'^rezhim:\s*(хроника|лестница)\s*(#.*)?$', t, re.M):
        errs.append('режим не назван: хроника или лестница (К6)')

    prinyato = len(re.findall(r'^ПРИНЯТО фаза-1:', t, re.M))
    if prinyato != 1:
        errs.append(f'строк «ПРИНЯТО фаза-1:» ровно {prinyato}, нужна одна — '
                    f'приёмка это строка в файле, а не согласие в чате (Н4)')

    print('НЕ проверяю:')
    for b in BLIND:
        print(f'   · {b}')
    print()
    for e in errs:
        print('✗ ' + e)
    if errs:
        print(f'\n✗ гейт фазы 1 красный: {len(errs)}')
        return 1
    proverki.avtomark(f.parent, 'check_raskladka',
                      'счётное по раскладке: поля, бюджеты, утверждения, ссылки, приёмка')
    print('✓ счётное по раскладке сошлось\n')
    # Верификатор — часть гейта, а не пожелание: без зелёного вердикта фаза не закрыта.
    return proverki.gate(f.parent, 'raskladka')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))

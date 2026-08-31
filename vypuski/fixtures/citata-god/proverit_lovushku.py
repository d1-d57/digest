#!/usr/bin/env python3
"""Ловушка «цитата-год»: RASKLADKA.md в этой папке несёт ssylki-клетку
«2 [Клартаг 2025]» — число вначале, за которым идёт цитата с годом. Гейт
`check_raskladka.py` обязан отклонить такую клетку как нечистое число.

    python3 vypuski/fixtures/citata-god/proverit_lovushku.py

Ничего не пишет: запускает check_raskladka.py как подпроцесс на СЕБЕ и читает
stdout, не даёт исполнению дойти до proverki.avtomark (та ветка требует
errs == [], а ловушка обязана дать errs != []).
"""
import subprocess
import sys
from pathlib import Path

FIXTURE = Path(__file__).resolve().parent
GATE = FIXTURE.parent.parent / 'check_raskladka.py'
OZHIDAETSYA = 'должно быть число от 2 до 3'


def main():
    p = subprocess.run([sys.executable, str(GATE), str(FIXTURE)],
                        capture_output=True, text=True)
    poimana = OZHIDAETSYA in p.stdout
    if poimana:
        print(f'✓ ловушка «цитата-год» сработала: «{OZHIDAETSYA}» найдено в выводе гейта')
        return 0
    print(f'✗ ловушка «цитата-год» МОЛЧИТ: «{OZHIDAETSYA}» не найдено в выводе гейта — '
          f'клетка «2 [Клартаг 2025]» прошла как чистое число')
    print('--- stdout гейта ---')
    print(p.stdout)
    return 1


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
"""Проба: берёт ли RuCoLA-классификатор незаконную русскую математическую идиому.

    python3 vypuski/probe_rucola.py                              # из корня репозитория
    python3 vypuski/probe_rucola.py --vypusk vypuski/2026-08-08-vypusk-03

ЗАЧЕМ. У фазы `stil` есть класс дефектов, который `check_stil.py` не ловит и ловить не может:
незаконная идиома («граница ушла» при законном «граница сдвинулась»). Синтаксический путь
закрыт разведкой 16.08 — переходность глагола границу не проводит. Здесь проверяется
следующий кандидат: классификатор приемлемости, обученный на корпусе RuCoLA.

ПРОДУКТ — ЧИСЛО, а не мнение: сколько пар «незаконно/законно» модель разделяет и какой порог
даёт ноль ложных срабатываний на уже ПРИНЯТОМ владельцем материале. Отрицательный результат —
полноценный ответ: он закрывает направление.

ТЕРМИНЫ (определяются здесь, до первого рабочего употребления):
  ПАРА          — одно предложение в двух вариантах, различающихся только оборотом; поля
                  `nezakonno` и `zakonno` файла `vypuski/pary_idiom.jsonl`.
  p_neprijem    — вероятность класса «неприемлемо», выданная моделью для одного предложения.
                  Какой индекс класса это означает, берётся из `config.json → id2label`
                  и дополнительно ПРОВЕРЯЕТСЯ замером на контрольной паре (см. `metka_neprijem`).
  ПАРА РАЗДЕЛЕНА — p_neprijem(nezakonno) > p_neprijem(zakonno) строго. Сравнение внутри пары,
                  порог не нужен.
  ПОРОГ T       — абсолютная отсечка: предложение с p_neprijem > T помечается подозрением.
                  Требование строже разделения пары, и число разделённых по нему будет меньше.
  СТРОГИЙ БЛОК  — блок выпуска с типом `utverzhdenie`, `opredelenie` или `vyvod`.

🔴 ПОЛОСА А · ЯДРО — файл уедет в скилл финальной правки, который заменит `russian-editor`.
   Что мешает переносу: стенд для любой модели-кандидата, жанрово нейтрален.
   Граница скилла и вопросы владельцу — `zhurnal/2026-08-15_vypusk-04/KARTA-PERENOSA-v-skill.md`.
"""
import json
import math
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

KOREN = Path(__file__).resolve().parent.parent
PARY = KOREN / 'vypuski' / 'pary_idiom.jsonl'
PAR_OZHIDAETSYA = 23
VYPUSKI_KALIBROVKI = [
    KOREN / 'vypuski' / '2026-08-01-vypusk-02' / 'vypusk.razmechen.md',
    KOREN / 'vypuski' / '2026-08-08-vypusk-03' / 'vypusk.razmechen.md',
]
OHVAT_ANALITIKA = (39, 32, 140)   # блоков, строгих, предложений — замер 2026-08-16
STROGIE = {'utverzhdenie', 'opredelenie', 'vyvod'}
PORQG_OSTANOVKI = 16              # разделено меньше — переходим к следующей модели

MODELI = [
    ('p1746-lingua/ruRoberta-large-rucola-science', 'дообучена на НАУЧНЫХ текстах поверх rucola'),
    ('RussianNLP/ruRoBERTa-large-rucola', 'эталонная от авторов корпуса'),
    ('d0rj/RuModernBERT-small-rucola', 'маленькая, CPU; требует transformers>=4.48'),
]

# Контрольная пара для проверки ЗНАКА метки: грамматически ломаное против целого.
# Не про идиому — про то, что модель вообще смотрит в ту сторону, в которую мы думаем.
KONTROL_LOMANOE = 'Мальчик читают книга на столом.'
KONTROL_CELOE = 'Мальчик читает книгу за столом.'

VENV = Path.home() / '.cache' / 'matemdigest-rucola' / 'venv'


def bootstrap():
    """Ставит torch (CPU) и transformers в отдельный venv и перезапускает себя в нём.

    Репозиторий и системный питон не трогаются: venv лежит вне репо. Флаг в окружении
    защищает от бесконечного перезапуска, если установка прошла, а импорт всё равно упал.
    """
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
        return
    except ImportError:
        pass
    if os.environ.get('PROBE_RUCOLA_BOOTSTRAP') == '1':
        print('✗ torch/transformers не импортируются даже после установки — останавливаюсь')
        sys.exit(1)
    py = VENV / 'bin' / 'python'
    if py.exists() and subprocess.run(
            [str(py), '-c', 'import torch, transformers'],
            capture_output=True).returncode == 0:
        os.environ['PROBE_RUCOLA_BOOTSTRAP'] = '1'
        os.execv(str(py), [str(py), str(Path(__file__).resolve())] + sys.argv[1:])
    if not py.exists():
        baza = None
        for kand in ('python3.12', 'python3.13', 'python3.11', sys.executable):
            put = Path.home() / '.local' / 'bin' / kand if not kand.startswith('/') else Path(kand)
            if put.exists():
                baza = str(put)
                break
        if baza is None:
            baza = sys.executable
        print(f'· среды нет, завожу venv в {VENV} на {baza}', flush=True)
        subprocess.run([baza, '-m', 'venv', str(VENV)], check=True)
    print('· ставлю torch (CPU) и transformers — первый запуск, это минуты', flush=True)
    subprocess.run([str(py), '-m', 'pip', 'install', '-q', '--upgrade', 'pip'], check=True)
    subprocess.run([str(py), '-m', 'pip', 'install', '-q', 'torch',
                    '--index-url', 'https://download.pytorch.org/whl/cpu'], check=True)
    subprocess.run([str(py), '-m', 'pip', 'install', '-q', 'transformers>=4.48'], check=True)
    os.environ['PROBE_RUCOLA_BOOTSTRAP'] = '1'
    os.execv(str(py), [str(py), str(Path(__file__).resolve())] + sys.argv[1:])


bootstrap()

import torch                                    # noqa: E402
from transformers import (AutoModelForSequenceClassification,  # noqa: E402
                          AutoTokenizer)

sys.path.insert(0, str(KOREN / 'vypuski'))
from check_stil import bloki                    # noqa: E402  переиспользуется, не переписывается


# ─────────────────────────────────────────────────────────── материал

def chitat_pary():
    pary = []
    for stroka in PARY.read_text(encoding='utf-8').splitlines():
        if not stroka.strip():
            continue
        zap = json.loads(stroka)
        if 'id' not in zap:          # служебная первая строка с ключом `_`
            continue
        pary.append(zap)
    return pary


def predlozheniya(proza):
    """Разбиение задано заходом, а не выбирается: другой метод даст другое P."""
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', proza.strip())
            if len(s.split()) > 2]


def proza_vypuskov(puti, tolko_strogie=True):
    """Возвращает (блоков, строгих, [(файл, блок, тип, предложение)])."""
    vsego_blokov = 0
    strogih = 0
    kuski = []
    for put in puti:
        bl = bloki(put.read_text(encoding='utf-8'))
        vsego_blokov += len(bl)
        for nom, tip, _mysl, _zachem, proza in bl:
            strogij = tip in STROGIE
            if strogij:
                strogih += 1
            if tolko_strogie and not strogij:
                continue
            for s in predlozheniya(proza):
                kuski.append((put.parent.name, nom, tip, s))
    return vsego_blokov, strogih, kuski


# ─────────────────────────────────────────────────────────── модель

class Klassifikator:
    def __init__(self, imya):
        self.imya = imya
        self.tok = AutoTokenizer.from_pretrained(imya)
        self.mod = AutoModelForSequenceClassification.from_pretrained(imya)
        self.mod.eval()
        self.id2label = dict(self.mod.config.id2label)
        self.idx_neprijem, self.osnovanie = self._metka_neprijem()

    def _metka_neprijem(self):
        """Индекс класса «неприемлемо» — из id2label, а не из номера класса.

        У разных авторов порядок разный; перепутанный знак даст «модель разделяет всё
        наоборот» вместо честного результата.
        """
        for i, lab in self.id2label.items():
            n = str(lab).lower()
            if any(k in n for k in ('unaccept', 'неприем', 'incorrect', 'ungrammat', 'bad')):
                return int(i), f'id2label[{i}]={lab!r} — прямое имя класса'
        for i, lab in self.id2label.items():
            n = str(lab).lower()
            if any(k in n for k in ('accept', 'приемл', 'correct', 'grammat', 'good')):
                drugoy = [int(j) for j in self.id2label if int(j) != int(i)]
                if len(drugoy) == 1:
                    return drugoy[0], (f'id2label[{i}]={lab!r} — «приемлемо», '
                                       f'значит «неприемлемо» это {drugoy[0]}')
        # Безымянные LABEL_0/LABEL_1: соглашение корпуса RuCoLA — 1 = acceptable, 0 = нет.
        return 0, ('имена классов безымянные (%s) — взято соглашение RuCoLA '
                   '«1 = приемлемо, 0 = неприемлемо»' % self.id2label)

    def p(self, teksty, paket=16):
        out = []
        for i in range(0, len(teksty), paket):
            kus = teksty[i:i + paket]
            vh = self.tok(kus, return_tensors='pt', padding=True,
                          truncation=True, max_length=512)
            with torch.no_grad():
                log = self.mod(**vh).logits
            out += torch.softmax(log, dim=-1)[:, self.idx_neprijem].tolist()
        return out

    def proverka_znaka(self):
        """Замер, а не допущение: ломаное предложение обязано получить p выше целого."""
        pl, pc = self.p([KONTROL_LOMANOE, KONTROL_CELOE])
        return pl, pc, pl > pc


# ─────────────────────────────────────────────────────────── шаги

def shag1_pary():
    print('=' * 78)
    print('ШАГ 1 · ПАРЫ')
    print('=' * 78)
    pary = chitat_pary()
    n = len(pary)
    print(f'пар в файле: {n}')
    if n != PAR_OZHIDAETSYA:
        print(f'🔴 КРАСНОЕ: ожидалось {PAR_OZHIDAETSYA} пар, в файле {n} — '
              f'файл разъехался с заходом. Останавливаюсь.')
        sys.exit(1)
    print(f'✓ сходится с заходом ({PAR_OZHIDAETSYA})')
    print()
    return pary


def shag3_razdelenie(klf, pary):
    """Считает разделение пар. Число X считает код, не человек."""
    p_nez = klf.p([z['nezakonno'] for z in pary])
    p_zak = klf.p([z['zakonno'] for z in pary])
    stroki = []
    for z, pn, pz in zip(pary, p_nez, p_zak):
        stroki.append({**z, 'p_nez': pn, 'p_zak': pz, 'razdelena': pn > pz})
    n = len(stroki)
    x = sum(1 for s in stroki if s['razdelena'])

    # Вероятности печатаются В НАУЧНОЙ ЗАПИСИ, а не с четырьмя знаками после точки.
    # Причина не косметическая: у части моделей обе вероятности пары меньше 1e-4, и при
    # округлении до 0.0000 столбцы становятся неразличимы — верификатор, которому заход
    # велит ПЕРЕСЧИТАТЬ `разделено X из N` по этой таблице, физически не может этого сделать.
    print(f'{"id":<4} {"klass":<13} {"zamena_ot":<10} {"p_nezak":>11} {"p_zak":>11}  разделена')
    print('-' * 78)
    for s in stroki:
        print(f'{s["id"]:<4} {s["klass"]:<13} {s["zamena_ot"]:<10} '
              f'{s["p_nez"]:>11.4e} {s["p_zak"]:>11.4e}  {"да" if s["razdelena"] else "НЕТ"}')
    print('-' * 78)
    print(f'разделено {x} из {n}')
    print()

    print('РАСПРЕДЕЛЕНИЕ (collections.Counter; клетка с нулём — мёртвая клетка или '
          'непокрытый случай, и видно это только так)')
    for pole in ('klass', 'zamena_ot'):
        vsego = Counter(s[pole] for s in stroki)
        razd = Counter(s[pole] for s in stroki if s['razdelena'])
        print(f'  по `{pole}`:')
        for k in sorted(vsego):
            print(f'    {k:<14} разделено {razd[k]} из {vsego[k]}')
    print()
    # Ориентир «около 11–12» заход даёт словами; здесь он же считается точно, чтобы
    # «14 из 23» не выглядело успехом на глаз. p — вероятность получить X и больше
    # разделённых пар ЧИСТО СЛУЧАЙНО, при честной монетке.
    p_sluchayno = sum(math.comb(n, k) for k in range(x, n + 1)) / 2 ** n
    print(f'ориентир: на {n} парах монетка даёт около 11–12 разделённых; '
          f'ниже {PORQG_OSTANOVKI} читается как «не разделяет», а не как частичный успех')
    print(f'  вероятность получить {x} и больше случайно (честная монетка, n={n}): '
          f'p = {p_sluchayno:.4f}'
          f'{"  — от случайности НЕ отличимо" if p_sluchayno > 0.05 else "  — случайностью не объясняется"}')
    print()
    return stroki, x, n


def shag4_porog(klf, stroki, n_par):
    print('=' * 78)
    print('ШАГ 4 · ПОРОГ ЗАМЕРОМ (из статьи и из карточки модели НЕ берётся)')
    print('=' * 78)
    m, s, kuski = proza_vypuskov(VYPUSKI_KALIBROVKI)
    p_kol = len(kuski)
    print(f'блоков {m}, строгих {s}, предложений {p_kol}')
    if (m, s, p_kol) != OHVAT_ANALITIKA:
        print(f'🔴 КРАСНОЕ: замер аналитика 2026-08-16 тем же методом давал '
              f'{OHVAT_ANALITIKA[0]}/{OHVAT_ANALITIKA[1]}/{OHVAT_ANALITIKA[2]} — файлы '
              f'изменились. Останавливаюсь, вопрос владельцу.')
        sys.exit(1)
    print(f'✓ сходится с замером аналитика 2026-08-16 '
          f'({OHVAT_ANALITIKA[0]}/{OHVAT_ANALITIKA[1]}/{OHVAT_ANALITIKA[2]}); '
          f'метод разбиения — re.split(r\'(?<=[.!?])\\s+\', proza), куски длиннее двух слов')
    print('материал: проза СТРОГИХ блоков выпусков 02 и 03, ПРИНЯТЫХ владельцем — '
          'значит ложных срабатываний на них быть не должно')
    print()

    p_prinyatyh = klf.p([k[3] for k in kuski])
    pary_sorted = sorted(zip(p_prinyatyh, kuski), key=lambda t: -t[0])

    def razdelyaet_porogom(T):
        return sum(1 for st in stroki if st['p_nez'] > T and st['p_zak'] <= T)

    # Порог с НУЛЁМ ложных срабатываний — ровно то, что просит заход.
    maks = max(p_prinyatyh)
    T0 = maks
    print(f'максимум p_neprijem на принятом материале: {maks:.6f} '
          f'(предложение: «{pary_sorted[0][1][3][:60]}…», блок {pary_sorted[0][1][1]} '
          f'выпуска {pary_sorted[0][1][0]})')
    print(f'порог {T0:.6f} выведен замером: ложных срабатываний 0 из {p_kol}')
    print(f'  этим порогом разделяется пар: {razdelyaet_porogom(T0)} из {n_par} '
          f'(незаконное строго выше порога, законное не выше)')
    print()
    print('«почти ноль» — тот же замер при допущенных ложных срабатываниях '
          '(заход разрешает, если названо сколько и какие именно):')
    print(f'  {"Y ложных":<10} {"порог T":>9} {"пар разделено":>15}   выброшенные предложения')
    for y in (1, 2, 3, 5):
        if y >= p_kol:
            break
        T = pary_sorted[y][0]
        # Нумерация нужна: два РАЗНЫХ предложения могут лежать в одном блоке, и без номера
        # список выглядит как повтор одного и того же имени.
        imena = ', '.join(f'#{i + 1} {k[0].split("-")[-1]}/{k[1]}'
                          for i, (_p, k) in enumerate(pary_sorted[:y]))
        print(f'  {y:<10} {T:>9.6f} {razdelyaet_porogom(T):>15}   {imena}')
    print()
    print('ТОП-5 принятых предложений по p_neprijem — на них модель ошибается сильнее всего:')
    for p, k in pary_sorted[:5]:
        print(f'  {p:.4f}  {k[0]} · {k[1]} · {k[3][:80]}')
    print()
    return T0, p_kol, {(k[0], k[3]) for k in kuski}


def shag5_ohvat(pary, p_kol, imya_modeli):
    n_par = len(pary)
    ot_analitika = sum(1 for z in pary if z.get('zamena_ot') == 'analitik')
    print('=' * 78)
    print('ЧЕГО ЭТОТ ПРОГОН НЕ ПРОВЕРЯЕТ')
    print('=' * 78)
    print(f'1. Пары КОРОТКИЕ и вырваны из абзаца. Модель видит одно предложение без контекста;')
    print(f'   в живом выпуске незаконный оборот стоит внутри абзаца, и соседние фразы могут')
    print(f'   менять оценку. Проверено ровно то, что проверено: {n_par} изолированных пар.')
    print(f'2. У {ot_analitika} пар из {n_par} законный вариант РЕКОНСТРУИРОВАН аналитиком '
          f'(поле `zamena_ot: analitik`; число снято кодом из файла, не переписано из захода)')
    print(f'   и вердиктом владельца НЕ подтверждён. Если реконструкция неточна, «не разделено»')
    print(f'   на такой паре может быть виной пары, а не модели — поэтому распределение по')
    print(f'   `zamena_ot` напечатано отдельно.')
    print(f'3. Порог выведен на {p_kol} предложениях ДВУХ выпусков, а не на большом корпусе.')
    print(f'   Это калибровка на том же материале, которым мы располагаем, а не независимая')
    print(f'   проверка: новый выпуск может дать другой максимум и сдвинуть порог.')
    print(f'4. Проверялась ПРИЕМЛЕМОСТЬ (грамматическая правильность по RuCoLA), а не')
    print(f'   ЗАКОННОСТЬ ИДИОМЫ в корпусе математического русского. Это разные вещи:')
    print(f'   «граница ушла» грамматически безупречна. Совпадение этих двух шкал —')
    print(f'   гипотеза, которую прогон и проверяет, а не предпосылка.')
    print(f'5. Модель одна ({imya_modeli}); согласие нескольких моделей не проверялось.')
    print(f'6. Ложноположительные на НЕматематическом русском не мерялись вовсе: весь')
    print(f'   материал — проза этой рассылки.')
    print()


def zhivoy_progon(klf, T, papka, kalibrovochnye):
    """Критерий 8: тот же скрипт по прозе принятого выпуска целиком."""
    put = Path(papka)
    if not put.is_absolute():
        put = KOREN / papka
    fajl = put / 'vypusk.razmechen.md'
    print('=' * 78)
    print(f'ЖИВОЙ ПРОГОН · {fajl.relative_to(KOREN)} · порог T = {T:.6f}')
    print('=' * 78)
    if not fajl.exists():
        print(f'✗ нет файла {fajl}')
        return 1
    m, s, kuski = proza_vypuskov([fajl], tolko_strogie=False)
    p = klf.p([k[3] for k in kuski])
    pomecheny = [(pp, k) for pp, k in zip(p, kuski) if pp > T]
    v_kalibrovke = [x for x in pomecheny if (x[1][0], x[1][3]) in kalibrovochnye]
    novye = [x for x in pomecheny if (x[1][0], x[1][3]) not in kalibrovochnye]
    n_kalibr = sum(1 for k in kuski if (k[0], k[3]) in kalibrovochnye)
    print(f'блоков {m}, строгих {s}, предложений {len(kuski)} '
          f'(из них {n_kalibr} участвовали в калибровке порога, '
          f'{len(kuski) - n_kalibr} — нет)')
    print(f'помечено подозрением при пороге {T:.6f}: {len(pomecheny)} из {len(kuski)}')
    print(f'  из них на КАЛИБРОВОЧНЫХ предложениях: {len(v_kalibrovke)} '
          f'(ноль здесь гарантирован построением порога и потому ничего не доказывает)')
    print(f'  из них на прозе ВНЕ калибровки: {len(novye)} из {len(kuski) - n_kalibr} '
          f'— вот это число несёт информацию')
    for pp, k in sorted(pomecheny, key=lambda t: -t[0]):
        print(f'    {pp:.4f}  {k[1]} · {k[2]} · {k[3][:80]}')
    if not pomecheny:
        print('    (ни одного — выпуск принят владельцем, это осмысленный результат)')
    print()
    maks = max(zip(p, kuski), key=lambda t: t[0])
    print(f'максимум p_neprijem по выпуску: {maks[0]:.4f} · {maks[1][1]} · {maks[1][3][:80]}')
    print()
    return 0


# ─────────────────────────────────────────────────────────── главное

def main():
    vypusk = None
    if '--vypusk' in sys.argv:
        vypusk = sys.argv[sys.argv.index('--vypusk') + 1]

    print('ПРОБА RuCoLA · берёт ли классификатор приемлемости незаконную идиому')
    print(f'python {sys.version.split()[0]} · torch {torch.__version__}')
    print()

    pary = shag1_pary()

    print('=' * 78)
    print('ШАГ 2 · МОДЕЛИ (сверху вниз; переход к следующей при разделено < '
          f'{PORQG_OSTANOVKI})')
    print('=' * 78)

    vybrannaya = None
    itogi = []
    for imya, chem in MODELI:
        print(f'── {imya}')
        print(f'   {chem}')
        try:
            klf = Klassifikator(imya)
        except Exception as e:
            print(f'   ✗ не загрузилась: {type(e).__name__}: {e}')
            itogi.append((imya, None, f'не загрузилась: {type(e).__name__}'))
            print()
            continue
        print(f'   id2label: {klf.id2label}')
        print(f'   «неприемлемо» = класс {klf.idx_neprijem} · основание: {klf.osnovanie}')
        pl, pc, znak_ok = klf.proverka_znaka()
        print(f'   проверка знака замером: ломаное «{KONTROL_LOMANOE}» p={pl:.4f} · '
              f'целое «{KONTROL_CELOE}» p={pc:.4f} → '
              f'{"знак верный" if znak_ok else "🔴 ЗНАК ПОДОЗРИТЕЛЕН"}')
        print()
        stroki, x, n = shag3_razdelenie(klf, pary)
        itogi.append((imya, x, f'разделено {x} из {n}'))
        if x >= PORQG_OSTANOVKI:
            print(f'✓ {x} >= {PORQG_OSTANOVKI} — останавливаюсь на этой модели, иду к шагу 4')
            print()
            vybrannaya = (klf, stroki, x, n)
            break
        print(f'✗ {x} < {PORQG_OSTANOVKI} — «не разделяет», перехожу к следующей модели')
        print()
        del klf

    print('=' * 78)
    print('ИТОГ ПО МОДЕЛЯМ')
    print('=' * 78)
    for imya, x, kak in itogi:
        print(f'  {imya:<48} {kak}')
    print()

    if vybrannaya is None:
        print('🔴 ВЕРДИКТ: ни одна из трёх моделей не разделяет пары на уровне '
              f'{PORQG_OSTANOVKI} из {len(pary)}. Инструмент не берётся.')
        print('Порог всё равно выводится замером — на ЛУЧШЕЙ из прогнанных моделей: '
              'без него неизвестно, дело в пороге или в модели.')
        print()
        luchshaya = max((t for t in itogi if t[1] is not None), key=lambda t: t[1], default=None)
        if luchshaya is None:
            print('✗ ни одна модель не загрузилась — порог выводить не на чем')
            return 1
        print(f'лучшая по разделению: {luchshaya[0]} ({luchshaya[2]})')
        print()
        klf = Klassifikator(luchshaya[0])
        stroki, x, n = shag3_razdelenie(klf, pary)
        vybrannaya = (klf, stroki, x, n)

    klf, stroki, x, n = vybrannaya
    T, p_kol, kalibrovochnye = shag4_porog(klf, stroki, n)
    shag5_ohvat(pary, p_kol, klf.imya)

    if vypusk:
        zhivoy_progon(klf, T, vypusk, kalibrovochnye)

    print('=' * 78)
    print('СВОДКА')
    print('=' * 78)
    print(f'модель: {klf.imya}')
    print(f'разделено {x} из {n}')
    print(f'порог {T:.6f} выведен замером: ложных срабатываний 0 из {p_kol}')
    print(f'вердикт: {"инструмент найден" if x >= PORQG_OSTANOVKI else "не берётся"}')
    return 0


if __name__ == '__main__':
    sys.exit(main())

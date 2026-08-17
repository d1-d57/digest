#!/usr/bin/env python3
"""Сборка таблицы сочетаемости «объект + предикат» из корпусов, РАЗМЕЧЕННЫХ ПО СТАТУСУ ИСТОЧНИКА.

    python3 sobrat_korpus.py --sloi kniga,chelovek,nejroset      # локальные источники
    python3 sobrat_korpus.py --wiki 6000                          # добрать статей Википедии
    python3 sobrat_korpus.py --svesti                             # собрать таблицу из накопленного

🔴 ЗАЧЕМ РАЗМЕТКА ПО СТАТУСУ, И ПОЧЕМУ БЕЗ НЕЁ ТАБЛИЦА ВРЁТ. Первая версия корпуса взяла 613
файлов из `materials` как «авторскую математическую прозу». Их написал Claude скиллом
`popsci-research`, человек их не вычитывал, — и таблица начала подтверждать как принятые ровно те
обороты, ради поимки которых строилась. Поймано владельцем 2026-08-16. Проверка на живом примере:
пара «задача + отдать» («задача ничего не отдала наружу», забракована владельцем) встречается
ТОЛЬКО в этом слое и ни разу — в книгах и вычитанных текстах.

СЛОИ И ЧТО ОНИ ДОКАЗЫВАЮТ:
  kniga     — русские математические книги (PDF). Автор написал и издал → доказывает принятость.
  chelovek  — посты канала КТ · деки слайдов · принятые выпуски · листки spetsmat · сайт фестиваля.
              Человек вычитал или выложил → доказывает принятость.
  wiki      — статьи русской Википедии по математике. Писали люди, правило сообщества → доказывает,
              но слабее книги: в Википедии встречается и канцелярит.
  nejroset  — `materials` (курсы, popsci-research). 🔴 НЕ ДОКАЗЫВАЕТ НИЧЕГО. Пара, живущая только
              здесь, — усиленное ПОДОЗРЕНИЕ.

🔴 ПРАВИЛО ЧТЕНИЯ НЕСИММЕТРИЧНО. Наличие пары в kniga/chelovek/wiki доказывает, что оборот принят.
ОТСУТСТВИЕ не доказывает ничего: «граница сдвинулась» законна по прямому вердикту владельца, а в
корпусе на 21 МБ её ноль.

РЕЕСТР. `reestr_korpusa.tsv` помнит, что уже прочитано (путь + размер). Повторный запуск не
перечитывает старое — дописывает новое. Это ответ на требование владельца: при пополнении корпуса
не гонять заново то, что уже сосчитано.

ЗАМЕР 2026-08-16 (на чём построены нынешние числа): kniga 117 книг / 21 МБ / 95 192 пары ·
chelovek 108 файлов / 18 018 пар · nejroset 637 файлов / 78 598 пар. Покрытие выпуска 4 в строгих
блоках при математических объектах — 46 % (169 пар из 367). Чтобы дойти до 80 %, корпус нужен
примерно на порядок больше; отсюда `--wiki`.

⚠ ИЗ ПЕСОЧНИЦЫ COWORK `--wiki` НЕ РАБОТАЕТ: одиночные запросы к API проходят, параллельные молча
падают на прокси, и 2000 статей качаются часами. Запускать на машине владельца.

Требует: spaCy + ru_core_news_sm, pdftotext (для книг).

🔴 ПОЛОСА А · ЯДРО — файл уедет в скилл финальной правки, который заменит `russian-editor`.
   Что мешает переносу: переносится как есть: ноль привязок к дайджесту.
   Граница скилла и вопросы владельцу — `zhurnal/2026-08-15_vypusk-04/KARTA-PERENOSA-v-skill.md`.
"""
import argparse
import collections
import csv
import gzip
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

KOREN = Path(__file__).resolve().parent
RABOCHAYA = KOREN / '.korpus'          # промежуточное состояние, в git не идёт
TABLICA = KOREN / 'tablica_sochetaemosti.json.gz'
REESTR = KOREN / 'reestr_korpusa.tsv'
UA = {'User-Agent': 'matemdigest-korpus/1.0 (research)'}
API = 'https://ru.wikipedia.org/w/api.php'

# Категории верхнего уровня для обхода. Список открытый — дополнять можно.
KATEGORII = ['Категория:Математика', 'Категория:Теоремы', 'Категория:Математический анализ',
             'Категория:Алгебра', 'Категория:Геометрия', 'Категория:Теория чисел',
             'Категория:Топология', 'Категория:Комбинаторика', 'Категория:Теория вероятностей',
             'Категория:Дискретная математика', 'Категория:Математическая логика',
             'Категория:Теория групп', 'Категория:Дифференциальные уравнения',
             'Категория:Функциональный анализ', 'Категория:Математические объекты']

INFINITIV = re.compile(r'(ть|ться|ти|тись|чь|чься)$')
STOP_OBJEKT = {'формула', 'год', 'раз', 'случай', 'пример', 'ссылка', 'страница', 'слово', 'текст',
               '·', '—', '-', 'мысль', 'зачем', 'блок', 'объём', 'link', 'areas'}
OKNO = 4


def chistka(t, tex=False):
    if tex:
        t = re.sub(r'(?s)\\begin\{(equation|align|gather|multline|tikzpicture|verbatim|lstlisting)\*?\}.*?\\end\{\1\*?\}', ' ', t)
        t = re.sub(r'\\[a-zA-Z]+\*?(\[[^\]]*\])?', ' ', t)
    t = re.sub(r'```.*?```', ' ', t, flags=re.S)
    t = re.sub(r'<[^>]+>', ' ', t)
    t = re.sub(r'\$\$.*?\$\$', ' формула ', t, flags=re.S)
    t = re.sub(r'\$[^$]*\$', ' формула ', t)
    t = re.sub(r'https?://\S+', ' ', t)
    t = re.sub(r'%.*', '', t)
    t = re.sub(r'[#*`>|\[\]{}\\&~^_]', ' ', t)
    t = re.sub(r'\b[A-Za-z]{1,4}\b', ' ', t)
    return re.sub(r'\s+', ' ', t)


def zapros(p, popytok=6):
    """🔴 Анонимный API троттлит: пачка ~10 запросов проходит быстро, затем 429 с Retry-After,
    который растёт от 5 до 52+ с при повторных нарушениях. Уважаем заголовок, не долбим вслепую."""
    u = API + '?' + urllib.parse.urlencode({**p, 'format': 'json'})
    for popytka in range(popytok):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            zhdat = int(e.headers.get('Retry-After', 5)) if e.code == 429 else 2 ** popytka
            time.sleep(zhdat)
        except Exception:
            time.sleep(2 ** popytka)
    return {}


def wiki_spisok(predel):
    """Обход категорий вширь. Возвращает заголовки статей."""
    stati, ochered, videno = set(), list(KATEGORII), set()
    while ochered and len(stati) < predel:
        kat = ochered.pop(0)
        if kat in videno:
            continue
        videno.add(kat)
        cont = None
        while True:
            p = {'action': 'query', 'list': 'categorymembers', 'cmtitle': kat,
                 'cmlimit': '500', 'cmtype': 'page|subcat'}
            if cont:
                p['cmcontinue'] = cont
            d = zapros(p)
            for m in d.get('query', {}).get('categorymembers', []):
                if m['ns'] == 0:
                    stati.add(m['title'])
                elif m['ns'] == 14 and len(ochered) < 600:
                    ochered.append(m['title'])
            cont = d.get('continue', {}).get('cmcontinue')
            if not cont:
                break
        print(f'  {kat}: всего статей {len(stati)}, категорий в очереди {len(ochered)}', flush=True)
    return sorted(stati)


def wiki_teksty(zagolovki, gotovo, f_checkpoint=None):
    """Тексты статей — ПО ОДНОМУ заголовку за запрос.
    🔴 Пачками по 20 (`exlimit=20`) НЕ РАБОТАЕТ: `prop=extracts&explaintext` без `exintro` отдаёт
    полный текст максимум для ОДНОЙ страницы в ответе, остальные приходят с пустым `extract` —
    проверено живым запросом (5 заголовков → 1 текст), и пробный `--wiki 300` это подтвердил
    (484 заголовка → 4 текста). Заодно и параллелизм убран: он усиливал троттлинг (см. ПЛАН захода
    `kod_korpus-wiki.md`), последовательные запросы с уважением Retry-After держат ровнее.
    Чекпойнт на диск каждые 25 статей — прогон многочасовой, обрыв не должен терять всё накопленное."""
    nado = [z for z in zagolovki if z not in gotovo]
    for n, z in enumerate(nado, 1):
        d = zapros({'action': 'query', 'prop': 'extracts', 'explaintext': '1', 'titles': z})
        for pg in d.get('query', {}).get('pages', {}).values():
            ex = pg.get('extract', '')
            if len(ex) > 800:
                gotovo[z] = ex
        if f_checkpoint and n % 25 == 0:
            json.dump(gotovo, open(f_checkpoint, 'w', encoding='utf-8'), ensure_ascii=False)
            print(f'  чекпойнт {n}/{len(nado)}: {len(gotovo)} статей, '
                  f'{sum(map(len, gotovo.values()))} символов', flush=True)
    if f_checkpoint:
        json.dump(gotovo, open(f_checkpoint, 'w', encoding='utf-8'), ensure_ascii=False)
    return gotovo


def nlp_pary(nlp, tekst):
    for kus in [tekst[i:i + 40000] for i in range(0, len(tekst), 40000)]:
        doc = nlp(kus)
        toks = [(t.lemma_.lower(), t.pos_) for t in doc if not t.is_space]
        for i, (l, p) in enumerate(toks):
            if p != 'VERB' or not INFINITIV.search(l):
                continue
            for j in range(max(0, i - OKNO), min(len(toks), i + OKNO + 1)):
                if j != i and toks[j][1] == 'NOUN' and toks[j][0] not in STOP_OBJEKT:
                    yield (toks[j][0], l)


POTOLOK_TABLICY = 25 * 1024 * 1024   # 25 МБ — решение владельца: место дешёвое, покрытие дорогое


def razmer_szhaty(t):
    return len(gzip.compress(json.dumps(t, ensure_ascii=False).encode('utf-8')))


def svesti_wiki():
    """Разбирает накопленные тексты Википедии в пары, кладёт четвёртым слоем `wiki` в таблицу —
    `kniga`/`chelovek`/`nejroset` НЕ трогает. Дописывает реестр, режет частоту-1 при переполнении
    потолка 25 МБ."""
    f = RABOCHAYA / 'wiki_teksty.json'
    if not f.exists():
        print(f'✗ нет {f} — сначала --wiki N')
        return 1
    teksty = json.load(open(f, encoding='utf-8'))
    print(f'сведение: {len(teksty)} статей в {f}')

    uzhe_v_reestre = set()
    if REESTR.exists():
        with open(REESTR, encoding='utf-8') as rf:
            rdr = csv.reader(rf, delimiter='\t')
            next(rdr, None)
            for row in rdr:
                if len(row) >= 3 and row[0] == 'wiki':
                    uzhe_v_reestre.add(row[2])

    import spacy
    nlp = spacy.load('ru_core_news_sm', disable=['ner', 'parser'])

    pary = collections.Counter()
    novye_stroki = []
    for n, (zagolovok, tekst) in enumerate(teksty.items(), 1):
        for o, g in nlp_pary(nlp, chistka(tekst)):
            pary[(o, g)] += 1
        if zagolovok not in uzhe_v_reestre:
            novye_stroki.append(('wiki', 'ru-wiki', zagolovok, str(len(tekst))))
        if n % 1000 == 0:
            print(f'  разобрано {n}/{len(teksty)} статей, пар пока {len(pary)}', flush=True)

    if novye_stroki:
        with open(REESTR, 'a', encoding='utf-8', newline='') as rf:
            w = csv.writer(rf, delimiter='\t')
            for row in novye_stroki:
                w.writerow(row)
    print(f'реестр: дописано {len(novye_stroki)} новых строк слоя wiki '
          f'({len(teksty) - len(novye_stroki)} уже были)')

    with gzip.open(TABLICA, 'rt', encoding='utf-8') as tf:
        T = json.load(tf)
    T['wiki'] = {f'{o}|{g}': v for (o, g), v in pary.items()}
    T['meta']['sloi']['wiki'] = {
        'chto': f'{len(teksty)} статей русской Википедии по математическим категориям',
        'status': 'да — писали люди, правило сообщества (слабее книги: встречается канцелярит)',
    }
    T['meta']['kak_chitat'] = ('наличие в kniga/chelovek/wiki доказывает принятость; наличие только '
                                'в nejroset — усиленное подозрение; отсутствие не доказывает ничего')

    srezano = 0
    r = razmer_szhaty(T)
    if r > POTOLOK_TABLICY:
        odnochastotnye = [k for k, v in T['wiki'].items() if v == 1]
        for i, k in enumerate(odnochastotnye, 1):
            del T['wiki'][k]
            srezano += 1
            if i % 5000 == 0:
                r = razmer_szhaty(T)
                if r <= POTOLOK_TABLICY:
                    break
        r = razmer_szhaty(T)
        print(f'⚠ потолок 25 МБ превышен — срезано {srezano} пар частоты 1 в слое wiki, '
              f'итоговый размер {r} байт ({len(T["wiki"])} пар осталось)')
    else:
        print(f'размер таблицы {r} байт ({r/1024/1024:.1f} МБ) — до потолка 25 МБ не дотянулись')

    with gzip.open(TABLICA, 'wt', encoding='utf-8') as tf:
        json.dump(T, tf, ensure_ascii=False)
    print(f'✓ таблица: слой wiki — {len(T["wiki"])} пар из {len(teksty)} статей')
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sloi', default='', help='какие локальные слои собрать: kniga,chelovek,nejroset')
    ap.add_argument('--wiki', type=int, default=0, help='сколько статей Википедии добрать')
    ap.add_argument('--svesti', action='store_true', help='свести накопленную википедию в слой wiki таблицы')
    ap.add_argument('--knigi', default=str(Path.home() / 'Documents' / 'Книги'))
    ap.add_argument('--github', default=str(Path.home() / 'Documents' / 'GitHub'))
    a = ap.parse_args()
    RABOCHAYA.mkdir(exist_ok=True)

    if a.wiki:
        print(f'Википедия: обход категорий до {a.wiki} статей')
        sp = wiki_spisok(a.wiki)
        json.dump(sp, open(RABOCHAYA / 'wiki_spisok.json', 'w', encoding='utf-8'), ensure_ascii=False)
        f = RABOCHAYA / 'wiki_teksty.json'
        gotovo = json.load(open(f, encoding='utf-8')) if f.exists() else {}
        gotovo = wiki_teksty(sp, gotovo, f_checkpoint=f)
        json.dump(gotovo, open(f, 'w', encoding='utf-8'), ensure_ascii=False)
        print(f'✓ Википедия: {len(gotovo)} статей, {sum(map(len, gotovo.values()))} символов')

    if a.svesti:
        rc = svesti_wiki()
        if rc:
            return rc

    if a.sloi:
        print('⚠ сборка ЛОКАЛЬНЫХ слоёв (kniga/chelovek/nejroset) вне этого захода — см. докстроку')
    return 0


if __name__ == '__main__':
    sys.exit(main())

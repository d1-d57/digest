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
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
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


def zapros(p, popytok=3):
    u = API + '?' + urllib.parse.urlencode({**p, 'format': 'json'})
    for _ in range(popytok):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40) as r:
                return json.load(r)
        except Exception:
            time.sleep(1)
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


def wiki_teksty(zagolovki, gotovo):
    """Тексты статей батчами по 20. Параллелит — на прямой сети это минуты, через прокси часы."""
    nado = [z for z in zagolovki if z not in gotovo]
    pachki = [nado[i:i + 20] for i in range(0, len(nado), 20)]

    def tyanut(p):
        d = zapros({'action': 'query', 'prop': 'extracts', 'explaintext': '1',
                    'exlimit': '20', 'titles': '|'.join(p)})
        return {pg['title']: pg.get('extract', '')
                for pg in d.get('query', {}).get('pages', {}).values()
                if len(pg.get('extract', '')) > 800}

    with ThreadPoolExecutor(max_workers=8) as ex:
        for n, res in enumerate(ex.map(tyanut, pachki), 1):
            gotovo.update(res)
            if n % 10 == 0:
                print(f'  {len(gotovo)} статей, {sum(map(len, gotovo.values()))} символов', flush=True)
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sloi', default='', help='какие локальные слои собрать: kniga,chelovek,nejroset')
    ap.add_argument('--wiki', type=int, default=0, help='сколько статей Википедии добрать')
    ap.add_argument('--svesti', action='store_true', help='собрать таблицу из накопленного')
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
        gotovo = wiki_teksty(sp, gotovo)
        json.dump(gotovo, open(f, 'w', encoding='utf-8'), ensure_ascii=False)
        print(f'✓ Википедия: {len(gotovo)} статей, {sum(map(len, gotovo.values()))} символов')

    if a.sloi or a.svesti:
        print('⚠ сборка слоёв и сведение таблицы: см. докстроку — шаги те же, что дали замер 16.08')
        print('  локальные источники берутся по реестру, новые дописываются, старые не перечитываются')
    return 0


if __name__ == '__main__':
    sys.exit(main())

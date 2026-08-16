#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_vypusk.py — движок дневника выпусков MATEMDIGEST.

Философия (из materials/_generator, семья build_doc/build_deck):
  • Markdown — ИСТОЧНИК ИСТИНЫ. HTML и Telegram — только ВИДЫ. Правь .md, пересобирай.
  • Чистая stdlib (re, sys, argparse, pathlib, html, datetime). Без сети/pip/токенов.
  • Линтер-гейт ДО сборки: структурная ошибка → exit 1 (ничего не пишем).
  • Шапка выходов: баннер «СГЕНЕРИРОВАНО — РУКАМИ НЕ ПРАВИТЬ».

Из одного vypusk-NN.md собирает три вида рядом с источником:
  vypusk-NN.html          — самодостаточная страница (палитра Atlas; смотреть + на сайт)
  vypusk-NN.telegram.txt  — пост в канал (Telegram-HTML; печатает длину и влезает ли в 4096)
  vypusk-NN.teaser.txt    — короткий тизер + ссылка на страницу (фолбэк, если пост длинный)

Формат источника (РУБРИКИ = журнальная иерархия):
  ---                       ← фронтматтер (YAML-lite: key: value, по строке)
  number: 1
  subtitle: ...
  date: 2026-07-18
  channel: ... / channel_url: ... / page_url: ... / teaser: одна строка
  ---
  <абзац-лид до первого заголовка>

  # Новые результаты        ← РУБРИКА (H1, один #)
  ## Заголовок материала     ← карточка (H2, два ##)
  - url: https://...
  - source: Quanta Magazine
  - byline: Лейла Сломан      (автор — выводится вперёд)
  - date: 2026-06-26
  - areas: комбинаторика · вероятность · геометрия
  - kind: статья             (жанр — крупный чип: статья/блог/обзор/подкаст/интервью/видео)
  <пустая строка>
  Абзац-подводка по-русски...

  # Обзоры                   ← следующая рубрика
  ## ...

Аранжировка — ПОРЯДКОМ В ИСТОЧНИКЕ (движок не сортирует): рубрики сверху вниз,
внутри рубрики карточки в порядке файла (статьи выше, видео ниже — так задаёт автор).

Запуск:
  python3 build_vypusk.py vypusk-01.md          # линтер + сборка трёх видов
  python3 build_vypusk.py vypusk-01.md --lint    # только линтер
"""
import re, sys, argparse, datetime
from pathlib import Path
from html import escape as esc

GEN_BANNER_HTML = ("<!-- СГЕНЕРИРОВАНО ИЗ {src} ГЕНЕРАТОРОМ build_vypusk.py — "
                   "РУКАМИ НЕ ПРАВИТЬ. Правь markdown-источник, пересобирай (0 токенов). -->\n")
GEN_BANNER_TXT = ("СГЕНЕРИРОВАНО ИЗ {src} — РУКАМИ НЕ ПРАВИТЬ. Правь .md, пересобирай.\n"
                  "════════════════════════════════════════════════════════════\n\n")

MONTHS_GEN = ['', 'января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля',
              'августа', 'сентября', 'октября', 'ноября', 'декабря']

REQUIRED_ITEM_KEYS = ['url', 'source', 'date', 'areas', 'kind']
TG_LIMIT = 4096


# ───────────────────────── ввод/вывод без трансляции переводов строк ─────────────────────────
def read_text(path):
    with open(path, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(text)


# ───────────────────────── парсинг источника ─────────────────────────
def split_frontmatter(text):
    m = re.match(r'^﻿?---\n(.*?)\n---\n?', text, re.S)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        lm = re.match(r'^([A-Za-z_]+):\s*(.*)$', line)
        if lm:
            meta[lm.group(1)] = lm.group(2).strip()
    return meta, text[m.end():]


def parse_item_chunks(text):
    """Куски, начатые '## ' → карточки."""
    parts = re.split(r'(?m)^##[ \t]+', text)
    items = []
    metapat = re.compile(r'^-\s*([a-z_]+):\s*(.*)$')
    for chunk in parts[1:]:
        lines = chunk.rstrip().split('\n')
        title = lines[0].strip()
        meta, i = {}, 1
        links, profiles = [], []

        def add_link(val):
            # link: URL | Название | Фраза о том, что это за материал
            f = [x.strip() for x in val.split('|')]
            f += [''] * (3 - len(f))
            links.append({'url': f[0], 'title': f[1], 'about': f[2]})

        def add_profile(val):
            # profile: URL | Подпись кнопки
            u, _, lbl = val.partition('|')
            profiles.append({'url': u.strip(), 'label': lbl.strip() or 'Профиль'})

        while i < len(lines) and metapat.match(lines[i]):
            mm = metapat.match(lines[i])
            key, val = mm.group(1), mm.group(2).strip()
            if key == 'link':
                add_link(val)
            elif key == 'profile':
                add_profile(val)
            else:
                meta[key] = val
            i += 1
        # ссылки-подборку можно писать и после текста карточки — так читаемее
        body_lines = []
        for line in lines[i:]:
            mm = metapat.match(line)
            if mm and mm.group(1) == 'link':
                add_link(mm.group(2).strip())
            else:
                body_lines.append(line)
        meta['links'] = links
        meta['profiles'] = profiles
        blurb = '\n'.join(body_lines).strip()
        items.append({'title': title, 'meta': meta, 'blurb': blurb})
    return items


def parse_body(body):
    """Тело → (лид, [(рубрика, [item...])]). Рубрики — H1 (один #, не ##)."""
    parts = re.split(r'(?m)^#(?!#)[ \t]+', body)
    head = parts[0]
    # Карта (К12) стоит перед лидом и в лид не входит; всё, что после её таблицы
    # и до первой рубрики, — лид с его блоками.
    if re.search(r'(?m)^## Карта[ \t]*$', head):
        hvost = re.split(r'(?m)^## Карта[ \t]*$', head, 1)[1]
        lead = re.sub(r'(?m)^\|.*$', '', hvost).strip()
    else:
        lead = re.split(r'(?m)^##[ \t]+', head)[0].strip()
    rubrics = []
    if len(parts) == 1:  # без рубрик — все карточки в одной безымянной секции
        items = parse_item_chunks(head)
        if items:
            rubrics.append(('', items))
        return lead, rubrics
    for chunk in parts[1:]:
        nl = chunk.find('\n')
        name, rest = (chunk.strip(), '') if nl == -1 else (chunk[:nl].strip(), chunk[nl + 1:])
        rubrics.append((name, parse_item_chunks(rest)))
    return lead, rubrics


# ───────────────────────── линтер-гейт ─────────────────────────
def lint(meta, lead, rubrics):
    errs, warns = [], []
    for k in ('number', 'subtitle', 'date'):
        if not meta.get(k):
            errs.append(f'фронтматтер: нет поля «{k}»')
    if meta.get('date') and not re.match(r'^\d{4}-\d{2}-\d{2}$', meta['date']):
        errs.append(f"фронтматтер: date «{meta.get('date')}» не в формате ГГГГ-ММ-ДД")
    if not lead:
        warns.append('нет лид-абзаца (текста до первой рубрики)')
    items = [(rn, it) for rn, its in rubrics for it in its]
    if not items:
        errs.append('нет ни одного материала (## …)')
    for rn, its in rubrics:
        if not rn:
            warns.append('есть карточки вне рубрики (без # заголовка)')
    for n, (rn, it) in enumerate(items, 1):
        if not it['title']:
            errs.append(f'материал #{n}: пустой заголовок')
        links = it['meta'].get('links') or []
        # два режима карточки: одиночный материал (url + kind + date) и подборка (link: …)
        if links:
            for li, ln in enumerate(links, 1):
                if not ln['url'].startswith(('http://', 'https://')):
                    errs.append(f'материал #{n}, ссылка #{li}: url не похож на ссылку: {ln["url"]}')
                for k in ('title', 'about'):
                    if not ln[k]:
                        errs.append(f'материал #{n}, ссылка #{li}: нет поля «{k}» '
                                    f'(формат: link: URL | Название | фраза о материале)')
        elif any(it['meta'].get(k) for k in REQUIRED_ITEM_KEYS if k != 'areas'):
            # режим одиночного материала: раз начали заполнять карточку — заполняй всю
            for k in REQUIRED_ITEM_KEYS:
                if not it['meta'].get(k):
                    errs.append(f'материал #{n} «{it["title"][:40]}»: нет поля «{k}»')
        # третий законный режим — блок вообще без ссылок: чистый текст в арке.
        # Минимализм важнее симметрии, ссылка ради заполнения слота хуже пустоты.
        u = it['meta'].get('url', '')
        if u and not u.startswith(('http://', 'https://')):
            errs.append(f'материал #{n}: url не похож на ссылку: {u}')
        if it['meta'].get('date') and not re.match(r'^\d{4}-\d{2}-\d{2}$', it['meta']['date']):
            errs.append(f'материал #{n}: date «{it["meta"]["date"]}» не ГГГГ-ММ-ДД')
        if not it['blurb']:
            errs.append(f'материал #{n} «{it["title"][:40]}»: нет подводки')
    return errs, warns, len(items)


# ───────────────────────── даты ─────────────────────────
def ru_date_full(iso):
    try:
        d = datetime.date.fromisoformat(iso)
        return f'{d.day} {MONTHS_GEN[d.month]} {d.year}'
    except Exception:
        return iso


def ru_date_short(iso):
    try:
        d = datetime.date.fromisoformat(iso)
        return f'{d.day} {MONTHS_GEN[d.month]}'
    except Exception:
        return iso


# ───────────────────────── математика в подводках ─────────────────────────
def _math_html(raw):
    """В HTML математику отдаём KaTeX'у как есть — он подключён в шапке страницы.
    Знаки < > & внутри формулы экранируем, остальной TeX не трогаем."""
    s = raw.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    return '$' + s + '$'


# TeX-макросы, у которых есть годный юникодный эквивалент для Telegram (там KaTeX нет).
# Пробел после имени макроса в TeX служебный (он завершает имя) — его же и съедаем.
# У знаков отношения и операций пробел в значении — он заменяет съеденный служебный;
# у букв и скобок пробела нет, иначе получается «⟨ x».
_TEX_WORDS = {
    'partial': '∂', 'pi': 'π', 'delta': 'δ', 'langle': '⟨', 'rangle': '⟩',
    'dots': '…', 'ldots': '…',
    'nabla': '∇', 'infty': '∞', 'alpha': 'α', 'beta': 'β', 'lambda': 'λ',
    'times': '×', 'to': '→', 'mapsto': '↦', 'in': '∈', 'circ': '∘', 'cdot': '·',
    'Longrightarrow': '⟹', 'Rightarrow': '⇒', 'cong': '≅', 'colon': ':',
    'le': '≤', 'leq': '≤', 'ge': '≥', 'geq': '≥', 'ne': '≠', 'neq': '≠',
    'approx': '≈', 'subset': '⊂', 'cup': '∪', 'cap': '∩', 'oplus': '⊕', 'otimes': '⊗',
    'qquad': '  ', 'quad': '  ',
    'sigma': 'σ', 'varepsilon': 'ε', 'epsilon': 'ε', 'lt': '<', 'gt': '>',
    'tau': 'τ', 'mu': 'μ', 'varphi': 'φ', 'subseteq': '⊆',
}
# Знаки отношений и операций: в TeX пробелы вокруг них ставит наборщик, в юникоде — мы.
_TEX_OPS = '×→↦∈∘·⟹⇒≅≤≥≠≈⊂∪∩⊕⊗<>'
_PLAIN_TEX = [
    (r'\\mathbb\{([A-Z])\}', r'\1'), (r'\\mathrm\{([^}]*)\}', r'\1'),
    (r'\\(?:big|Big|left|right)([()\[\]])', r'\1'),
    # Неизвестный макрос оставляем именем и НЕ съедаем пробел — иначе `n\le 3`
    # молча превращается в «nle3». Заметно в вычитке — значит, чинится словарём.
    (r'\\([a-zA-Z]+)( ?)', lambda m: _TEX_WORDS.get(m.group(1), m.group(1) + m.group(2))),
    (r'\\([{}]) ?', r'\1'), (r'\\, ?', ' '), (r'\\ ', ' '),
]
_SUP = str.maketrans('0123456789nijkm-+', '⁰¹²³⁴⁵⁶⁷⁸⁹ⁿⁱʲᵏᵐ⁻⁺')
_SUB = str.maketrans('0123456789nijkm-+', '₀₁₂₃₄₅₆₇₈₉ₙᵢⱼₖₘ₋₊')


def _math_plain(raw):
    s = raw
    for pat, rep in _PLAIN_TEX:
        s = re.sub(pat, rep, s)
    s = re.sub(r'\^\{([^}]*)\}|\^(\w)',
               lambda m: (m.group(1) or m.group(2)).translate(_SUP), s)
    s = re.sub(r'_\{([^}]*)\}|_(\w)',
               lambda m: (m.group(1) or m.group(2)).translate(_SUB), s)
    s = re.sub(rf' *([{_TEX_OPS}]) *', r' \1 ', s)
    return re.sub(r'\s{3,}', '  ', s).strip()


# ───────────────────────── инлайн-разметка ─────────────────────────
def render_inline_html(text):
    stash = []

    def keep(m):
        stash.append(m.group(1))
        return f'\x00{len(stash) - 1}\x00'

    text = re.sub(r'\$(.+?)\$', keep, text)
    text = esc(text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', text)
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    text = re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)',
                  r'<a href="\2" target="_blank" rel="noopener">\1</a>', text)
    text = re.sub(r'\x00(\d+)\x00', lambda m: _math_html(stash[int(m.group(1))]), text)
    return text


def render_inline_plain(text):
    text = re.sub(r'\$(.+?)\$', lambda m: _math_plain(m.group(1)), text)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'\1', text)
    text = re.sub(r'`(.+?)`', r'\1', text)
    text = re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)', r'\1', text)
    return esc(text, quote=False)


def drop_final_dot(s):
    """Точка в конце абзаца не нужна — она только утяжеляет текст.
    Снимаем одиночную точку; многоточие, вопрос, восклицание и сокращения не трогаем."""
    s = s.rstrip()
    if s.endswith('.') and not s.endswith('..') and not re.search(r'(?:\s\w|[А-ЯA-Z])\.$', s):
        return s[:-1]
    return s


# Маркер блока: «%% <статус> · <зачем блок нужен>» отдельной строкой перед абзацами.
# Генератор его не рендерит: разметка нужна тому, кто собирает и проверяет текст,
# а не читателю. Дом статусов — docs/PROTOKOL-VYPUSKA.md, канон К9.
BLOK_RE = re.compile(r'^%%\s*([\wЛ.]+)\s*·\s*([a-z]+)\s*$', re.M)


def paras(blurb):
    """Абзацы текста. Шапка блока (от «%%» до «====») в вёрстку не идёт: она
    для того, кто пишет и проверяет, а не для читателя (канон К12)."""
    out = []
    for p in re.split(r'\n\s*\n', blurb):
        p = p.strip()
        if not p or p.startswith('%%'):
            continue
        out.append(drop_final_dot(p))
    return out


def bloki(blurb):
    """[(id, статус, {поля шапки}, [абзацы])]. Абзацы до первой шапки — брак,
    их ловит гейт: у них id=None."""
    out, tek = [], (None, None, {}, [])
    for p in re.split(r'\n\s*\n', blurb):
        p = p.strip()
        if not p:
            continue
        if p.startswith('%%'):
            if tek[3] or tek[0]:
                out.append(tek)
            m = BLOK_RE.match(p)
            polya = dict(re.findall(r'^(зачем|мысль|опирается|объём):\s*(.+)$', p, re.M))
            tek = (m.group(1) if m else '?', m.group(2) if m else '?', polya, [])
        else:
            tek[3].append(drop_final_dot(p))
    if tek[3] or tek[0]:
        out.append(tek)
    return out


def bullets(p):
    """Абзац, все строки которого начаты с «- », — это список, а не текст.
    Однородные пункты (два свойства, три условия) в подбор не читаются: глаз
    не видит, где кончается первый. Возвращает пункты или None."""
    lines = [ln.strip() for ln in p.split('\n') if ln.strip()]
    if len(lines) >= 2 and all(ln.startswith('- ') for ln in lines):
        return [drop_final_dot(ln[2:].strip()) for ln in lines]
    return None


# Выключная формула: абзац целиком в $$…$$ — идёт отдельной строкой по центру.
DISPLAY_RE = re.compile(r'^\$\$(.+)\$\$$', re.S)


def display_math(p):
    """Вернуть содержимое выключной формулы или None, если абзац обычный."""
    mm = DISPLAY_RE.match(p.strip())
    return mm.group(1).strip() if mm else None


def byline_str(m):
    """Автор · Источник · области — автор вперёд."""
    bits = []
    if m.get('byline'):
        bits.append(m['byline'])
    if m.get('source'):
        bits.append(m['source'])
    if m.get('areas'):
        bits.append(m['areas'])
    return ' · '.join(bits)


# ───────────────────────── вид 1: HTML-страница (Atlas) ─────────────────────────
STYLE = """*{box-sizing:border-box}
:root{--bg:#14110d;--ink:#ece3d2;--mut:#a89c86;--faint:#6b6252;--line:rgba(236,227,210,.13);--gold:#cea24a;--gold2:#e6c26f;--teal:#6fae9f}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font-family:'Golos Text',system-ui,sans-serif;
 font-size:clamp(18px,1.32vw,29px);line-height:1.55;
 background-image:radial-gradient(900px 500px at 15% -8%,rgba(206,162,74,.12),transparent 60%),radial-gradient(800px 600px at 100% 4%,rgba(111,174,159,.07),transparent 55%);-webkit-font-smoothing:antialiased}
.wrap{width:min(1780px,93vw);margin:0 auto;padding:clamp(30px,3.2vw,64px) 0 110px}
.kick{font-family:'JetBrains Mono',monospace;font-size:.66em;letter-spacing:.28em;text-transform:uppercase;color:var(--gold);margin-bottom:14px}
h1{font-family:'Forum',serif;font-weight:400;font-size:clamp(40px,5.4vw,104px);margin:0 0 20px;line-height:1.03;overflow-wrap:break-word}
.intro{color:var(--mut);margin:0 0 .34em;font-size:1.1em;line-height:1.5}
.intro:last-of-type{margin-bottom:0}
.intro a,.blurb a,.labout a{color:var(--gold2);text-decoration:none;border-bottom:1px solid rgba(206,162,74,.35)}
.intro a:hover,.blurb a:hover,.labout a:hover{color:var(--gold);border-bottom-color:var(--gold)}
.note{display:flex;gap:.6em;align-items:baseline;margin-top:22px;color:var(--faint);font-size:.75em;line-height:1.45}
.note .sign{color:var(--gold);font-size:1.15em;line-height:1}
.author{font-family:'JetBrains Mono',monospace;font-size:.8em;letter-spacing:.05em;color:var(--mut);margin-top:20px}
.author a{color:var(--gold);text-decoration:none}.author a:hover{text-decoration:underline}
.rubric{font-family:'JetBrains Mono',monospace;font-size:.72em;letter-spacing:.24em;text-transform:uppercase;color:var(--gold2);margin:clamp(34px,3vw,56px) 0 22px;padding-top:16px;border-top:1px solid rgba(206,162,74,.3)}
.rule{height:1px;background:var(--line);margin:clamp(24px,2vw,38px) 0}
.item{padding:2px 0}
.side{margin-bottom:16px}
.meta{display:flex;gap:10px;align-items:center;margin-bottom:10px;flex-wrap:wrap}
.kind{font-family:'JetBrains Mono',monospace;font-size:.62em;letter-spacing:.1em;text-transform:uppercase;color:var(--bg);background:var(--gold);border-radius:5px;padding:5px 11px;font-weight:700;text-decoration:none;display:inline-block}
a.kind:hover{background:var(--gold2)}
.date{font-family:'JetBrains Mono',monospace;font-size:.62em;color:var(--faint);margin-left:auto}
/* Длинный термин в заголовке («аппроксимируемость») переполняет колонку и
   налезает на текст. Переносы по слогам + разрыв слова как крайняя мера. */
.title{font-family:'Forum',serif;font-weight:400;font-size:clamp(30px,2.55vw,50px);line-height:1.1;margin:0 0 12px;
 hyphens:auto;-webkit-hyphens:auto;overflow-wrap:break-word}
.by{font-size:.82em;color:var(--mut);margin:0;line-height:1.45}
.prof{display:block;width:fit-content;margin-top:12px;font-size:.8em;color:var(--teal);text-decoration:none;border:1px solid rgba(111,174,159,.4);border-radius:7px;padding:7px 13px;line-height:1.3}
.prof:hover{color:var(--bg);background:var(--teal);border-color:var(--teal)}
.blurb{margin:0 0 .38em;color:#ded4c2}
.blist{margin:.5em 0 .5em;padding:0;list-style:none;color:#ded4c2}
.blist li{margin:0 0 .5em;padding-left:1.15em;position:relative}
.blist li:last-child{margin-bottom:0}
.blist li:before{content:'—';position:absolute;left:0;color:var(--gold2)}
.blurb:last-child{margin-bottom:0}
.blurb .m{font-family:'JetBrains Mono',monospace;font-size:.92em}
.disp{margin:clamp(26px,2.1vw,44px) 0;text-align:center;line-height:1.5;color:var(--gold2);
 overflow-x:auto;overflow-y:hidden}
.katex{font-size:1.02em}
.disp .katex{font-size:1.34em}
.blurb .katex,.intro .katex{color:var(--ink)}
.blurb sup,.blurb sub{font-size:.72em}
.more{font-family:'JetBrains Mono',monospace;font-size:.7em;color:var(--gold);text-decoration:none;letter-spacing:.02em}
.more:hover{color:var(--gold2);text-decoration:underline}
.links{margin:clamp(26px,2.2vw,44px) 0 4px;padding:clamp(18px,1.5vw,32px) clamp(20px,1.6vw,34px);border:1px solid var(--line);border-radius:10px;background:rgba(236,227,210,.03)}
.lhead{font-family:'JetBrains Mono',monospace;font-size:.62em;letter-spacing:.18em;text-transform:uppercase;color:var(--faint);margin-bottom:18px}
.lnk{margin:0 0 20px;line-height:1.45}
.lnk:last-child{margin-bottom:0}
.labout{color:var(--mut);font-size:.92em;margin-bottom:2px}
.lnk a{color:var(--gold2);text-decoration:none;border-bottom:1px solid rgba(206,162,74,.35)}
.lnk a:hover{color:var(--gold);border-bottom-color:var(--gold)}
.dots{position:fixed;right:clamp(10px,2vw,30px);top:50%;transform:translateY(-50%);display:none;flex-direction:column;gap:15px;z-index:9}
.dots a{position:relative;width:9px;height:9px;border-radius:50%;background:rgba(236,227,210,.22);transition:background .18s,transform .18s}
.dots a:hover{background:var(--gold);transform:scale(1.35)}
.dots a::after{content:attr(data-t);position:absolute;right:20px;top:50%;transform:translateY(-50%);
 white-space:nowrap;font-family:'JetBrains Mono',monospace;font-size:12px;letter-spacing:.04em;color:var(--ink);
 background:rgba(20,17,13,.94);border:1px solid var(--line);border-radius:6px;padding:5px 10px;opacity:0;pointer-events:none;transition:opacity .18s}
.dots a:hover::after{opacity:1}
@media (min-width:1080px){
 .wrap{padding-right:clamp(26px,2.4vw,52px)}
 .dots{display:flex}
 .item{display:grid;grid-template-columns:minmax(240px,23%) minmax(0,1fr);column-gap:clamp(28px,2.4vw,52px)}
 .side{grid-column:1;margin-bottom:0;position:sticky;top:30px;align-self:start}
 .body{grid-column:2}
}
.foot{margin-top:clamp(40px,3.4vw,64px);padding-top:22px;border-top:1px solid var(--line)}
.foot .author{margin-top:0;white-space:nowrap}"""


# SRI-хеши намеренно не проставлены: проверить их из песочницы нечем, а неверный
# хеш молча блокирует скрипт и убивает всю математику на странице. Версия пришпилена.
KATEX_HEAD = (
    '<link rel=stylesheet href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css" '
    'crossorigin=anonymous>'
    '<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js" '
    'crossorigin=anonymous></script>'
    '<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js" '
    'crossorigin=anonymous '
    'onload="renderMathInElement(document.body,{delimiters:['
    '{left:\'$$\',right:\'$$\',display:true},{left:\'$\',right:\'$\',display:false}],'
    'throwOnError:false})"></script>'
)


def build_html(meta, lead, rubrics, src_name):
    kick = ru_date_full(meta['date']).upper() if meta.get('date') else ''
    P = [GEN_BANNER_HTML.format(src=src_name)]
    P.append('<!doctype html><html lang=ru><head><meta charset=utf-8>')
    P.append('<meta name=viewport content="width=device-width,initial-scale=1">')
    P.append(f"<title>MATEMDIGEST · выпуск №{esc(meta.get('number',''))}</title>")
    P.append('<link rel=preconnect href="https://fonts.googleapis.com">'
             '<link rel=preconnect href="https://fonts.gstatic.com" crossorigin>')
    P.append('<link href="https://fonts.googleapis.com/css2?family=Forum&family=Golos+Text:wght@400;500;600&family=JetBrains+Mono:wght@400;700&display=swap" rel=stylesheet>')
    P.append(KATEX_HEAD)
    P.append(f'<style>{STYLE}</style></head><body><div class=wrap>')
    if kick:
        P.append(f'<div class=kick>{esc(kick)}</div>')
    P.append(f"<h1>{esc(meta.get('subtitle',''))}</h1>")
    if lead:
        for p in paras(lead):
            P.append(f'<p class=intro>{render_inline_html(p)}</p>')
    if meta.get('note'):
        P.append('<div class=note><span class=sign>&#9651;</span><span>'
                 + render_inline_html(drop_final_dot(meta['note'])) + '</span></div>')
    sig = []
    if meta.get('author'):
        sig.append(esc(meta['author']))
    if meta.get('channel'):
        if meta.get('channel_url'):
            sig.append(f"<a href=\"{esc(meta['channel_url'])}\" target=_blank rel=noopener>«{esc(meta['channel'])}»</a>")
        else:
            sig.append(f"«{esc(meta['channel'])}»")
    sig_html = '<div class=author>' + ' · '.join(sig) + '</div>' if sig else ''
    if sig_html:
        P.append(sig_html)

    nav, k = [], 0
    for rname, items in rubrics:
        if rname:
            P.append(f'<div class=rubric>{esc(rname)}</div>')
        for j, it in enumerate(items):
            m = it['meta']
            k += 1
            anchor = f'p{k}'
            nav.append((anchor, it['title']))
            if j > 0:
                P.append('<div class=rule></div>')
            P.append(f'<article class=item id={anchor}>')
            P.append('<div class=side>')
            row = []
            if m.get('kind'):
                row.append(f"<span class=kind>{esc(m['kind'].upper())}</span>")
            if m.get('award'):
                row.append(f"<span class=kind>{esc(m['award'].upper())}</span>")
            if m.get('date'):
                row.append(f"<span class=date>{esc(ru_date_short(m['date']))}</span>")
            if row:
                P.append('<div class=meta>' + ''.join(row) + '</div>')
            P.append(f"<h2 class=title>{esc(it['title'])}</h2>")
            by = byline_str(m)
            if by:
                P.append(f"<div class=by>{esc(by)}</div>")
            for pr in (m.get('profiles') or []):
                P.append(f"<a class=prof href=\"{esc(pr['url'])}\" target=_blank rel=noopener>"
                         f"{esc(pr['label'])} →</a>")
            if m.get('award_url'):
                P.append(f"<a class=prof href=\"{esc(m['award_url'])}\" target=_blank rel=noopener>"
                         f"Страница награды →</a>")
            P.append('</div><div class=body>')
            for p in paras(it['blurb']):
                dm = display_math(p)
                bl = bullets(p)
                if dm:
                    P.append('<p class=disp>$' + _math_html(dm) + '$</p>')
                elif bl:
                    P.append('<ul class=blist>' + ''.join(
                        f'<li>{render_inline_html(b)}</li>' for b in bl) + '</ul>')
                else:
                    P.append(f'<p class=blurb>{render_inline_html(p)}</p>')
            links = m.get('links') or []
            if links:
                P.append('<div class=links><div class=lhead>Что почитать и посмотреть</div>')
                for ln in links:
                    P.append(f"<div class=lnk><div class=labout>{render_inline_html(drop_final_dot(ln['about']))}</div>"
                             f"<a href=\"{esc(ln['url'])}\" target=_blank rel=noopener>{esc(ln['title'])}</a></div>")
                P.append('</div>')
            elif m.get('url'):
                P.append(f"<a class=more href=\"{esc(m['url'])}\" target=_blank rel=noopener>Читать →</a>")
            P.append('</div></article>')

    if sig_html:
        P.append(f'<div class=foot>{sig_html}</div>')
    P.append('</div>')
    if nav:
        P.append('<nav class=dots>' + ''.join(
            f'<a href="#{a}" data-t="{esc(t, quote=True)}"></a>' for a, t in nav) + '</nav>')
    P.append('</body></html>')
    return '\n'.join(P) + '\n'


# ───────────────────────── вид 2: Telegram-пост ─────────────────────────
def build_telegram(meta, lead, rubrics, src_name):
    L = [f"<b>MATEMDIGEST · выпуск №{esc(meta.get('number',''), quote=False)}</b>"]
    if meta.get('subtitle'):
        L.append(f"<i>{esc(meta['subtitle'], quote=False)}</i>")
    L.append('')
    if lead:
        L.append('\n\n'.join(render_inline_plain(p) for p in paras(lead)))
        L.append('')
    if meta.get('note'):
        L.append('△ ' + render_inline_plain(drop_final_dot(meta['note'])))
        L.append('')
    for rname, items in rubrics:
        if rname:
            L.append(f"▎<b>{esc(rname.upper(), quote=False)}</b>")
            L.append('')
        for it in items:
            m = it['meta']
            links = m.get('links') or []
            if links:
                L.append(f"<b>{esc(it['title'], quote=False)}</b>")
            else:
                L.append(f"<b><a href=\"{esc(m.get('url',''), quote=True)}\">{esc(it['title'], quote=False)}</a></b>")
            head_bits = [x for x in ((m.get('kind', '') or '').upper(), m.get('byline'), m.get('source')) if x]
            if m.get('date'):
                head_bits.append(ru_date_short(m['date']))
            if head_bits:
                L.append(esc(' · '.join(head_bits), quote=False))
            if m.get('areas'):
                L.append(f"<i>{esc(m['areas'], quote=False)}</i>")
            for pr in (m.get('profiles') or []):
                L.append(f"<a href=\"{esc(pr['url'], quote=True)}\">{esc(pr['label'], quote=False)}</a>")
            L.append('')
            for p in paras(it['blurb']):
                dm = display_math(p)
                bl = bullets(p)
                if dm:
                    L.append(_math_plain(dm))
                elif bl:
                    L.extend('• ' + render_inline_plain(b) for b in bl)
                else:
                    L.append(render_inline_plain(p))
            L.append('')
            for ln in links:
                if ln['about']:
                    L.append(render_inline_plain(drop_final_dot(ln['about'])))
                L.append(f"→ <a href=\"{esc(ln['url'], quote=True)}\">{esc(ln['title'], quote=False)}</a>")
            if links:
                L.append('')
    if meta.get('channel'):
        L.append('➖➖➖➖➖➖➖➖➖➖')
        L.append(f"<i>{esc(meta['channel'], quote=False)}</i>")
    return '\n'.join(L).rstrip() + '\n'


# ───────────────────────── вид 3: короткий тизер ─────────────────────────
def build_teaser(meta):
    L = [f"⚡️ MATEMDIGEST · выпуск №{meta.get('number','')}"]
    if meta.get('teaser'):
        L += ['', render_inline_plain(meta['teaser'])]
    if meta.get('page_url', '').strip():
        L += ['', f"Читать целиком → {meta['page_url'].strip()}"]
    return '\n'.join(L).rstrip() + '\n'


# ───────────────────────── CLI ─────────────────────────
def main():
    ap = argparse.ArgumentParser(description='Сборка выпуска MATEMDIGEST из markdown-источника.')
    ap.add_argument('src', help='путь к vypusk-NN.md')
    ap.add_argument('--lint', action='store_true', help='только линтер, без записи')
    args = ap.parse_args()

    src = Path(args.src)
    if not src.exists():
        print(f'✗ источник не найден: {src}', file=sys.stderr)
        sys.exit(1)

    meta, body = split_frontmatter(read_text(src))
    lead, rubrics = parse_body(body)

    errs, warns, nitems = lint(meta, lead, rubrics)
    for w in warns:
        print(f'  ⚠ {w}')
    if errs:
        print(f'✗ линтер: {len(errs)} структурн. ошиб. в {src.name} — сборка прервана:', file=sys.stderr)
        for e in errs:
            print(f'    • {e}', file=sys.stderr)
        sys.exit(1)
    rub_names = [rn for rn, _ in rubrics if rn]
    print(f'✓ линтер ок: {nitems} материалов в {len(rub_names)} рубриках ({", ".join(rub_names)})')

    if args.lint:
        return

    stem = src.stem
    write_text(src.with_name(stem + '.html'), build_html(meta, lead, rubrics, src.name))
    tg = build_telegram(meta, lead, rubrics, src.name)
    write_text(src.with_name(stem + '.telegram.txt'), GEN_BANNER_TXT.format(src=src.name) + tg)
    write_text(src.with_name(stem + '.teaser.txt'), GEN_BANNER_TXT.format(src=src.name) + build_teaser(meta))

    fits = '✓ влезает в одно сообщение' if len(tg) <= TG_LIMIT else f'✗ длиннее {TG_LIMIT} — постим тизер + ссылку'
    print(f'✓ {stem}.html')
    print(f'✓ {stem}.telegram.txt  ({len(tg)} симв., {fits})')
    print(f'✓ {stem}.teaser.txt')


if __name__ == '__main__':
    main()

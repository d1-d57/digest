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
        while i < len(lines) and metapat.match(lines[i]):
            mm = metapat.match(lines[i])
            meta[mm.group(1)] = mm.group(2).strip()
            i += 1
        blurb = '\n'.join(lines[i:]).strip()
        items.append({'title': title, 'meta': meta, 'blurb': blurb})
    return items


def parse_body(body):
    """Тело → (лид, [(рубрика, [item...])]). Рубрики — H1 (один #, не ##)."""
    parts = re.split(r'(?m)^#(?!#)[ \t]+', body)
    head = parts[0]
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
        for k in REQUIRED_ITEM_KEYS:
            if not it['meta'].get(k):
                errs.append(f'материал #{n} «{it["title"][:40]}»: нет поля «{k}»')
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
    s = esc(raw)
    s = re.sub(r'\^\{([^}]*)\}', r'<sup>\1</sup>', s)
    s = re.sub(r'\^(\w)', r'<sup>\1</sup>', s)
    s = re.sub(r'_\{([^}]*)\}', r'<sub>\1</sub>', s)
    s = re.sub(r'_(\w)', r'<sub>\1</sub>', s)
    return '<span class="m">' + s + '</span>'


def _math_plain(raw):
    s = re.sub(r'\^\{([^}]*)\}', r'^(\1)', raw)
    s = re.sub(r'_\{([^}]*)\}', r'_(\1)', s)
    return s


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


def paras(blurb):
    return [p.strip() for p in re.split(r'\n\s*\n', blurb) if p.strip()]


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
body{margin:0;background:var(--bg);color:var(--ink);font-family:'Golos Text',system-ui,sans-serif;font-size:17px;line-height:1.62;
 background-image:radial-gradient(900px 500px at 15% -8%,rgba(206,162,74,.12),transparent 60%),radial-gradient(800px 600px at 100% 4%,rgba(111,174,159,.07),transparent 55%);-webkit-font-smoothing:antialiased}
.wrap{max-width:680px;margin:0 auto;padding:64px 28px 100px}
.kick{font-family:'JetBrains Mono',monospace;font-size:12px;letter-spacing:.28em;text-transform:uppercase;color:var(--gold);margin-bottom:18px}
h1{font-family:'Forum',serif;font-weight:400;font-size:40px;margin:0 0 12px;line-height:1.12}
.intro{color:var(--mut);margin:0;font-size:16px}
.rubric{font-family:'JetBrains Mono',monospace;font-size:12.5px;letter-spacing:.24em;text-transform:uppercase;color:var(--gold2);margin:52px 0 22px;padding-top:20px;border-top:1px solid rgba(206,162,74,.3)}
.rule{height:1px;background:var(--line);margin:30px 0}
.item{padding:2px 0}
.meta{display:flex;gap:10px;align-items:center;margin-bottom:11px}
.kind{font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:.11em;text-transform:uppercase;color:var(--bg);background:var(--gold);border-radius:4px;padding:3px 9px;font-weight:700}
.date{font-family:'JetBrains Mono',monospace;font-size:10.5px;color:var(--faint);margin-left:auto}
.title{font-family:'Forum',serif;font-weight:400;font-size:25px;line-height:1.16;margin:0 0 8px}
.by{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--faint);margin:0 0 13px;line-height:1.5}
.blurb{margin:0 0 14px;color:#ded4c2}
.blurb .m{font-family:'JetBrains Mono',monospace;font-size:.92em}
.blurb sup,.blurb sub{font-size:.72em}
.more{font-family:'JetBrains Mono',monospace;font-size:12.5px;color:var(--gold);text-decoration:none;letter-spacing:.02em}
.more:hover{color:var(--gold2);text-decoration:underline}
footer{margin-top:52px;padding-top:18px;border-top:1px solid var(--line);color:var(--faint);font-family:'JetBrains Mono',monospace;font-size:11.5px;line-height:1.7}
footer a{color:var(--gold);text-decoration:none}footer a:hover{text-decoration:underline}"""


def build_html(meta, lead, rubrics, src_name):
    kick = f"MATEMDIGEST · ВЫПУСК №{esc(meta.get('number',''))}"
    if meta.get('date'):
        kick += ' · ' + ru_date_full(meta['date']).upper()
    P = [GEN_BANNER_HTML.format(src=src_name)]
    P.append('<!doctype html><html lang=ru><head><meta charset=utf-8>')
    P.append('<meta name=viewport content="width=device-width,initial-scale=1">')
    P.append(f"<title>MATEMDIGEST · выпуск №{esc(meta.get('number',''))}</title>")
    P.append('<link rel=preconnect href="https://fonts.googleapis.com">'
             '<link rel=preconnect href="https://fonts.gstatic.com" crossorigin>')
    P.append('<link href="https://fonts.googleapis.com/css2?family=Forum&family=Golos+Text:wght@400;500;600&family=JetBrains+Mono:wght@400;700&display=swap" rel=stylesheet>')
    P.append(f'<style>{STYLE}</style></head><body><div class=wrap>')
    P.append(f'<div class=kick>{kick}</div>')
    P.append(f"<h1>{esc(meta.get('subtitle',''))}</h1>")
    if lead:
        P.append('<p class=intro>' + '<br><br>'.join(render_inline_html(p) for p in paras(lead)) + '</p>')

    for rname, items in rubrics:
        if rname:
            P.append(f'<div class=rubric>{esc(rname)}</div>')
        for j, it in enumerate(items):
            m = it['meta']
            if j > 0:
                P.append('<div class=rule></div>')
            P.append('<article class=item>')
            row = [f"<span class=kind>{esc((m.get('kind','') or '').upper())}</span>"]
            if m.get('date'):
                row.append(f"<span class=date>{esc(ru_date_short(m['date']))}</span>")
            P.append('<div class=meta>' + ''.join(row) + '</div>')
            P.append(f"<h2 class=title>{esc(it['title'])}</h2>")
            P.append(f"<div class=by>{esc(byline_str(m))}</div>")
            for p in paras(it['blurb']):
                P.append(f'<p class=blurb>{render_inline_html(p)}</p>')
            P.append(f"<a class=more href=\"{esc(m.get('url',''))}\" target=_blank rel=noopener>Читать →</a>")
            P.append('</article>')

    ch = ''
    if meta.get('channel'):
        if meta.get('channel_url'):
            ch = f"Канал <a href=\"{esc(meta['channel_url'])}\" target=_blank rel=noopener>«{esc(meta['channel'])}»</a> · "
        else:
            ch = f"Канал «{esc(meta['channel'])}» · "
    P.append(f'<footer>{ch}MATEMDIGEST — дайджест высокой математики<br>'
             f'собрано из {esc(src_name)} генератором build_vypusk.py · правь источник, не HTML</footer>')
    P.append('</div></body></html>')
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
    for rname, items in rubrics:
        if rname:
            L.append(f"▎<b>{esc(rname.upper(), quote=False)}</b>")
            L.append('')
        for it in items:
            m = it['meta']
            L.append(f"<b><a href=\"{esc(m.get('url',''), quote=True)}\">{esc(it['title'], quote=False)}</a></b>")
            head = (m.get('kind', '') or '').upper()
            for x in (m.get('byline'), m.get('source')):
                if x:
                    head += ' · ' + x
            if m.get('date'):
                head += ' · ' + ru_date_short(m['date'])
            L.append(esc(head, quote=False))
            if m.get('areas'):
                L.append(f"<i>{esc(m['areas'], quote=False)}</i>")
            L.append('')
            for p in paras(it['blurb']):
                L.append(render_inline_plain(p))
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

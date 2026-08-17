#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_intervyu.py — одностраничник интервью из markdown-источника.

Философия та же, что у build_vypusk.py: markdown — ИСТОЧНИК ИСТИНЫ,
HTML — только ВИД. Правь .md, пересобирай. Чистая stdlib, без сети.

Формат источника:
  # Заголовок                ← <h1>
  **Вопрос?**                ← абзац целиком в ** ** = реплика интервьюера
  Обычный абзац              ← ответ
  *Курсивный абзац*          ← служебная строка в конце (кто беседовал, оригинал)
  ---                        ← горизонтальное правило

Палитра и шрифты — те же, что в build_vypusk.py (Atlas), чтобы страница
садилась рядом с выпуском.

Запуск:
  python3 build_intervyu.py Vyazovskaya-intervyu-2022-perevod.md
"""
import re, sys
from pathlib import Path
from html import escape as esc

BANNER = ("<!-- СГЕНЕРИРОВАНО ИЗ {src} ГЕНЕРАТОРОМ build_intervyu.py — "
          "РУКАМИ НЕ ПРАВИТЬ. Правь markdown-источник, пересобирай (0 токенов). -->\n")

STYLE = """*{box-sizing:border-box}
:root{--bg:#14110d;--ink:#ece3d2;--mut:#a89c86;--faint:#6b6252;--line:rgba(236,227,210,.13);--gold:#cea24a;--gold2:#e6c26f}
body{margin:0;background:var(--bg);color:var(--ink);font-family:'Golos Text',system-ui,sans-serif;
 font-size:clamp(25px,1.72vw,38px);line-height:1.58;
 background-image:radial-gradient(900px 500px at 15% -8%,rgba(206,162,74,.12),transparent 60%);-webkit-font-smoothing:antialiased}
.wrap{width:min(1780px,93vw);margin:0 auto;padding:clamp(34px,3.4vw,72px) 0 clamp(60px,6vw,120px)}
.kick{font-family:'JetBrains Mono',monospace;font-size:.66em;letter-spacing:.28em;text-transform:uppercase;color:var(--gold);margin-bottom:16px}
h1{font-family:'Forum',serif;font-weight:400;font-size:clamp(46px,6vw,104px);margin:0 0 clamp(30px,3.4vw,58px);line-height:1.03;overflow-wrap:break-word}
p{margin:0 0 1.05em}
.q{color:var(--gold2);font-weight:500;margin-top:1.9em}
.q:first-of-type{margin-top:0}
hr{border:0;height:1px;background:var(--line);margin:clamp(38px,3.4vw,64px) 0 clamp(26px,2.4vw,40px)}
.note{color:var(--faint);font-size:.84em;line-height:1.5;margin-bottom:.5em}
"""

HEAD = """<!doctype html><html lang=ru><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>{title}</title>
<link rel=preconnect href="https://fonts.googleapis.com"><link rel=preconnect href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Forum&family=Golos+Text:wght@400;500&family=JetBrains+Mono:wght@400&display=swap" rel=stylesheet>
<style>{style}</style></head><body><div class=wrap>
"""


def inline(s: str) -> str:
    """Экранируем, потом возвращаем «...» и тире как есть; ссылок в источнике нет."""
    return esc(s)


def build(src: Path, sayt_slug: str = '') -> list:
    blocks = [b.strip() for b in src.read_text(encoding='utf-8').split('\n\n')]
    blocks = [b for b in blocks if b]

    title, out = '', []
    for b in blocks:
        if b.startswith('# '):
            title = b[2:].strip()
            out.append('<div class=kick>интервью</div>')
            out.append(f'<h1>{inline(title)}</h1>')
        elif set(b) <= set('-') and len(b) >= 3:
            out.append('<hr>')
        elif b.startswith('**') and b.endswith('**'):
            out.append(f'<p class=q>{inline(b[2:-2].strip())}</p>')
        elif b.startswith('*') and b.endswith('*'):
            out.append(f'<p class=note>{inline(b[1:-1].strip())}</p>')
        else:
            out.append(f'<p>{inline(b)}</p>')

    if not title:
        sys.exit('нет заголовка «# ...» в источнике')

    html = (BANNER.format(src=src.name)
            + HEAD.format(title=esc(title), style=STYLE)
            + '\n'.join(out) + '\n</div></body></html>\n')
    dst = src.with_suffix('.html')
    dst.write_text(html, encoding='utf-8')
    written = [dst]

    # Вид для сайта: Hugo отдаёт static/<слаг>/index.html как /<слаг>/ —
    # так же, как лежат выпуски (static/1|2|3). Тот же html, второй адрес.
    if sayt_slug:
        pub = src.parent / 'sayt' / 'static' / sayt_slug / 'index.html'
        pub.parent.mkdir(parents=True, exist_ok=True)
        pub.write_text(html, encoding='utf-8')
        written.append(pub)

    return written


if __name__ == '__main__':
    args = sys.argv[1:]
    slug = ''
    if '--sayt' in args:
        i = args.index('--sayt')
        if i + 1 >= len(args):
            sys.exit('--sayt требует слаг, например: --sayt vyazovskaya')
        slug = args[i + 1]
        del args[i:i + 2]
    if len(args) != 1:
        sys.exit('использование: python3 build_intervyu.py ИСТОЧНИК.md [--sayt СЛАГ]')
    for p in build(Path(args[0]), slug):
        print(f'✓ {p}  ({p.stat().st_size // 1024} КБ)')

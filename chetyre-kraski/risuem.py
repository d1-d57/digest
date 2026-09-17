#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Схемы ленты «Двенадцать единиц кривизны».

Словарь примитивов — скилл `illustracii`; носитель классов `.s-*` —
`disciplina/_generator/build_doc.py`, СВОИХ классов здесь не заводится.
Четыре краски карты набраны существующими заливками движка:

    s-node              --panel   почти белая
    s-line s-fillsh     --shade   бледно-голубая
    s-line s-fillw      --warm    оранжевая
    s-node-a            --accent  синяя

Порядок в CSS движка (build_doc.py:1526–1538) таков, что `s-line` объявлен
РАНЬШЕ заливок, поэтому пара «s-line + заливка» даёт заливку и чернильную
обводку. Обратный порядок не сработал бы молча — это ловушка словаря.

Внутри рисунков нет ни одной буквы: вся проза живёт в `figcaption`.

    python3 risuem.py risovat                    # → illustrations/*.svg
    python3 risuem.py vstavit LENTA-…/lenta.md   # вклеить в источник ленты
    python3 risuem.py png LENTA-…/lenta.md       # → LENTA-…-png/ для гейта L13
"""
import math
import pathlib
import re
import sys

KOREN = pathlib.Path(__file__).parent
SVG = KOREN / "illustrations"

# ЧЕТЫРЕ КРАСКИ И ЧЕМ ЗА НИХ ПЛАТИМ. Замерено рендером 900px, не прикидкой.
# Движок даёт пять заливок, и как НАБОР ЧЕТЫРЁХ РАВНОПРАВНЫХ КРАСОК они не работают:
#   --panel  #fffdf8  на бумаге #fbfaf6 читается пустым местом, а не краской;
#   --shade  #dfeaf0  на узле размером с точку неотличим от полого узла;
#   --text   #211f1b  большим пятном забивает рисунок (первый прогон карты — два
#                     чёрных прямоугольника съели всю схему).
# Отсюда правило этой ленты: сильных красок три (shade, warm, accent), а чернильная
# заливка идёт ЧЕТВЁРТОЙ и только на мелком элементе — на узле, не на области.
KRASKI = ("s-line s-fillsh", "s-line s-fillw", "s-node-a", "s-node s-node-r")


def svg(name, vb, aria, body):
    SVG.mkdir(exist_ok=True)
    doc = (f'<svg viewBox="{vb}" role="img" aria-label="{aria}" '
           f'xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">'
           + body + '</svg>')
    (SVG / f"{name}.svg").write_text(doc, encoding="utf-8")


def node(x, y, cls="s-node", r=5.0):
    return f'<circle class="{cls}" cx="{x:.1f}" cy="{y:.1f}" r="{r}"/>'


def line(x1, y1, x2, y2, cls="s-line"):
    return f'<line class="{cls}" x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"/>'


def poly(points, cls):
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    return f'<polygon class="{cls}" points="{pts}"/>'


def strelka(x1, y, x2):
    return (f'<line class="s-thin" x1="{x1}" y1="{y}" x2="{x2 - 8}" y2="{y}"/>'
            f'<path class="s-ar-m" d="M {x2 - 9},{y - 4} l9,4 -9,4 z"/>')


# ── 1. Карта становится графом ───────────────────────────────────────────────
OBLASTI = [  # многоугольник, номер краски, столица
    ([(10, 5), (120, 5), (120, 105), (10, 105)], 0, (65, 55)),
    ([(120, 5), (220, 5), (220, 65), (120, 65)], 1, (170, 35)),
    ([(120, 65), (220, 65), (220, 105), (120, 105)], 2, (170, 85)),
    ([(220, 5), (310, 5), (310, 95), (220, 95)], 0, (265, 50)),
    ([(220, 95), (310, 95), (310, 185), (220, 185)], 1, (265, 140)),
    ([(10, 105), (120, 105), (120, 185), (10, 185)], 1, (65, 145)),
    ([(120, 105), (220, 105), (220, 185), (120, 185)], 3, (170, 145)),
]
REBRA = [(0, 1), (0, 2), (0, 5), (1, 2), (1, 3), (2, 3), (2, 4), (2, 6), (3, 4), (4, 6), (5, 6)]


def fig_karta_graf():
    """Работа рисунка — перевод, а не раскраска: краски показывает соседняя схема."""
    karta = [poly(p, "s-line") for p, _, _ in OBLASTI]
    for _, _, (cx, cy) in OBLASTI:
        karta.append(node(cx, cy, "s-node", 4.0))
    graf = [poly(p, "s-thin") for p, _, _ in OBLASTI]
    for i, j in REBRA:
        graf.append(line(*OBLASTI[i][2], *OBLASTI[j][2]))
    for _, _, (cx, cy) in OBLASTI:
        graf.append(node(cx, cy, "s-node", 6.0))
    svg("karta-graf", "0 0 666 200",
        "Слева карта из семи областей с точкой-столицей в каждой; "
        "справа остались только точки и отрезки между теми из них, "
        "чьи области имеют общий участок границы",
        "".join(karta) + strelka(318, 95, 342)
        + '<g transform="translate(348,0)">' + "".join(graf) + "</g>")


# ── 2. Конфигурация внутри кольца ────────────────────────────────────────────
def fig_konfiguraciya():
    cx, cy, r_k, r_v = 160.0, 125.0, 60.0, 105.0
    kolco = [(cx + r_k * math.cos(math.radians(a)), cy + r_k * math.sin(math.radians(a)))
             for a in (-90, -18, 54, 126, 198)]
    vne = [(cx + r_v * math.cos(math.radians(a)), cy + r_v * math.sin(math.radians(a)))
           for a in (-54, 18, 90, 162, 234)]
    cveta = [1, 2, 0, 1, 2]   # warm · accent · shade · warm · accent; соседи различны

    def panel(zakrashen):
        p = []
        for k, (ox, oy) in enumerate(vne):
            p.append(line(ox, oy, *kolco[k], "s-thin"))
            p.append(line(ox, oy, *kolco[(k + 1) % 5], "s-thin"))
            p.append(line(ox, oy, *vne[(k + 1) % 5], "s-thin"))
        for k in range(5):
            p.append(line(*kolco[k], *kolco[(k + 1) % 5]))
            p.append(line(cx, cy, *kolco[k]))
        for k, (rx, ry) in enumerate(kolco):
            p.append(node(rx, ry, KRASKI[cveta[k]], 7))
        for ox, oy in vne:
            p.append(node(ox, oy, "s-node", 4.4))
        p.append(node(cx, cy, KRASKI[3] if zakrashen else "s-node", 7.5))
        return "".join(p)

    svg("konfiguraciya", "0 0 660 250",
        "Кольцо из пяти покрашенных вершин вокруг одной пустой; "
        "справа та же картинка, где центральная вершина получила четвёртую краску",
        panel(False) + strelka(300, 125, 338)
        + '<g transform="translate(340,0)">' + panel(True) + "</g>")


# ── 3. Равнина растёт, холмы — нет ───────────────────────────────────────────
DX, DY = 21.0, 18.19


def reshetka(stolbcov, ryadov, ox, oy, holmy):
    """Кусок треугольной решётки. Линии — тремя семействами прямых путей, а не
    сотнями отрезков: иначе рисунок весит полсотни килобайт прямо в источнике.

    Смещение нечётных рядов на полшага задаёт соседей вниз так:
        ряд чётный   → (r+1, c−1) и (r+1, c)
        ряд нечётный → (r+1, c)   и (r+1, c+1)
    Это и есть два диагональных семейства. Наивная арифметика «по номеру
    диагонали» даёт зигзаг вместо прямой — поймано рендером, не чтением."""
    poz = {(r, c): (ox + c * DX + (r % 2) * DX / 2, oy + r * DY)
           for r in range(ryadov) for c in range(stolbcov)}

    def sled(semja, r, c):
        if semja == "levoe":
            return (r + 1, c - 1 if r % 2 == 0 else c)
        return (r + 1, c if r % 2 == 0 else c + 1)

    p = []
    for r in range(ryadov):                                    # горизонтали
        p.append(line(*poz[(r, 0)], *poz[(r, stolbcov - 1)], "s-thin"))
    for semja in ("levoe", "pravoe"):                          # две диагонали
        prishli = {sled(semja, r, c) for (r, c) in poz}
        for nachalo in sorted(poz):
            if nachalo in prishli:
                continue
            cep, uzel = [], nachalo
            while uzel in poz:
                cep.append(poz[uzel])
                uzel = sled(semja, *uzel)
            if len(cep) > 1:
                p.append('<polyline class="s-thin" points="'
                         + " ".join(f"{x:.1f},{y:.1f}" for x, y in cep) + '"/>')
    for (r, c), (x, y) in poz.items():
        holm = (r, c) in holmy
        p.append(node(x, y, "s-node-a" if holm else "s-node", 4.8 if holm else 3.4))
    return "".join(p), (stolbcov - 1) * DX + DX / 2, (ryadov - 1) * DY


def fig_dvenadcat():
    plany = [
        (5, 4, [(0, 0), (0, 2), (0, 4), (1, 1), (1, 3), (2, 0), (2, 2),
                (2, 4), (3, 1), (3, 3), (1, 0), (3, 0)]),
        (8, 6, [(0, 1), (0, 5), (1, 3), (1, 7), (2, 0), (2, 4), (3, 2),
                (3, 6), (4, 1), (4, 5), (5, 3), (5, 7)]),
        (12, 8, [(0, 3), (0, 9), (1, 6), (2, 1), (2, 11), (3, 4), (4, 8),
                 (5, 2), (5, 10), (6, 6), (7, 0), (7, 9)]),
    ]
    chasti, x = [], 20.0
    for st, ry, holmy in plany:
        g, w, h = reshetka(st, ry, x, 128 - (ry - 1) * DY / 2, set(holmy))
        chasti.append(f"<g>{g}</g>")
        x += w + 42
    svg("dvenadcat", f"0 0 {x - 42 + 20:.0f} 256",
        "Три куска треугольной решётки разного размера; "
        "в каждом ровно двенадцать залитых вершин, "
        "а число пустых растёт вместе с решёткой",
        "".join(chasti))


# ── 4. Минус константа против «в константу раз» ──────────────────────────────
def fig_shagi():
    x0, w0, vh, zazor = 30.0, 560.0, 11.0, 6.0
    p, y, w = [], 18.0, w0
    for _ in range(9):
        p.append(f'<rect class="s-line s-fillsh" x="{x0}" y="{y:.1f}" '
                 f'width="{w:.1f}" height="{vh}" rx="2"/>')
        y += vh + zazor
        w -= 42
    for k in range(3):
        p.append(node(x0 + 8 + k * 13, y + 6, "s-node", 2.6))
    y, w = 190.0, w0
    for _ in range(5):
        p.append(f'<rect class="s-node-a" x="{x0}" y="{y:.1f}" '
                 f'width="{w:.1f}" height="{vh}" rx="2"/>')
        y += vh + zazor
        w /= 2
    svg("shagi", "0 0 620 290",
        "Сверху длинный столбик полос, каждая короче предыдущей на одинаковую величину; "
        "снизу пять полос, каждая вдвое короче предыдущей",
        "".join(p))


# ── вклейка в источник ленты ─────────────────────────────────────────────────
FIGURA_RE = re.compile(r'(<figure data-imya="([a-z-]+)">)(.*?)(<figcaption>)', re.S)


def vstavit(put_lenty):
    """Схема живёт в figure по имени: комментариев-маркеров нет, потому что
    check_view.py сверяет источник с видом построчно и чужой пассаж ловит."""
    tekst = pathlib.Path(put_lenty).read_text(encoding="utf-8")

    def zamena(m):
        telo = (SVG / f"{m.group(2)}.svg").read_text(encoding="utf-8").strip()
        return m.group(1) + telo + m.group(4)

    novyj, n = FIGURA_RE.subn(zamena, tekst)
    pathlib.Path(put_lenty).write_text(novyj, encoding="utf-8")
    print(f"вклеено схем: {n}")


# ── PNG для гейта L13 ────────────────────────────────────────────────────────
# cairosvg классов не применяет (ловушка словаря) — разворачиваем их в атрибуты
# ровно теми значениями, что стоят в движке-носителе.
CVET = {"text": "#211f1b", "muted": "#726c60", "accent": "#2f6e8e",
        "warm": "#c9743a", "shade": "#dfeaf0", "panel": "#fffdf8"}

# Порядок строк = порядок каскада в build_doc.py (1526→1550): класс ниже в списке
# перебивает свойство класса выше. Пара классов на элементе разворачивается
# слиянием словарей в этом порядке — иначе выходит двойной `fill` и битый XML.
KASKAD = [
    ("s-line",   {"fill": "none", "stroke": CVET["text"], "stroke-width": "2"}),
    ("s-thin",   {"fill": "none", "stroke": CVET["muted"], "stroke-width": "1.2"}),
    ("s-dash",   {"fill": "none", "stroke": CVET["accent"], "stroke-width": "1.3",
                  "stroke-dasharray": "4 4"}),
    ("s-accent", {"fill": "none", "stroke": CVET["accent"], "stroke-width": "2.4"}),
    ("s-fillw",  {"fill": CVET["warm"]}),
    ("s-fillsh", {"fill": CVET["shade"]}),
    ("s-node",   {"fill": CVET["panel"], "stroke": CVET["text"], "stroke-width": "1.8"}),
    ("s-node-r", {"fill": CVET["text"]}),
    ("s-node-a", {"fill": CVET["accent"], "stroke": CVET["accent"]}),
    ("s-thin-a", {"fill": "none", "stroke": CVET["accent"], "stroke-width": "1.4"}),
    ("s-ar-a",   {"fill": CVET["accent"]}),
    ("s-ar-m",   {"fill": CVET["muted"]}),
]


def razvernut(telo):
    """Классы → атрибуты. cairosvg CSS не применяет — без этого всё выйдет чёрным."""
    def odin(m):
        klassy = set(m.group(1).split())
        svojstva = {}
        for imya, pravilo in KASKAD:
            if imya in klassy:
                svojstva.update(pravilo)
                klassy.discard(imya)
        if klassy:
            sys.exit("класс вне носителя: %s" % sorted(klassy))
        return " ".join(f'{k}="{v}"' for k, v in svojstva.items())
    return re.sub(r'class="([^"]+)"', odin, telo)


def png(put_lenty):
    import cairosvg
    ist = pathlib.Path(put_lenty)
    papka = ist.parent / (ist.stem + "-png")
    papka.mkdir(exist_ok=True)
    sxemy = [(m.group(2), m.group(3)) for m in FIGURA_RE.finditer(ist.read_text(encoding="utf-8"))]
    for imya, telo in sxemy:
        plosk = razvernut(telo)
        plosk = re.sub(r'\swidth="\d+"', "", plosk, count=1)  # ловушка cairosvg
        plosk = plosk.replace("<svg ", '<svg style="background:%s" ' % CVET["panel"], 1)
        cairosvg.svg2png(bytestring=plosk.encode("utf-8"),
                         write_to=str(papka / f"{imya}.png"), output_width=900)
    print(f"отрисовано PNG: {len(sxemy)} → {papka}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "risovat"
    if cmd == "risovat":
        fig_karta_graf(); fig_konfiguraciya(); fig_dvenadcat(); fig_shagi()
        print("нарисовано:", *sorted(f.name for f in SVG.glob("*.svg")))
    elif cmd == "vstavit":
        vstavit(sys.argv[2])
    elif cmd == "png":
        png(sys.argv[2])
    else:
        sys.exit("команды: risovat | vstavit <lenta.md> | png <lenta.md>")

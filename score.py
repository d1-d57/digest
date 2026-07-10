#!/usr/bin/env python3
"""Скоринг и теги — прозрачная эвристика (рубрика в README).
Карта для человека, не готовая лента: скорим и тегируем, НЕ выкидываем (§2)."""

import re

# --- классификатор раздела по ключевым словам (title+summary) -------------
AREA_KEYWORDS = [
    ("теория чисел",        r"number theory|prime|riemann|zeta|modular form|elliptic curve|diophantine|arithmetic geometr|langlands|automorphic|galois|l-function|analytic number"),
    ("алгебраическая геометрия", r"algebraic geometr|scheme|motive|moduli|birational|hodge|sheaf|derived categor|intersection theory|toric"),
    ("топология",           r"topolog|homotopy|manifold|knot|cobordism|homolog|cohomolog|4-manifold|floer|gauge theor|surgery"),
    ("дифференциальная геометрия", r"differential geometr|riemannian|curvature|ricci|minimal surface|symplectic|kähler|kahler|geometric flow|mean curvature"),
    ("анализ",              r"harmonic analysis|functional analysis|operator|fourier|measure theor|ergodic|complex analysis|real analysis|potential theory"),
    ("уравнения в частных производных", r"\bpde\b|partial differential|navier-stokes|wave equation|schrödinger equation|elliptic equation|dispersive|fluid"),
    ("математическая физика", r"mathematical physics|quantum field|conformal field|string theor|statistical mechanic|integrable system|yang-mills|renormaliz|spin glass"),
    ("комбинаторика",       r"combinatoric|graph theor|ramsey|extremal|additive combinatoric|hypergraph|matching|coloring|enumerat|polytope|design theor"),
    ("логика",              r"\blogic\b|set theory|model theory|proof theory|forcing|large cardinal|computability|decidab|foundations of math|homotopy type"),
    ("вероятность",         r"probabilit|random|stochastic|martingale|percolation|brownian|markov chain|random matri|random graph"),
    ("теория представлений", r"representation theor|lie group|lie algebra|character|hecke|quantum group|categorification"),
    ("динамические системы", r"dynamical system|ergodic theor|chaos|billiard|geodesic flow|teichmüller|homogeneous dynamic"),
    ("алгебра",             r"group theor|ring theor|field theor|commutative algebra|homological algebra|category theor|operad|k-theory"),
    ("теория чисел/криптография", r"cryptograph|lattice-based|post-quantum"),
    ("computer science",    r"algorithm|complexity|computation|machine learning|neural|quantum comput|\bp vs np\b|optimization|data structure|error-correcting"),
    ("статистика",          r"statistic|inference|regression|causal|high-dimensional data"),
    ("математическая биология", r"mathematical biolog|epidemi|population dynamic|evolutionary game"),
    ("история/философия математики", r"history of math|biograph|obituary|memorial|centenary|anniversary|philosophy of math|in memoriam"),
    ("геометрия",           r"\bgeometr|convex|discrete geometr|packing|tiling"),
]

def classify_area(text, fallback=None):
    t = (text or "").lower()
    for area, pat in AREA_KEYWORDS:
        if re.search(pat, t):
            return area
    return fallback  # может остаться None -> "лучшая догадка не найдена"

# --- ключи широты/значимости --------------------------------------------
BREADTH_HI = r"why|how|explain|introduction|survey|overview|guide|panorama|the joy|what is|beginner|for everyone|breakthrough|solved|proof of|resolves|famous|century-old|long-standing|mystery|puzzle"
SIGNIF_HI  = r"fields medal|abel prize|breakthrough prize|wolf prize|icm|plenary|major|resolves|proves|counterexample|first|new proof|settles|conjecture"

# базовые уровни широты/значимости по (категория, тип, источник)
def base_scores(cat, typ, source):
    s = (source or "").lower()
    # (breadth, significance)
    if cat == "C":                       # научпоп — по определению широкий
        return 4, 2
    if cat == "B":                       # обзорные площадки для широкой аудитории
        if "icm" in s: return 4, 5
        if "bourbaki" in s: return 4, 4
        if "current events" in s: return 5, 4   # CEB — прямо «legible across fields»
        return 4, 3
    if cat == "A":                       # проф. обзоры
        if "notices" in s: return 4, 3   # Notices — для широкой мат-аудитории
        if "bulletin of the ams" in s: return 4, 3
        return 3, 3                      # узкие обзоры — легибельны в своём поле
    if cat == "D":                       # блоги
        return 2, 2
    if cat == "E":
        if typ in ("prize",): return 4, 5
        if typ in ("interview","podcast"): return 4, 2
        if typ in ("book","review"): return 3, 2
        if typ in ("anniversary","obituary"): return 4, 2
        if typ == "video": return 4, 2
        return 3, 2
    return 2, 2

def clamp(x): return max(0, min(5, x))

def score_row(row):
    """Возвращает (breadth, significance, tags[list]). Не мутирует row."""
    cat, typ, source = row.get("category"), row.get("type"), row.get("source_name")
    text = f"{row.get('title','')} {row.get('summary','') or ''}".lower()
    b, s = base_scores(cat, typ, source)
    tags = []

    # межпредметность/легибельность поднимает широту
    if re.search(BREADTH_HI, text):
        b += 1; tags.append("legible")
    # два+ разных раздела упомянуты -> кросс-полевое
    hit_areas = sum(1 for _, pat in AREA_KEYWORDS if re.search(pat, text))
    if hit_areas >= 2:
        b += 1; tags.append("cross-field")
    if re.search(SIGNIF_HI, text):
        s += 1; tags.append("high-signif")

    # экспозиция vs анонс
    if typ in ("survey","expository","popsci","review","book") or re.search(r"survey|expositor|introduction|overview|explain", text):
        tags.append("expository")
    if re.search(r"announc|preprint|new result|we prove|arxiv", text):
        tags.append("announcement")

    # добываемость (для книг/ресурсов)
    if typ in ("book","video","podcast","interview"):
        tags.append("extractable")

    # Quanta-метка
    if "quanta" in (source or "").lower():
        tags.append("is_quanta")

    # тип-производные теги
    if typ: tags.append(f"type:{typ}")

    return clamp(b), clamp(s), sorted(set(tags))

# --- явный не-математический мусор (жёсткий дроп, со счётчиком) -----------
JUNK = r"\b(recipe|celebrity|gossip|nfl|nba|horoscope|casino|weather forecast|stock tip)\b"
def is_junk(row):
    text = f"{row.get('title','')} {row.get('summary','') or ''}".lower()
    return bool(re.search(JUNK, text)) and "math" not in text

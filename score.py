#!/usr/bin/env python3
"""Скоринг и теги — прозрачная эвристика (рубрика в README).
Карта для человека, не готовая лента: скорим и тегируем, НЕ выкидываем (§2)."""

import re
import html as _html

# --- нормализация заголовка (чистка сырого MathML/HTML из Crossref) --------
# Заголовки журналов через Crossref иногда приходят с непроэкранированными
# MathML/HTML: '<mml:math ...>', '<italic>', '&lt;em&gt;'. Делаем читаемым:
# unescape entities -> снять теги -> схлопнуть пробелы. Строку НЕ удаляем.
_TAG = re.compile(r"<[^>]+>")
def clean_title(title):
    if not title:
        return title
    t = _html.unescape(title)          # &lt;em&gt; -> <em>
    t = _TAG.sub(" ", t)               # снять <...> (в т.ч. <mml:math ...>)
    t = _html.unescape(t)              # добить двойное экранирование
    t = re.sub(r"\s+", " ", t).strip() # схлопнуть переносы/пробелы
    return t

# --- классификатор раздела по ключевым словам (title+summary) -------------
AREA_KEYWORDS = [
    ("история/философия математики", r"history of math|biograph|obituary|memorial|in memoriam|remembering|centenary|anniversary|philosophy of math|mathematics people|\bmemorial tribute"),
    ("теория чисел",        r"number theor|\bprime|riemann|\bzeta\b|modular form|elliptic curve|diophantine|arithmetic geometr|langlands|automorphic|\bgalois|l-function|analytic number|sumset|sieve method|class field|arithmetic statistic|transcendence|continued fraction|\bpartition\b|bsd|birch|szemer|van der corput|mahler"),
    ("алгебраическая геометрия", r"algebraic geometr|\bscheme|\bmotiv|moduli|birational|\bhodge|\bsheaf|derived categor|intersection theory|\btoric|slice theorem|geometric invariant|\bgit\b|vector bundle|line bundle|resolution of singular|minimal model|gromov-witten|enumerative geometr|luna|algebraic stack|abelian variet"),
    ("топология",           r"topolog|homotopy|manifold|\bknot\b|cobordism|homolog|cohomolog|farrell-jones|mapping class group|characteristic class|fiber bundle|floer|gauge theor|surgery|\bspectra\b|configuration space|braid group"),
    ("дифференциальная геометрия", r"differential geometr|riemannian|\bcurvature|\bricci|minimal surface|symplectic|kähler|kahler|geometric flow|mean curvature|geodesic|einstein metric|yamabe|sectional curvature|willmore"),
    ("анализ",              r"harmonic analysis|functional analysis|\boperator|fourier|measure theor|ergodic|complex analysis|real analysis|potential theory|asymptotic spectra|spectral theor|banach|hilbert space|sobolev|singular integral|hardy space|approximation theor|\bspectrum\b"),
    ("уравнения в частных производных", r"\bpde\b|partial differential|navier-stokes|wave equation|schrödinger|elliptic equation|dispersive|\bfluid|free boundary|regularity of solution|boltzmann|heat equation"),
    ("математическая физика", r"mathematical physics|quantum field|conformal field|string theor|statistical mechanic|integrable system|yang-mills|renormaliz|spin glass|gauge/gravity|standard model|octonion|quantum mechanic|scattering|feynman|topological quantum"),
    ("комбинаторика",       r"combinator|graph theor|ramsey|extremal|additive combinatoric|hypergraph|\bmatching|coloring|enumerat|polytope|design theor|\bposet\b|tensor rank|sunflower|expander|latin square|sum-free|incidence"),
    ("логика",              r"\blogic\b|set theory|model theory|proof theory|forcing|large cardinal|computability|decidab|foundations of math|homotopy type|formaliz|proof assistant|\blean\b|type theory|reverse math|o-minimal|continuum hypothesis|\bzfc\b"),
    ("вероятность",         r"probabilit|\brandom|stochastic|martingale|percolation|brownian|markov|random matri|random graph|\bkpz\b|directed landscape|interacting particle|self-avoiding"),
    ("теория представлений", r"representation theor|\blie group|lie algebra|\bcharacter variet|\bhecke|quantum group|categorif|cluster algebra|kazhdan|geometric langlands|symmetric function|\bkac-moody"),
    ("динамические системы", r"dynamical system|ergodic theor|\bchaos|billiard|geodesic flow|teichm|homogeneous dynamic|entropy|renormalization group|circle diffeomorph|translation surface|thurston"),
    ("алгебра",             r"group theor|\bring theor|field theor|commutative algebra|homological algebra|category theor|\boperad|k-theory|galois cohomolog|finite group|hopf algebra|\bmonoid|semigroup|lattice theor"),
    ("теория чисел/криптография", r"cryptograph|lattice-based|post-quantum|zero-knowledge|homomorphic encrypt"),
    ("computer science",    r"algorithm|complexity|computation|machine learning|neural|quantum comput|\bp vs np\b|\bp=np|optimization|data structure|error-correcting|\bsat\b|circuit complex|coding theor|\bllm\b|artificial intelligence|chatgpt"),
    ("статистика",          r"statistic|\binference|regression|causal|high-dimensional data|compressed sensing|signal process"),
    ("математическая биология", r"mathematical biolog|epidemi|population dynamic|evolutionary game|neuroscience"),
    ("геометрия",           r"\bgeometr|\bconvex|discrete geometr|packing|tiling|kakeya|distance problem|polygon|origami"),
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

# --- явный не-математический мусор (жёсткий дроп, со счётчиком, §2) --------
JUNK = r"\b(recipe|celebrity|gossip|nfl|nba|horoscope|casino|weather forecast|stock tip)\b"
# Редакционно-административный балласт бюллетеней (Notices/AMS): не материалы, а
# служебные колонки. Матчим по заголовку целиком — это структурные рубрики.
ADMIN = re.compile(
    r"^(classified advertising|ams updates|calls? for (nominations|applications|proposals|papers)"
    r"|state of the ams|from the ams|reciprocity agreement|report of the (treasurer|secretary)"
    r"|\d{4} election|election (results|information)|new members of the ams|ams officers"
    r"|mathematics opportunities|deaths of ams members|in memory of members"
    r"|editorial board|publisher.s note)\b", re.I)  # +масштхед журналов (ЗАХОД-1)

def is_junk(row):
    title = (row.get("title") or "").strip().lower()
    if ADMIN.match(title):
        return True
    text = f"{title} {row.get('summary','') or ''}"
    return bool(re.search(JUNK, text)) and "math" not in text

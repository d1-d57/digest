#!/usr/bin/env python3
"""
pull_surveys.py — вычёрпывает ГОД обзорных/экспозиционных статей из
профессионального журнального слоя через Crossref REST API (по ISSN).

Зачем: веб-поиск отдаёт описания журналов, а не оглавления. Crossref отдаёт
КАЖДУЮ статью журнала за период — название, авторов, дату, DOI-ссылку.

Где запускать: там, где доступен api.crossref.org (Claude Code на твоей машине,
локальный терминал, любой сервер). В песочнице чата этот домен закрыт — поэтому
скрипт отдаётся тебе как артефакт, а не гоняется здесь.

    pip install requests
    python pull_surveys.py > surveys_year.md

Bull AMS / Russian Math Surveys / EMS Surveys — почти целиком обзорные, фильтр не нужен.
Notices — смешанный (features + новости + рецензии), фильтруется эвристикой (см. ниже, tunable).
Bourbaki в Crossref по ISSN не лежит чисто — тянется отдельно со страницы bourbaki.fr
(там обычная статическая программа, парсится тривиально; добавлю по запросу).
"""

import requests, time

MAILTO = "you@example.com"        # Crossref "polite pool": подставь свой email
FROM    = "2025-07-01"            # начало окна
UNTIL   = "2026-07-10"           # конец окна

# name, [ISSN...], note. Скрипт печатает журналы, по которым Crossref ничего не отдал,
# чтобы сразу видеть, где ISSN надо уточнить.
JOURNALS = [
    ("Bulletin of the AMS (New Series)",       ["0273-0979"],               "ежеквартально · целиком обзоры для не-специалистов + рецензии на книги"),
    ("Notices of the AMS",                     ["0002-9920", "1088-9477"],  "ежемесячно · 1–2 экспозиции/номер + memorials + Short Stories"),
    ("Russian Mathematical Surveys (УМН)",     ["0036-0279", "1468-4829"],  "двухмесячно · обзоры cover-to-cover"),
    ("EMS Surveys in Mathematical Sciences",   ["2308-2151", "2308-216X"],  "дважды в год · обзоры"),
    ("Bulletin of the London Math. Society",   ["0024-6093", "1469-2120"],  "обзоры среди research — фильтровать по 'Survey Article'"),
    ("Jahresbericht der DMV",                  ["0012-0456", "1869-7135"],  "обзоры/экспозиция (DE/EN)"),
    ("Acta Numerica",                          ["0962-4929", "1474-0508"],  "ежегодно · длинные обзоры по вычислительной математике"),
    ("Expositiones Mathematicae",              ["0723-0869"],               "экспозиция"),
    ("Japanese J. of Math (3rd ser.)",         ["0289-2316", "1861-3624"],  "Takagi lectures · обзоры"),
]

def fetch(issn):
    url = f"https://api.crossref.org/journals/{issn}/works"
    params = {
        "filter": f"from-pub-date:{FROM},until-pub-date:{UNTIL},type:journal-article",
        "select": "title,author,published,DOI,volume,issue,page",
        "rows": 500,
        "mailto": MAILTO,
    }
    try:
        r = requests.get(url, params=params, timeout=30)
        if r.status_code != 200:
            return None
        return r.json().get("message", {}).get("items", [])
    except requests.RequestException:
        return None

def authors(item):
    a = item.get("author") or []
    names = [" ".join(x for x in (p.get("given"), p.get("family")) if x) for p in a]
    if len(names) > 3:
        names = names[:3] + ["et al."]
    return ", ".join(names)

def pubdate(item):
    parts = (item.get("published") or {}).get("date-parts", [[None]])[0]
    return "-".join(f"{p:02d}" if isinstance(p, int) and p < 100 else str(p)
                    for p in parts if p is not None)

def looks_expository(item, journal):
    """Грубый фильтр только для смешанных журналов (Notices). Обзорные журналы
    пропускаем целиком. Эвристика: у экспозиции обычно >= 4 страниц; короткие
    заметки/новости отсекаются. Настраивай под себя."""
    if "Notices" not in journal:
        return True
    pg = item.get("page", "")
    try:
        lo, hi = (int(x) for x in pg.split("-")[:2])
        return (hi - lo) >= 3
    except Exception:
        return True  # если страниц нет — не выкидываем, пусть решает человек

print(f"# Обзоры мат-журналов, {FROM} — {UNTIL}\n")
total = 0
for name, issns, note in JOURNALS:
    items = None
    for issn in issns:
        items = fetch(issn)
        time.sleep(1)                      # вежливо к Crossref
        if items:
            break
    print(f"\n## {name}\n*{note}*\n")
    if not items:
        print("_(Crossref не отдал записи — уточнить ISSN или тянуть источник напрямую)_\n")
        continue
    kept = [it for it in items if looks_expository(it, name)]
    kept.sort(key=pubdate, reverse=True)
    for it in kept:
        title = (it.get("title") or ["—"])[0].strip()
        doi = it.get("DOI", "")
        vol = it.get("volume", ""); iss = it.get("issue", "")
        loc = f" · {vol}({iss})" if vol else ""
        print(f"- **{title}** — {authors(it) or '—'} · {pubdate(it)}{loc} · https://doi.org/{doi}")
        total += 1
print(f"\n---\n**Всего статей за период: {total}**")
print("\nПримечания: Bull AMS/УМН/EMS — чистые обзоры, берутся целиком (включая рецензии).")
print("Notices отфильтрован по длине; порог правится в looks_expository().")
print("Bourbaki (Astérisque) и блоги/Quanta тянутся отдельно (RSS/страница) — добавлю по запросу.")

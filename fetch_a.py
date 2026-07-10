#!/usr/bin/env python3
"""Категория A — проф. обзорные журналы через Crossref по ISSN.
Логика взята из pull_surveys.py (§0: переиспользуй, не переписывай с нуля),
но пишем в строки-словари для БД, а не в markdown."""

import requests, time
from config import FROM, UNTIL, MAILTO, HEADERS

# name, [ISSN...], тип-по-умолч, фильтровать_ли_notices, note
JOURNALS = [
    ("Bulletin of the AMS (New Series)",     ["0273-0979"],               "survey",     False, "целиком обзоры + рецензии на книги"),
    ("Notices of the AMS",                   ["0002-9920","1088-9477"],   "expository", True,  "features + memorials + Short Stories"),
    ("Russian Mathematical Surveys (УМН)",   ["0036-0279","1468-4829"],   "survey",     False, "обзоры cover-to-cover"),
    ("EMS Surveys in Mathematical Sciences", ["2308-2151","2308-216X"],   "survey",     False, "обзоры"),
    ("Bulletin of the London Math. Society", ["0024-6093","1469-2120"],   "survey",     "lms", "фильтр Survey Article среди research"),
    ("Jahresbericht der DMV",                ["0012-0456","1869-7135"],   "expository", False, "обзоры/экспозиция DE/EN"),
    ("Acta Numerica",                        ["0962-4929","1474-0508"],   "survey",     False, "длинные обзоры по выч. математике"),
    ("Expositiones Mathematicae",            ["0723-0869"],               "expository", False, "экспозиция"),
    ("Japanese J. of Math (3rd ser.)",       ["0289-2316","1861-3624"],   "survey",     False, "Takagi lectures · обзоры"),
]

def fetch(issn):
    url = f"https://api.crossref.org/journals/{issn}/works"
    params = {"filter": f"from-pub-date:{FROM},until-pub-date:{UNTIL},type:journal-article",
              "select": "title,author,published,DOI,volume,issue,page,subject",
              "rows": 500, "mailto": MAILTO}
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=30)
        if r.status_code != 200:
            return None, r.status_code
        return r.json().get("message", {}).get("items", []), 200
    except requests.RequestException as e:
        return None, str(e)

def _authors(item):
    a = item.get("author") or []
    names = [" ".join(x for x in (p.get("given"), p.get("family")) if x) for p in a]
    if len(names) > 3:
        names = names[:3] + ["et al."]
    return ", ".join(names) or None

def _pubdate(item):
    parts = (item.get("published") or {}).get("date-parts", [[None]])[0]
    out = "-".join(f"{p:02d}" if isinstance(p, int) and 0 < p < 100 else str(p)
                   for p in parts if p is not None)
    return out or None

def _survey_only(item, mode):
    """Фильтры для смешанных журналов. Возвращает (keep, reason_drop)."""
    title = " ".join(item.get("title") or []).lower()
    if mode == "lms":   # Bulletin LMS: только Survey Article
        return ("survey" in title), None
    if mode is True:    # Notices: отсечь короткие заметки (<4 стр), но не выкидываем без страниц
        pg = item.get("page", "") or ""
        try:
            lo, hi = (int(x) for x in pg.split("-")[:2])
            return (hi - lo) >= 3, None
        except Exception:
            return True, None
    return True, None

def collect():
    """Возвращает (rows, source_reports). source_reports — для sources.yaml."""
    rows, reports = [], []
    for name, issns, typ, mode, note in JOURNALS:
        items, status = None, None
        used_issn = None
        for issn in issns:
            items, status = fetch(issn)
            time.sleep(1)                      # вежливо к Crossref
            if items:
                used_issn = issn; break
        rep = {"name": name, "category": "A", "mechanism": "Crossref /journals/{ISSN}/works",
               "issn": issns, "issn_used": used_issn, "note": note}
        if not items:
            rep["status"] = "FAILED"
            rep["reason"] = f"Crossref не отдал записи (last status={status}); уточнить ISSN"
            reports.append(rep); print(f"  [A] {name:42} FAILED ({status})")
            continue
        kept = 0
        for it in items:
            keep, _ = _survey_only(it, mode)
            if not keep:
                continue
            doi = it.get("DOI", "")
            subj = it.get("subject") or []
            rows.append({
                "title": (it.get("title") or ["—"])[0].strip(),
                "authors": _authors(it),
                "date": _pubdate(it),
                "source_name": name,
                "category": "A",
                "type": typ,
                "area": None,                         # классифицируется в build (title+subject)
                "url": f"https://doi.org/{doi}" if doi else None,
                "summary": ("; ".join(subj)[:200] or None),
                "notes": None,
                "_area_hint": " ".join(subj),         # подсказка классификатору
            })
            kept += 1
        rep["status"] = "OK"; rep["kept"] = kept; rep["raw"] = len(items)
        reports.append(rep); print(f"  [A] {name:42} OK kept={kept}/{len(items)} (issn {used_issn})")
    return rows, reports

if __name__ == "__main__":
    rows, reps = collect()
    print(f"\n[A] всего строк: {len(rows)}")

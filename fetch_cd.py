#!/usr/bin/env python3
"""Категории C (научпоп) и D (блоги живых математиков).
Ключевой урок пробинга: RSS отдаёт лишь последние 5-25 записей -> на год не хватает.
Поэтому основной механизм — WordPress REST (годовой охват с датами), RSS — резерв,
берём union(API, RSS) с дедупом. Битые/частичные источники честно помечаем."""

import requests, time, html, re
import feedparser
from config import FROM, UNTIL, HEADERS, in_window

def _clean(t):
    if not t: return None
    t = re.sub(r"<[^>]+>", "", t)
    return html.unescape(t).strip() or None

# --- D: блоги на wordpress.com -> public-api.wordpress.com (годовой охват) ---
WPCOM_BLOGS = [
    ("Terence Tao — What's New",     "terrytao.wordpress.com",           "теория чисел"),
    ("Gil Kalai — Combinatorics",    "gilkalai.wordpress.com",           "комбинаторика"),
    ("Timothy Gowers",               "gowers.wordpress.com",             None),
    ("John Baez — Azimuth",          "johncarlosbaez.wordpress.com",     "математическая физика"),
    ("Igor Pak",                     "igorpak.wordpress.com",            "комбинаторика"),
    ("Jordan Ellenberg — Quomodocumque", "quomodocumque.wordpress.com",  "теория чисел"),
    ("Persiflage (galoisrepresentations)", "galoisrepresentations.wordpress.com", "теория чисел"),
]

def fetch_wpcom(name, site, area):
    url = f"https://public-api.wordpress.com/rest/v1.1/sites/{site}/posts/"
    rows, page_handle, got = [], None, 0
    for _ in range(6):                    # до 600 постов, обычно хватает 1-2 стр
        params = {"after": f"{FROM}T00:00:00", "before": f"{UNTIL}T23:59:59",
                  "number": 100, "fields": "ID,title,date,URL,excerpt,author"}
        if page_handle: params["page_handle"] = page_handle
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=25)
            if r.status_code != 200: return rows, ("FAILED", f"status {r.status_code}")
            j = r.json()
        except Exception as e:
            return rows, ("FAILED", str(e))
        for p in j.get("posts", []):
            rows.append({
                "title": _clean(p.get("title")),
                "authors": (p.get("author") or {}).get("name"),
                "date": (p.get("date") or "")[:10] or None,
                "source_name": name, "category": "D", "type": "blog", "area": area,
                "url": p.get("URL"), "summary": (_clean(p.get("excerpt")) or "")[:220] or None,
                "notes": None,
            })
        page_handle = j.get("meta", {}).get("next_page")
        time.sleep(0.5)
        if not page_handle: break
    return rows, ("OK", f"{len(rows)} in window")

# --- D/C: источники только-RSS или Atom (частичный охват -> помечаем) --------
FEED_SOURCES = [
    # name, url, category, type, area, note_partial?
    ("Peter Woit — Not Even Wrong", "https://www.math.columbia.edu/~woit/wordpress/?feed=rss2", "D", "blog", "математическая физика", True),
    ("Scott Aaronson — Shtetl-Optimized", "https://scottaaronson.blog/?feed=rss2", "D", "blog", "computer science", True),
    ("n-Category Café",             "https://golem.ph.utexas.edu/category/atom10.xml", "D", "blog", "алгебра", False),
    ("plus.maths.org",              "https://plus.maths.org/content/rss.xml", "C", "popsci", None, True),
    ("AMS Feature Column",          "https://blogs.ams.org/featurecolumn/feed/", "C", "expository", None, False),
]

def fetch_feed(name, url, cat, typ, area, partial):
    try:
        r = requests.get(url, headers=HEADERS, timeout=25)
        d = feedparser.parse(r.content)
    except Exception as e:
        return [], ("FAILED", str(e))
    if not d.entries:
        return [], ("FAILED", f"no entries (status {getattr(r,'status_code','?')})")
    rows = []
    for e in d.entries:
        # дата
        dt = None
        for k in ("published_parsed", "updated_parsed"):
            if e.get(k):
                dt = time.strftime("%Y-%m-%d", e[k]); break
        if dt and not in_window(dt):
            continue
        auth = e.get("author") or (name.split("—")[0].strip())
        rows.append({
            "title": _clean(e.get("title")),
            "authors": auth,
            "date": dt,
            "source_name": name, "category": cat, "type": typ, "area": area,
            "url": e.get("link"),
            "summary": (_clean(e.get("summary")) or "")[:220] or None,
            "notes": ("частичный охват: только RSS (нет годового API)" if partial else None),
        })
    tag = "OK" if not partial else "OK_PARTIAL"
    return rows, (tag, f"{len(rows)} in window (RSS truncates!)" if partial else f"{len(rows)} in window")

def collect():
    rows, reports = [], []
    for name, site, area in WPCOM_BLOGS:
        rs, (st, msg) = fetch_wpcom(name, site, area)
        rows += rs
        reports.append({"name": name, "category": "D", "mechanism": "public-api.wordpress.com/rest/v1.1",
                        "url": f"https://public-api.wordpress.com/rest/v1.1/sites/{site}/posts/",
                        "status": st, "kept": len(rs), "reason": None if st=="OK" else msg})
        print(f"  [D] {name:38} {st} n={len(rs)}")
    for name, url, cat, typ, area, partial in FEED_SOURCES:
        rs, (st, msg) = fetch_feed(name, url, cat, typ, area, partial)
        rows += rs
        reports.append({"name": name, "category": cat, "mechanism": "RSS/Atom (feedparser)",
                        "url": url, "status": st, "kept": len(rs),
                        "reason": (msg if st.startswith("FAILED") else ("частичный охват (RSS)" if partial else None))})
        print(f"  [{cat}] {name:38} {st} n={len(rs)}")
        time.sleep(0.5)
    return rows, reports

if __name__ == "__main__":
    rows, reps = collect()
    print(f"\n[C/D] всего строк: {len(rows)}")

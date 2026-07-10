#!/usr/bin/env python3
"""Категория E — YouTube мат-каналы через RSS videos.xml?channel_id=.
Оговорка: YouTube-RSS отдаёт лишь ~15 последних роликов -> для частых каналов
(Numberphile/Veritasium) охват частичный; помечаем. Veritasium — общий научпоп,
фильтруем по мат-ключам в заголовке."""

import requests, time
import feedparser
from config import HEADERS, in_window

CHANNELS = [
    # name, channel_id, math_only_filter?, area
    ("3Blue1Brown",  "UCYO_jab_esuFRV4b17AJtAw", False, None),
    ("Numberphile",  "UCoxcjq-8xIDTYp3uz647V5A", False, None),
    ("Mathologer",   "UC1_uAIS3r8Vu6JjXWvastJg", False, None),
    ("Veritasium",   "UCHnyfMqiRRG1u-2MsSQLbXA", True,  None),   # общий научпоп -> math-фильтр
    ("Quanta Magazine (YouTube)", "UCTpmmkp1E4nmZqWPS-dl5bg", True, None),
]

MATH = ("math","prime","number","geometr","topolog","infinit","theorem","proof","equation",
        "calculus","algebra","pi ","dimension","fractal","paradox","probabil","graph")

def _is_math(title):
    t = (title or "").lower()
    return any(k in t for k in MATH)

def collect():
    rows, reports = [], []
    for name, cid, filt, area in CHANNELS:
        url = f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
        try:
            r = requests.get(url, headers=HEADERS, timeout=25)
            d = feedparser.parse(r.content)
        except Exception as e:
            reports.append({"name": name, "category": "E", "mechanism": "YouTube RSS",
                            "url": url, "status": "FAILED", "kept": 0, "reason": str(e)})
            print(f"  [E-YT] {name:30} FAILED {e}"); continue
        if not d.entries:
            reports.append({"name": name, "category": "E", "mechanism": "YouTube RSS",
                            "url": url, "status": "FAILED", "kept": 0,
                            "reason": f"нет записей (channel_id неверен?) status {r.status_code}"})
            print(f"  [E-YT] {name:30} FAILED no entries"); continue
        ch_title = d.feed.get("title", "?")
        n = 0
        for e in d.entries:
            dt = time.strftime("%Y-%m-%d", e.published_parsed) if e.get("published_parsed") else None
            if dt and not in_window(dt):
                continue
            if filt and not _is_math(e.get("title")):
                continue
            rows.append({
                "title": e.get("title"), "authors": name, "date": dt,
                "source_name": f"YouTube · {name}", "category": "E", "type": "video",
                "area": area, "url": e.get("link"),
                "summary": None,
                "notes": "YouTube-RSS усечён (~15 последних роликов) — частичный охват",
            })
            n += 1
        reports.append({"name": name, "category": "E", "mechanism": "YouTube RSS videos.xml",
                        "url": url, "status": "OK_PARTIAL", "kept": n,
                        "reason": f"channel='{ch_title}'; RSS усечён ~15 роликов"})
        print(f"  [E-YT] {name:30} OK n={n} (channel='{ch_title}')")
        time.sleep(0.5)
    return rows, reports

if __name__ == "__main__":
    rows, reps = collect()
    print(f"\n[E-YT] всего строк: {len(rows)}")

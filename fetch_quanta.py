#!/usr/bin/env python3
"""Категория C — Quanta Magazine. Механизм: wp/v2 REST на api.quantamagazine.org
(годовой охват ~170 постов всех тем), затем math-фильтр через классификатор разделов.
Endpoint капризный -> экспоненциальный backoff; при полном отказе — RSS-резерв
(math-tag feed, но он усечён -> помечаем частичный охват). Потолок доли — метрика отчёта."""

import requests, time, html, re
import feedparser
from config import FROM, UNTIL, HEADERS, in_window
from score import classify_area

def _clean(t):
    if not t: return None
    t = re.sub(r"<[^>]+>", "", t)
    return html.unescape(t).strip() or None

MATH_SIGNAL = r"math|prime|theorem|conjecture|proof|geometr|topolog|number theor|algebra|combinator|graph|equation|dimension|infinit|knot|manifold|curve|symmetr|randomness|probabil"

def _is_math(title, excerpt):
    txt = f"{title} {excerpt or ''}"
    area = classify_area(txt)
    if area and area not in ("computer science", "статистика", "математическая биология"):
        return True, area          # чистая математика
    if re.search(MATH_SIGNAL, txt.lower()):
        return True, (area or None)  # смежное, где всплывает серьёзная математика
    return False, area

# api.* хост блокируется Cloudflare при частых запросах; фронт www + браузерный UA стабилен
QUA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/126.0 Safari/537.36", "Accept": "application/json"}

def fetch_wp():
    """wp/v2/posts постранично с backoff. Возвращает (rows|None, note)."""
    base = "https://www.quantamagazine.org/wp-json/wp/v2/posts"
    all_posts, page = [], 1
    while page <= 5:
        params = {"after": f"{FROM}T00:00:00", "before": f"{UNTIL}T23:59:59",
                  "per_page": 100, "page": page, "_fields": "title,date,link,excerpt"}
        ok = False
        for attempt in range(4):
            try:
                r = requests.get(base, params=params, headers=QUA, timeout=30)
            except Exception:
                time.sleep(2**attempt); continue
            if "json" in r.headers.get("content-type", "").lower() and r.status_code == 200:
                ok = True; break
            time.sleep(2**attempt)         # backoff, не слепой ретрай
        if not ok:
            return (all_posts or None), f"wp/v2 отказал на стр.{page} (после backoff)"
        batch = r.json()
        if not batch: break
        all_posts += batch
        if len(batch) < 100: break
        page += 1; time.sleep(1)
    return all_posts, f"wp/v2 OK ({len(all_posts)} постов всех тем)"

def rss_fallback():
    rows = []
    for url in ("https://www.quantamagazine.org/tag/mathematics/feed/",
                "https://api.quantamagazine.org/feed/"):
        try:
            d = feedparser.parse(requests.get(url, headers=HEADERS, timeout=20).content)
        except Exception:
            continue
        for e in d.entries:
            dt = time.strftime("%Y-%m-%d", e.published_parsed) if e.get("published_parsed") else None
            rows.append({"title": _clean(e.get("title")), "authors": "Quanta Magazine",
                         "date": dt, "url": e.get("link"),
                         "excerpt": _clean(e.get("summary"))})
    # dedup by url
    seen, out = set(), []
    for r in rows:
        if r["url"] in seen: continue
        seen.add(r["url"]); out.append(r)
    return out

def collect():
    posts, note = fetch_wp()
    mechanism = "api.quantamagazine.org/wp/v2/posts + math-фильтр"
    status = "OK"
    if not posts:
        raw = rss_fallback()
        mechanism = "RSS math-tag (wp/v2 недоступен) — ЧАСТИЧНЫЙ охват"
        status = "OK_PARTIAL"
        posts = [{"title": r["title"], "date": r["date"], "link": r["url"],
                  "excerpt": {"rendered": r["excerpt"] or ""}} for r in raw]
        note = f"{note}; RSS-резерв дал {len(posts)} записей (усечён)"
    rows = []
    for p in posts:
        title = _clean(p.get("title", {}).get("rendered") if isinstance(p.get("title"), dict) else p.get("title"))
        exc = p.get("excerpt", {})
        exc = _clean(exc.get("rendered") if isinstance(exc, dict) else exc)
        date = (p.get("date") or "")[:10] or None
        if date and not in_window(date):
            continue
        ok, area = _is_math(title or "", exc)
        if not ok:
            continue
        rows.append({
            "title": title, "authors": "Quanta Magazine", "date": date,
            "source_name": "Quanta Magazine", "category": "C", "type": "popsci",
            "area": area, "url": p.get("link"),
            "summary": (exc or "")[:220] or None,
            "notes": ("math-tag RSS (частичный охват)" if status=="OK_PARTIAL" else None),
        })
    report = {"name": "Quanta Magazine", "category": "C", "mechanism": mechanism,
              "url": "https://api.quantamagazine.org/wp/v2/posts", "status": status,
              "kept": len(rows), "reason": note}
    print(f"  [C] Quanta Magazine  {status}  math={len(rows)}  | {note}")
    return rows, [report]

if __name__ == "__main__":
    rows, rep = collect()
    print(f"[C] Quanta math строк: {len(rows)}")
    from collections import Counter
    print("areas:", Counter(r["area"] for r in rows))

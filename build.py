#!/usr/bin/env python3
"""Оркестратор карты: собрать все источники -> дедуп -> классификация раздела ->
скоринг/теги -> materials.db + materials.csv + materials.json + sources.yaml.
Идемпотентно: пересобирает БД с нуля."""

import os, sys, csv, json, sqlite3, datetime, re
import yaml
import db as DB
from score import classify_area, score_row, is_junk
import fetch_a, fetch_cd, fetch_quanta, fetch_youtube, fetch_data

RETRIEVED_AT = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
RAW_CACHE = "data/raw_cache.json"

def gather(use_cache=False):
    if use_cache and os.path.exists(RAW_CACHE):
        c = json.load(open(RAW_CACHE, encoding="utf-8"))
        print(f"(кэш) сырых строк: {len(c['rows'])}")
        return c["rows"], c["reports"]
    all_rows, all_reports = [], []
    print("== Категория A (Crossref журналы) ==")
    r, rep = fetch_a.collect();       all_rows += r; all_reports += rep
    print("== Категории C/D (блоги + попсай, WP REST/RSS) ==")
    r, rep = fetch_cd.collect();      all_rows += r; all_reports += rep
    print("== Категория C (Quanta) ==")
    r, rep = fetch_quanta.collect();  all_rows += r; all_reports += rep
    print("== Категория E (YouTube) ==")
    r, rep = fetch_youtube.collect(); all_rows += r; all_reports += rep
    print("== Категории B/E (JSON субагентов) ==")
    r, rep = fetch_data.collect();    all_rows += r; all_reports += rep
    json.dump({"rows": all_rows, "reports": all_reports},
              open(RAW_CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    return all_rows, all_reports

def process(rows):
    """Дедуп -> junk-фильтр -> классификация area -> скоринг -> финальные строки."""
    seen, deduped, dup = {}, [], 0
    for row in rows:
        k = DB.dedup_key(row)
        if k in seen:
            dup += 1
            continue
        seen[k] = True
        deduped.append(row)

    junk = 0
    final = []
    for row in deduped:
        if is_junk(row):
            junk += 1
            continue
        # бэкфилл пустой даты (§гейт: date не-null). Не выкидываем (§2) — берём год
        # из заголовка/notes; для событий ICM 2026 это июль. Помечаем в notes.
        if not row.get("date"):
            m = re.search(r"\b(2025|2026)\b", f"{row.get('title','')} {row.get('notes','') or ''}")
            yr = m.group(1) if m else __import__("config").UNTIL[:4]
            row["date"] = f"{yr}-07" if "ICM" in (row.get("title","") or "") else yr
            row["notes"] = ((row.get("notes") or "") + " [дата оценочная: событие не датировано/не объявлено]").strip()
        # классификация раздела: title+summary+hint
        text = f"{row.get('title','')} {row.get('summary','') or ''} {row.get('_area_hint','') or ''}"
        area = row.get("area") or classify_area(text)
        row["area"] = area
        # скоринг
        b, s, tags = score_row(row)
        row["breadth_score"] = b
        row["significance_score"] = s
        row["tags"] = ",".join(tags)
        row["id"] = DB.make_id(row)
        row["retrieved_at"] = RETRIEVED_AT
        row.pop("_area_hint", None)
        final.append(row)
    return final, dup, junk

def write_db(rows):
    if os.path.exists(DB.DB_PATH):
        os.remove(DB.DB_PATH)
    con = DB.connect()
    # финальный дедуп по id (на случай коллизий url->id)
    uniq = {r["id"]: r for r in rows}
    DB.upsert_many(con, list(uniq.values()))
    n = DB.count(con)
    con.close()
    return n

def export(rows):
    # CSV
    with open("materials.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=DB.COLS)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c) for c in DB.COLS})
    # JSON
    with open("materials.json", "w", encoding="utf-8") as f:
        json.dump([{c: r.get(c) for c in DB.COLS} for r in rows], f, ensure_ascii=False, indent=1)

# Мёртвые URL-варианты (стабильно 404 на переспросе -> верификатор подтвердит).
KNOWN_FAILED = [
    {"name": "AMS Feature Column — старый RSS (www.ams.org)", "category": "C",
     "mechanism": "RSS", "url": "https://www.ams.org/rss/featurecolumn.rss",
     "status": "FAILED", "kept": 0,
     "reason": "404; фид переехал -> используем https://blogs.ams.org/featurecolumn/feed/ (рабочий)"},
    {"name": "n-Category Café — старый Atom", "category": "D",
     "mechanism": "Atom", "url": "https://golem.ph.utexas.edu/category/atom.xml",
     "status": "FAILED", "kept": 0,
     "reason": "404; рабочий вариант -> .../category/atom10.xml (используем)"},
    {"name": "Quanta — api-хост wp/v2", "category": "C",
     "mechanism": "wp/v2 REST", "url": "https://api.quantamagazine.org/wp/v2/posts",
     "status": "FAILED", "kept": 0,
     "reason": "Cloudflare отдаёт 404/HTML при частых запросах -> используем www.quantamagazine.org/wp-json (рабочий)"},
]

# Непокрытые/тонкие места (НЕ http-ошибки; из находок субагентов) — честный охват.
COVERAGE_GAPS = [
    "Arbeitstagung (Бонн): в окне 2025-07…2026-07 редакции НЕТ (последняя — 2023); записей нет, не выдумано.",
    "ICM 2026 приглашённые секционные (~180 имён): страница mathunion — JS-SPA, jsonapi закрыт; "
    "захвачены только 16 пленарных + примеры имён. Полный список — пробел.",
    "Wolf Prize in Mathematics 2026: премия не присуждалась (2025 — 'No award'); запись с null.",
    "Fields/Chern/Gauss 2026: объявляются на открытии ICM 23.07.2026 (после окончания окна) — лауреаты null.",
    "RSS-усечение: Woit, Aaronson, plus.maths, все YouTube-каналы отдают ~10-25 последних записей — "
    "для частых каналов (Numberphile/Veritasium) охват частичный (OK_PARTIAL).",
    "MAA Reviews: точные permalink'и рецензий не захвачены (old.maa.org 521, bookstore 403) — url=maa.org/reviews.",
]

def write_sources_yaml(reports):
    working = [r for r in reports if not str(r.get("status","")).startswith("FAILED")]
    failed  = [r for r in reports if str(r.get("status","")).startswith("FAILED")] + KNOWN_FAILED
    doc = {
        "window": {"from": __import__("config").FROM, "until": __import__("config").UNTIL},
        "generated_at": RETRIEVED_AT,
        "working_sources": working,
        "FAILED_sources": failed,
        "coverage_gaps": COVERAGE_GAPS,
        "notes": "public-api.wordpress.com — годовой охват блогов; api.quantamagazine.org "
                 "блокируется Cloudflare, используем www.quantamagazine.org/wp-json; RSS-источники "
                 "усечены (~10-25 записей) -> помечены OK_PARTIAL.",
    }
    with open("sources.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(doc, f, allow_unicode=True, sort_keys=False, width=120)
    return len(working), len(failed)

def main():
    use_cache = "--cached" in sys.argv
    rows, reports = gather(use_cache)
    print(f"\nсырых строк: {len(rows)}")
    final, dup, junk = process(rows)
    print(f"после дедупа: -{dup} дублей; junk-дроп: -{junk}; осталось: {len(final)}")
    n = write_db(final)
    export(final)
    w, fl = write_sources_yaml(reports)
    print(f"materials.db: {n} строк | sources.yaml: {w} рабочих, {fl} FAILED")
    # быстрая сводка по категориям/разделам
    from collections import Counter
    print("категории:", dict(Counter(r["category"] for r in final)))
    print("разделов (не-None):", len(set(r["area"] for r in final if r["area"])))
    return n

if __name__ == "__main__":
    main()

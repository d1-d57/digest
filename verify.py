#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Независимый верификатор «карты года» MATEMDIGEST.
НЕ доверяет числам из report.md — считает всё прямым SQL к materials.db,
затем парсит заявленные числа регуляркой и сверяет. Плюс резолвит URL по сети.
Ничего не правит: только читает materials.db / report.md / sources.yaml.
"""
import os, re, sqlite3, random, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
DB   = os.path.join(ROOT, "materials.db")
RMD  = os.path.join(ROOT, "report.md")
YAML = os.path.join(ROOT, "sources.yaml")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

discrepancies = []   # ИТОГОВЫЙ список расхождений

def q(sql):
    con = sqlite3.connect(DB); con.row_factory = sqlite3.Row
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()

def one(sql):
    return q(sql)[0][0]

# ----------------------------------------------------------------------------
# (a) Числа отчёта == БД
# ----------------------------------------------------------------------------
print("=" * 72)
print("(a) СВЕРКА ЧИСЕЛ: БД  vs  report.md")
print("=" * 72)

total_db   = one("SELECT COUNT(*) FROM materials")
cats_db    = {r[0]: r[1] for r in q("SELECT category,COUNT(*) FROM materials GROUP BY category")}
areas_db   = one("SELECT COUNT(DISTINCT area) FROM materials WHERE area IS NOT NULL AND area!=''")
quanta_n   = one("SELECT COUNT(*) FROM materials WHERE tags LIKE '%is_quanta%'")
quanta_pct_db = round(100.0 * quanta_n / total_db, 1)
breadth3_db = one("SELECT COUNT(*) FROM materials WHERE breadth_score>=3")

report = open(RMD, encoding="utf-8").read()

def grab(pattern, default=None):
    m = re.search(pattern, report, re.MULTILINE)
    return m.group(1) if m else default

total_rep = grab(r"Всего материалов[^:\d]*:\s*\*{0,2}(\d+)")
cats_rep = {}
for c in "ABCDE":
    cats_rep[c] = grab(rf"^-\s*{c}\s*[·].*?:\s*\*{{0,2}}(\d+)")
areas_rep  = grab(r"По разделам математики\s*\((\d+)\s*определ")
quanta_rep = grab(r"доля Quanta:\s*\*{0,2}([\d.]+)%")
breadth_rep = grab(r"breadth_score\s*≥\s*3[^:]*:\s*\*{0,2}(\d+)")

rows = []
def cmp(metric, db_val, rep_val, discr_label=None):
    ok = str(db_val) == str(rep_val)
    rows.append((metric, db_val, rep_val, ok))
    if not ok:
        discrepancies.append(discr_label or f"(a) {metric}: БД={db_val}, report={rep_val}")

cmp("Всего материалов", total_db, total_rep)
for c in "ABCDE":
    cmp(f"Категория {c}", cats_db.get(c, 0), cats_rep.get(c))
cmp("Различных area (>=1)", areas_db, areas_rep)
cmp("Доля Quanta, %", f"{quanta_pct_db:.1f}", quanta_rep)
cmp("breadth_score >= 3", breadth3_db, breadth_rep)

w = max(len(r[0]) for r in rows)
print(f"{'метрика'.ljust(w)} | {'БД':>8} | {'report':>8} | совпало")
print("-" * (w + 30))
for m, d, r_, ok in rows:
    print(f"{m.ljust(w)} | {str(d):>8} | {str(r_):>8} | {'OK' if ok else 'РАСХОЖДЕНИЕ'}")

# ----------------------------------------------------------------------------
# (b) Гейт обязательных полей
# ----------------------------------------------------------------------------
print("\n" + "=" * 72)
print("(b) ГЕЙТ ОБЯЗАТЕЛЬНЫХ ПОЛЕЙ")
print("=" * 72)

def gate(label, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{('  — ' + detail) if detail else ''}")
    if not ok:
        discrepancies.append(f"(b) {label} — {detail}")

for col in ["title", "date", "source_name", "category", "url", "breadth_score"]:
    n = one(f"SELECT COUNT(*) FROM materials WHERE {col} IS NULL OR {col}=''")
    gate(f"нет NULL/'' в {col}", n == 0, f"найдено {n}")

gate("всего строк >= 250", total_db >= 250, f"строк={total_db}")
empty_cats = [c for c in "ABCDE" if cats_db.get(c, 0) == 0]
gate("все 5 категорий непусты", not empty_cats, f"пустые: {empty_cats}")
gate("различных area >= 10", areas_db >= 10, f"area={areas_db}")

# ----------------------------------------------------------------------------
# сеть
# ----------------------------------------------------------------------------
import requests
try:
    import urllib3
    urllib3.disable_warnings()
except Exception:
    pass

def resolve(url, timeout=25):
    """Возвращает (ok, code, final_url, note)."""
    headers = {"User-Agent": UA, "Accept": "*/*"}
    try:
        r = requests.get(url, headers=headers, timeout=timeout,
                         allow_redirects=True, verify=False, stream=True)
        code = r.status_code
        final = r.url
        note = ""
        if code == 403:
            note = "403 (антибот, не мёртвая)"
        try:
            r.close()
        except Exception:
            pass
        return (code == 200, code, final, note)
    except Exception as e:
        return (False, None, url, type(e).__name__)

# ----------------------------------------------------------------------------
# (c) Резолв 15 случайных URL
# ----------------------------------------------------------------------------
print("\n" + "=" * 72)
print("(c) РЕЗОЛВ 15 СЛУЧАЙНЫХ URL")
print("=" * 72)

urls = [r[0] for r in q("SELECT url FROM materials ORDER BY RANDOM() LIMIT 15")]
ok_c = 0
problems_c = []
for u in urls:
    ok, code, final, note = resolve(u)
    if ok:
        ok_c += 1
    else:
        problems_c.append((u, code, note))
    flag = "OK" if ok else "FAIL"
    print(f"  [{flag}] {str(code):>4} {note:22} {u[:80]}")

print(f"\n  Резолвится: {ok_c}/15")
if ok_c < 13:
    # 403 антибот считаем отдельно, не как «мёртвую»
    hard = [p for p in problems_c if p[1] != 403]
    discrepancies.append(f"(c) резолв {ok_c}/15 (<13). Проблемные: " +
                         "; ".join(f"{c} {u[:60]}" for u, c, n in problems_c))
    print("  ПРОБЛЕМА: < 13/15")
    for u, c, n in problems_c:
        print(f"    - {c} {n} {u}")
else:
    print("  OK (>=13/15)")
    if problems_c:
        print("  (не-резолвнутые, но порог пройден):")
        for u, c, n in problems_c:
            print(f"    - {c} {n} {u}")

# ----------------------------------------------------------------------------
# (d) FAILED реально ошибаются
# ----------------------------------------------------------------------------
print("\n" + "=" * 72)
print("(d) FAILED_sources РЕАЛЬНО ОШИБАЮТСЯ")
print("=" * 72)

# простой парсер FAILED-блока (без PyYAML — его может не быть)
ytxt = open(YAML, encoding="utf-8").read()
failed_block = ytxt.split("FAILED_sources:", 1)[1].split("coverage_gaps:", 1)[0]
# разбить на элементы по "- name:"
items = re.split(r"\n- name:", failed_block)
failed = []
for it in items:
    if "url:" not in it:
        continue
    name = re.search(r"^\s*(.+)", it)
    url  = re.search(r"url:\s*(\S+)", it)
    if url:
        failed.append((name.group(1).strip() if name else "?", url.group(1).strip()))

for name, url in failed:
    ok, code, final, note = resolve(url)
    # проверим тип контента для 200-ответов
    content_kind = ""
    is_false_failed = False
    if ok:
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=25,
                             verify=False)
            ct = r.headers.get("Content-Type", "")
            body = r.text[:400]
            looks_json = "json" in ct.lower() or body.lstrip().startswith(("[", "{"))
            has_items = looks_json and len(r.text) > 50 and r.text.strip() not in ("[]", "{}")
            content_kind = f"CT={ct.split(';')[0]}"
            if has_items:
                is_false_failed = True
        except Exception as e:
            content_kind = f"err:{type(e).__name__}"
    verdict = ("ЛОЖНЫЙ FAILED (200+валидный контент!)" if is_false_failed
               else "подтверждён как ошибающийся")
    print(f"  [{code}] {verdict}")
    print(f"        {name}")
    print(f"        {url}  {content_kind}")
    if is_false_failed:
        discrepancies.append(f"(d) ложный FAILED: {name} -> {url} отвечает 200 валидным контентом")

# ----------------------------------------------------------------------------
# ИТОГ
# ----------------------------------------------------------------------------
print("\n" + "=" * 72)
print("ИТОГ: СПИСОК РАСХОЖДЕНИЙ")
print("=" * 72)
if discrepancies:
    for i, d in enumerate(discrepancies, 1):
        print(f"  {i}. {d}")
    print("\nВЕРИФИКАЦИЯ НЕ ПРОЙДЕНА")
    sys.exit(1)
else:
    print("  (пусто)")
    print("\nВЕРИФИКАЦИЯ ПРОЙДЕНА")

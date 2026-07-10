#!/usr/bin/env python3
"""Загрузчик структурированного JSON от разведочных субагентов (категории B и E).
Файлы: data/b_venues.json (B), data/e_prizes.json (E), data/e_people.json (E)."""

import json, os

SPECS = [
    ("data/b_venues.json", "B", None,     "Séminaire Bourbaki / ICM 2026 / JMM CEB / Takagi (скрейп, субагент)"),
    ("data/e_prizes.json", "E", "prize",  "Премии (Abel/Fields/Breakthrough/... — субагент)"),
    ("data/e_people.json", "E", None,     "Книги/юбилеи/интервью (субагент)"),
]

def collect():
    rows, reports = [], []
    for path, cat, force_type, desc in SPECS:
        if not os.path.exists(path):
            reports.append({"name": desc, "category": cat, "mechanism": "субагент → JSON",
                            "url": path, "status": "FAILED", "kept": 0,
                            "reason": "файл субагента отсутствует"})
            print(f"  [{cat}] {path:24} FAILED (нет файла)"); continue
        data = json.load(open(path, encoding="utf-8"))
        n = 0
        for r in data:
            rows.append({
                "title": r.get("title"),
                "authors": r.get("authors"),
                "date": (r.get("date") or None),
                "source_name": r.get("source_name") or desc,
                "category": cat,
                "type": force_type or r.get("type") or "expository",
                "area": None,                       # переклассифицируем; hint ниже
                "url": r.get("url"),
                "summary": r.get("summary"),
                "notes": r.get("notes"),
                "_area_hint": r.get("area") or "",
            })
            n += 1
        reports.append({"name": desc, "category": cat, "mechanism": "субагент → JSON (скрейп/поиск)",
                        "url": path, "status": "OK", "kept": n, "reason": None})
        print(f"  [{cat}] {path:24} OK n={n}")
    return rows, reports

if __name__ == "__main__":
    rows, reps = collect()
    print(f"\n[JSON] всего строк: {len(rows)}")

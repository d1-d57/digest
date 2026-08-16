#!/usr/bin/env python3
"""ЗАХОД-7 Направление A — дозор журнального слоя, окно 2026-06-15..2026-07-16.
Одноразовый скрипт. Переиспользует fetch(), _authors(), _pubdate(), _survey_only(), JOURNALS из fetch_a.py.
НЕ трогает config.FROM/UNTIL — локальное окно ниже.
"""
import json, time, re, sys
from fetch_a import fetch, _authors, _pubdate, _survey_only, JOURNALS
from config import MAILTO, HEADERS

FROM = "2026-06-15"
UNTIL = "2026-07-16"

def fetch_window(issn):
    import requests
    url = f"https://api.crossref.org/journals/{issn}/works"
    params = {"filter": f"from-pub-date:{FROM},until-pub-date:{UNTIL},type:journal-article",
              "select": "title,author,published,DOI,volume,issue,page,subject,abstract",
              "rows": 500, "mailto": MAILTO}
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=30)
        if r.status_code != 200:
            return None, r.status_code
        return r.json().get("message", {}).get("items", []), 200
    except requests.RequestException as e:
        return None, str(e)

def main():
    all_rows = []
    per_journal = {}
    errors = []
    for name, issns, typ, mode, note in JOURNALS:
        items, status, used_issn = None, None, None
        last_status = None
        for issn in issns:
            items, status = fetch_window(issn)
            last_status = status
            time.sleep(1)
            if status == 429 or (isinstance(status, str) and "429" in status):
                break
            if items is not None:
                used_issn = issn
                if items:
                    break
        if status == 429 or (isinstance(status, str) and "429" in status):
            errors.append(f"{name}: RATE LIMIT (429)")
            print(f"[RATE LIMIT] {name} — stopping per instructions")
            per_journal[name] = {"found": 0, "status": "429"}
            continue
        if items is None:
            per_journal[name] = {"found": 0, "status": f"FAILED({last_status})"}
            print(f"[A-dozor] {name:42} FAILED ({last_status})")
            continue
        if not items:
            per_journal[name] = {"found": 0, "status": "OK-empty", "issn_used": used_issn}
            print(f"[A-dozor] {name:42} OK, 0 статей в окне (issn {used_issn})")
            continue
        kept_items = []
        for it in items:
            # Notices: skip the page-length filter per instructions — take all
            if name == "Notices of the AMS":
                keep = True
            else:
                keep, _ = _survey_only(it, mode)
            if not keep:
                continue
            kept_items.append(it)
        per_journal[name] = {"found": len(kept_items), "raw": len(items), "issn_used": used_issn}
        print(f"[A-dozor] {name:42} raw={len(items)} kept={len(kept_items)} (issn {used_issn})")
        for it in kept_items:
            doi = it.get("DOI", "")
            subj = it.get("subject") or []
            abstract = it.get("abstract") or ""
            all_rows.append({
                "title": (it.get("title") or ["—"])[0].strip(),
                "authors": _authors(it),
                "date": _pubdate(it),
                "source_name": name,
                "type": typ,
                "url": f"https://doi.org/{doi}" if doi else None,
                "subject": "; ".join(subj),
                "abstract": abstract,
            })

    with open("dozor_a_candidates.json", "w") as f:
        json.dump({"rows": all_rows, "per_journal": per_journal, "errors": errors}, f, ensure_ascii=False, indent=2)
    print(f"\n[A-dozor] всего кандидатов (до дедупа): {len(all_rows)}")
    if errors:
        print("ERRORS:", errors)

if __name__ == "__main__":
    main()

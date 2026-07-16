#!/usr/bin/env python3
"""ZAHOD-5 · пробник mathnet.ru.  СРАБОТАВШИЙ РЫЧАГ: №3 — Wayback (web.archive.org).

ПОЧЕМУ ИМЕННО ЭТОТ РЫЧАГ (разведка 12.07.2026, перепроверено 16.07.2026; машина владельца, сеть открыта):

  Рычаг 1 — requests + config.HEADERS + Accept-Language: ru  →  ПРОВАЛ НА ТРАНСПОРТЕ.
      www.mathnet.ru = CNAME -> mathnet.ru -> единственный A-адрес 185.129.147.147.
      * порт 443: TCP-хендшейк НЕ завершается (curl connect=0.000000 при --max-time 12/30/45);
        один раз из многих connect прошёл за 0.61 с, но TLS (appconnect) так и не состоялся;
        через requests — ReadTimeout 8/8 попыток, один раз SSLEOFError.
      * порт 80: мгновенный RST («Connection refused» за 43 мс) — т.е. хост ОТВЕЧАЕТ.
      * ICMP: ping 3/3, 0% потерь, RTT ~58 мс — хост жив, пакеты доходят.
      * контроли в тот же момент: api.crossref.org → HTTP 200 (28 КБ), web.archive.org → HTTP 200
        (145 КБ). Значит интернет исправен, фильтрует сторона mathnet, а не наша сеть.
      ВЫВОД, ОПРОВЕРГАЮЩИЙ ИСХОДНУЮ ПРЕДПОСЫЛКУ ЗАХОДА: НИКАКОЙ КАПЧИ НЕТ. До HTTP-слоя дело
      не доходит вовсе — SYN на 443 избирательно гасится анти-DDoS-фронтом. Браузерный UA,
      полный набор заголовков и Accept-Language роли не играют: они отправляются уже ПОСЛЕ
      TCP+TLS, которых нет. «Открытая сеть у владельца» тут не лечит.

  Рычаг 2 — OAI-PMH / Math-Net API  →  ПРОВАЛ ПО ТОЙ ЖЕ ПРИЧИНЕ (тот же хост = та же стена).
      /php/oai.phtml?verb=Identify и /oai?verb=Identify — оба connect=0.000000.
      Сам эндпоинт даже не разведать: robots.txt и sitemap с живого хоста не читаются.

  Рычаг 3 — Wayback  →  РАБОТАЕТ. web.archive.org отдаёт архивные копии mathnet:
      /web/<timestamp>id_/<url>  ('id_' = оригинальные байты, без тулбара и переписывания ссылок).
      ЦЕНА РЫЧАГА: свежесть = свежесть архива, не «сегодня» (см. snapshot-метки ниже).

ВОСПРОИЗВОДИМОСТЬ: снапшоты ЗАКРЕПЛЕНЫ константами ниже — повторный прогон даёт те же записи.
  Обновить выемку = найти свежий снапшот через CDX и заменить timestamp, напр.:
  curl -G 'https://web.archive.org/cdx/search/cdx' --data-urlencode 'url=<URL>' \
       --data-urlencode 'output=json' --data-urlencode 'filter=statuscode:200' --data-urlencode 'limit=-1'
  ВНИМАНИЕ: часть захватов есть в индексе CDX (statuscode 200), но НЕ проигрывается (плейбек
  отдаёт 404 внутри 142-КБ html-страницы Wayback). Поэтому проверка контента ниже обязательна.

ГРАНИЦЫ: скрипт только ЧИТАЕТ архив и пишет в data/mathnet_probe/. В materials.db и sources*.yaml
  не пишет ничего — это отдельные заходы.

Запуск:  python3 probe_mathnet.py
"""

import warnings; warnings.filterwarnings("ignore")
import argparse, json, os, re, sys, time

import requests
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from config import HEADERS                      # §0: переиспользуем готовые заголовки проекта

OUT = os.path.join(ROOT, "data", "mathnet_probe")
RAW = os.path.join(OUT, "raw")

H = dict(HEADERS)
H["Accept-Language"] = "ru,en;q=0.8"            # §3: как велено рычагом 1

PAUSE = 2.0                                     # §2: вежливость к web.archive.org (≥1–2 с)

# --- закреплённые снапшоты (найдены через CDX; проверены на проигрываемость) ------------------
# ZAHOD-6: конф408 «Коллоквиум МИАН» мёртв с 2023 — перенацелено на живой confid=142
# «Математика и её приложения» (аналитик ЗАХОД-6, проверено CDX 16.07.2026).
COLLOQ = ("colloquium_conf142", "20251114111128",
          "https://www.mathnet.ru/php/conference.phtml?option_lang=rus&eventID=9&confid=142")
UMN_ISSUE = ("umn_currentissue", "20260114101928",
             "https://www.mathnet.ru/php/currentissue.phtml?jrnid=rm&option_lang=rus")
UMN_PAPER = ("umn_paper_10293", "20251204010148",
             "https://www.mathnet.ru/php/archive.phtml?wshow=paper&jrnid=rm&paperid=10293&option_lang=rus")

MONTHS = {"января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
          "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12}


def norm(s):
    """NBSP и мусорные пробелы -> обычный текст."""
    return re.sub(r"\s+", " ", (s or "").replace("\xa0", " ")).strip()


def wb_get(timestamp, original, tries=5):
    """Тянем архивную копию. archive.org капризен (ловили 503 и read-timeout) -> backoff."""
    url = f"https://web.archive.org/web/{timestamp}id_/{original}"
    for k in range(tries):
        try:
            r = requests.get(url, headers=H, timeout=(20, 120))
            if r.status_code in (429, 502, 503, 504):
                print(f"      archive.org {r.status_code} -> backoff"); time.sleep(6 * (k + 1)); continue
            # mathnet отдаёт windows-1251
            return r, r.content.decode("windows-1251", errors="replace")
        except requests.RequestException as e:
            print(f"      {type(e).__name__} -> backoff"); time.sleep(6 * (k + 1))
    return None, None


def live_get(original, tries=3):
    """ZAHOD-6 §3-Г: прямой ход в mathnet вместо Wayback. Транспорт НЕ проверен —
    ЗАХОД-5 установил, что 443/mathnet.ru глушится анти-DDoS-стеной под тем же VPN,
    из-под которого работает Claude; годится только для российского окна владельца."""
    for k in range(tries):
        try:
            r = requests.get(original, headers=H, timeout=(20, 60))
            if r.status_code in (429, 502, 503, 504):
                print(f"      mathnet {r.status_code} -> backoff"); time.sleep(6 * (k + 1)); continue
            return r, r.content.decode("windows-1251", errors="replace")
        except requests.RequestException as e:
            print(f"      {type(e).__name__} -> backoff"); time.sleep(6 * (k + 1))
    return None, None


def fetch(ts, original, live=False):
    """Единая точка входа: Wayback по умолчанию, --live -> live_get(). Оба ведут в один parse_*."""
    return live_get(original) if live else wb_get(ts, original)


def check_real(label, txt, must_have, min_cyr=500):
    """§3: КРИТЕРИЙ, КОТОРЫЙ МОЖЕТ ПРОВАЛИТЬСЯ. Код 200 — не доказательство.

    Ловим: страницу-404 Wayback (она приходит с полным html!), капчу, JS-заглушку, пустышку.
    """
    problems = []
    if not txt:
        return ["нет ответа"]
    cyr = len(re.findall(r"[А-Яа-яЁё]", txt))
    if cyr < min_cyr:
        problems.append(f"кириллицы {cyr} < {min_cyr} (заглушка/404/капча?)")
    if "<title>Wayback Machine</title>" in txt:
        problems.append("это страница-404 самого Wayback, а не архивная копия")
    for tok in must_have:
        if tok not in txt:
            problems.append(f"нет ожидаемого токена {tok!r}")
    for bad in ("captcha", "Проверка браузера", "checking your browser"):
        if bad.lower() in txt.lower():
            problems.append(f"маркер капчи/заглушки: {bad!r}")
    print(f"      проверка «контент настоящий»: кириллицы={cyr}, "
          f"{'ОК' if not problems else 'ПРОВАЛ: ' + '; '.join(problems)}")
    return problems


def parse_colloquium(txt):
    """Коллоквиум МИАН: <a class=SLink href=/rus/presentN>Заголовок</a><br>Докладчик<br><i>дата</i>."""
    soup = BeautifulSoup(txt, "html.parser")
    talks, seen = [], set()
    for a in soup.find_all("a", class_="SLink"):
        href = a.get("href") or ""
        if not re.fullmatch(r"/rus/present\d+", href) or href in seen:
            continue
        seen.add(href)
        bits, date_raw = [], None
        node = a.next_sibling
        while node is not None:
            name = getattr(node, "name", None)
            if name == "i":                                   # <i>дата время</i>, место
                date_raw = norm(node.get_text(" ", strip=True)); break
            if name == "a":
                break
            s = norm(node.get_text(" ", strip=True)) if hasattr(node, "get_text") else norm(str(node))
            if s:
                bits.append(s)
            node = node.next_sibling
        iso = None
        m = re.search(r"(\d{1,2})\s+([а-я]+)\s+(\d{4})", date_raw or "")
        if m and m.group(2) in MONTHS:
            iso = f"{m.group(3)}-{MONTHS[m.group(2)]:02d}-{int(m.group(1)):02d}"
        talks.append({
            "title": norm(a.get_text(" ", strip=True)),
            "speaker": " ".join(bits) or None,
            "date_raw": date_raw,
            "date": iso,
            "url": "https://www.mathnet.ru" + href,
            "video_or_abstract_url":
                f"https://www.mathnet.ru/php/presentation.phtml?option_lang=rus&presentid={href.split('present')[-1]}",
        })
    return talks


def parse_umn_issue(txt):
    """Оглавление выпуска УМН: <a class=SLink href=/rus/rmN>Заголовок</a><br>Авторы + div со стр. и DOI."""
    soup = BeautifulSoup(txt, "html.parser")
    arts, seen = [], set()
    for a in soup.find_all("a", class_="SLink"):
        href = a.get("href") or ""
        if not re.fullmatch(r"/rus/rm\d+", href) or href in seen:
            continue
        seen.add(href)
        authors_bits, meta_div = [], None
        node = a.next_sibling
        while node is not None:
            name = getattr(node, "name", None)
            if name == "div":
                meta_div = node; break
            if name == "a" and re.fullmatch(r"/rus/rm\d+", node.get("href") or ""):
                break
            s = norm(node.get_text(" ", strip=True)) if hasattr(node, "get_text") else norm(str(node))
            if s:
                authors_bits.append(s)
            node = node.next_sibling
        pages = doi = None
        if meta_div is not None:
            mt = norm(meta_div.get_text(" ", strip=True))
            mp = re.search(r"страницы\s+([\d]+\s*[–-]\s*[\d]+)", mt)
            pages = norm(mp.group(1)) if mp else None
            for link in meta_div.find_all("a", href=True):
                if "doi.org" in link["href"] and not link["href"].rstrip("/").endswith("e"):
                    doi = link["href"]; break
        pid = href.split("rm")[-1]
        arts.append({
            "title": norm(a.get_text(" ", strip=True)),
            "authors": " ".join(authors_bits) or None,
            "pages": pages,
            "doi": doi,
            "abstract_url": "https://www.mathnet.ru" + href,
            "pdf_url": f"https://www.mathnet.ru/php/getFT.phtml?jrnid=rm&paperid={pid}&what=fullt&option_lang=rus",
        })
    return arts


def parse_umn_paper(txt):
    """Страница статьи УМН — то, чего НЕТ в Crossref: русская аннотация, ключевые слова, PDF."""
    soup = BeautifulSoup(txt, "html.parser")
    out = {"title": None, "abstract_ru": None, "keywords_ru": None, "pdf_url": None, "pdf_label": None}
    t = soup.find("title")
    if t:
        out["title"] = norm(t.get_text())
    for b in soup.find_all("b"):
        head = norm(b.get_text())
        if head.startswith("Аннотация") and b.parent is not None:
            out["abstract_ru"] = norm(b.parent.get_text(" ", strip=True)).replace("Аннотация:", "").strip()
        elif head.startswith("Ключевые слова") and b.parent is not None:
            out["keywords_ru"] = norm(b.parent.get_text(" ", strip=True)).replace("Ключевые слова:", "").strip()
    for a in soup.find_all("a", href=True):
        if "getFT.phtml" in a["href"]:
            out["pdf_url"] = "https://www.mathnet.ru" + a["href"] if a["href"].startswith("/") else a["href"]
            out["pdf_label"] = norm(a.get_text())
            break
    return out


def save_raw(label, timestamp, txt):
    path = os.path.join(RAW, f"{label}_{timestamp}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(txt)
    return os.path.relpath(path, ROOT)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true",
                         help="ZAHOD-6 §3-Г: ходить напрямую в mathnet вместо Wayback "
                              "(транспорт не проверен под VPN-стеной — только для российского окна)")
    args = parser.parse_args()

    os.makedirs(RAW, exist_ok=True)
    verdicts, failures = {}, []

    # ---------- 1. Коллоквиум МИАН, confid=142 «Математика и её приложения» ----------
    label, ts, orig = COLLOQ
    lever = "live" if args.live else "wayback"
    print(f"[1/3] Коллоквиум МИАН confid=142  <- {lever} {'' if args.live else ts}  {orig}")
    r, txt = fetch(ts, orig, args.live)
    probs = check_real(label, txt, must_have=["Математика и ее приложения"])
    talks = parse_colloquium(txt) if not probs else []
    empty = [t for t in talks if not (t["title"] and t["speaker"] and t["date_raw"])]
    if probs or len(talks) < 10 or empty:
        failures.append(f"колоквиум: {probs or ''} записей={len(talks)} пустых={len(empty)}")
    else:
        raw_path = save_raw(label, ts, txt)
        with open(os.path.join(OUT, "colloquium_mian.json"), "w", encoding="utf-8") as f:
            json.dump({"source_url": orig, "wayback_timestamp": ts, "lever": lever,
                       "count": len(talks), "talks": talks}, f, ensure_ascii=False, indent=2)
        verdicts["colloquium"] = {"records": len(talks), "empty_fields": len(empty), "raw": raw_path,
                                  "newest_talk": talks[0]["date"], "oldest_talk": talks[-1]["date"]}
        print(f"      -> {len(talks)} докладов, пустых полей 0, свежайший {talks[0]['date']}")
    time.sleep(PAUSE)

    # ---------- 2. УМН — последний выпуск ----------
    label, ts, orig = UMN_ISSUE
    print(f"[2/3] УМН, последний выпуск  <- {'live' if args.live else 'Wayback ' + ts}  {orig}")
    r, txt = fetch(ts, orig, args.live)
    probs = check_real(label, txt, must_have=["Успехи математических наук"])
    arts = parse_umn_issue(txt) if not probs else []
    m = re.search(r"<title>(.*?)</title>", txt or "", re.S | re.I)
    issue_title = norm(BeautifulSoup(m.group(1), "html.parser").get_text()) if m else None
    empty_a = [a for a in arts if not (a["title"] and a["abstract_url"])]
    if probs or len(arts) < 1 or empty_a:
        failures.append(f"УМН-выпуск: {probs or ''} статей={len(arts)} пустых={len(empty_a)}")
    else:
        raw_path = save_raw(label, ts, txt)
        with open(os.path.join(OUT, "umn_last_issue.json"), "w", encoding="utf-8") as f:
            json.dump({"source_url": orig, "wayback_timestamp": ts, "lever": lever,
                       "issue": issue_title, "count": len(arts), "articles": arts},
                      f, ensure_ascii=False, indent=2)
        verdicts["umn_issue"] = {"issue": issue_title, "records": len(arts), "raw": raw_path}
        print(f"      -> {issue_title}: {len(arts)} статей")
    time.sleep(PAUSE)

    # ---------- 3. УМН — страница статьи (аннотация + PDF: чего нет в Crossref) ----------
    label, ts, orig = UMN_PAPER
    print(f"[3/3] УМН, страница статьи  <- {'live' if args.live else 'Wayback ' + ts}  {orig}")
    r, txt = fetch(ts, orig, args.live)
    probs = check_real(label, txt, must_have=["Аннотация"])
    paper = parse_umn_paper(txt) if not probs else {}
    if probs or not paper.get("abstract_ru") or not paper.get("pdf_url"):
        failures.append(f"УМН-статья: {probs or ''} аннотация={bool(paper.get('abstract_ru'))} pdf={bool(paper.get('pdf_url'))}")
    else:
        raw_path = save_raw(label, ts, txt)
        with open(os.path.join(OUT, "umn_paper_sample.json"), "w", encoding="utf-8") as f:
            json.dump({"source_url": orig, "wayback_timestamp": ts, "lever": lever,
                       "paper": paper}, f, ensure_ascii=False, indent=2)
        verdicts["umn_paper"] = {"abstract_chars": len(paper["abstract_ru"]), "pdf": paper["pdf_url"],
                                 "raw": raw_path}
        print(f"      -> аннотация {len(paper['abstract_ru'])} симв., PDF: {paper['pdf_label']}")

    # ---------- итог ----------
    summary = {
        "zahod": "ZAHOD-6 mian colloquium confid=142 (перенацелено с мёртвого confid=408, ЗАХОД-5)",
        "lever_used": "live" if args.live else "3 — Wayback (web.archive.org), id_-плейбек архивных копий mathnet.ru",
        "levers_failed": {
            "1_requests_live": "TCP:443 не устанавливается (connect=0); ICMP 3/3, порт 80 RST; "
                               "контроли crossref/archive.org = 200. Капчи нет — до HTTP не доходит.",
            "2_oai_pmh": "тот же хост -> та же стена (connect=0 на обоих кандидат-эндпоинтах)",
        },
        "freshness_caveat": "данные — на дату снапшота, не на сегодня",
        "checks": verdicts,
        "failures": failures,
    }
    with open(os.path.join(OUT, "_probe_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    if failures:
        print("ВЕРДИКТ: ПРОВАЛ ГЕЙТА —", "; ".join(failures))
        return 1
    print("ВЕРДИКТ: выемка удалась. Рычаг 3 (Wayback) даёт настоящий контент mathnet.")
    for k, v in verdicts.items():
        print(f"  {k}: {v}")
    print(f"Файлы -> {os.path.relpath(OUT, ROOT)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())

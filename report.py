#!/usr/bin/env python3
"""Отчёт о распределении карты: report.md + report.html (инлайн-SVG графики).
Все числа берутся ПРЯМЫМ запросом к materials.db."""

import sqlite3, datetime, html
from collections import Counter, defaultdict
from config import DB_PATH, FROM, UNTIL

CAT_NAMES = {"A": "A · Проф. обзорные журналы", "B": "B · Обзорные площадки",
             "C": "C · Научпоп", "D": "D · Блоги математиков", "E": "E · Разовое/люди/события"}

def load():
    c = sqlite3.connect(DB_PATH); c.row_factory = sqlite3.Row
    return c, list(c.execute("SELECT * FROM materials"))

# ---- простые инлайн-SVG графики (без внешних зависимостей на рендере) ----
def bar_svg(pairs, width=680, bar_h=26, gap=8, pad_l=210, color="#3b6ea5", unit=""):
    pairs = list(pairs)
    if not pairs: return "<p>—</p>"
    mx = max(v for _, v in pairs) or 1
    h = len(pairs) * (bar_h + gap) + gap
    plot = width - pad_l - 60
    out = [f'<svg viewBox="0 0 {width} {h}" width="100%" style="max-width:{width}px" xmlns="http://www.w3.org/2000/svg" font-family="system-ui,sans-serif" font-size="13">']
    y = gap
    for label, v in pairs:
        w = int(plot * v / mx)
        lab = html.escape(str(label))[:34]
        out.append(f'<text x="{pad_l-8}" y="{y+bar_h*0.68}" text-anchor="end" fill="var(--fg)">{lab}</text>')
        out.append(f'<rect x="{pad_l}" y="{y}" width="{max(w,1)}" height="{bar_h}" rx="3" fill="{color}"/>')
        out.append(f'<text x="{pad_l+max(w,1)+6}" y="{y+bar_h*0.68}" fill="var(--fg)">{v}{unit}</text>')
        y += bar_h + gap
    out.append("</svg>")
    return "\n".join(out)

def month_hist_svg(month_counts, width=680, height=220, pad=34):
    months = sorted(month_counts)
    if not months: return "<p>—</p>"
    mx = max(month_counts.values()) or 1
    plot_w = width - pad*2; plot_h = height - pad*2
    bw = plot_w / len(months)
    out = [f'<svg viewBox="0 0 {width} {height}" width="100%" style="max-width:{width}px" xmlns="http://www.w3.org/2000/svg" font-family="system-ui,sans-serif" font-size="11">']
    out.append(f'<line x1="{pad}" y1="{height-pad}" x2="{width-pad}" y2="{height-pad}" stroke="var(--muted)"/>')
    for i, m in enumerate(months):
        v = month_counts[m]; bh = int(plot_h * v / mx)
        x = pad + i*bw
        out.append(f'<rect x="{x+2}" y="{height-pad-bh}" width="{bw-4}" height="{bh}" rx="2" fill="#3b6ea5"/>')
        out.append(f'<text x="{x+bw/2}" y="{height-pad-bh-4}" text-anchor="middle" fill="var(--fg)">{v}</text>')
        out.append(f'<text x="{x+bw/2}" y="{height-pad+14}" text-anchor="middle" fill="var(--muted)" transform="rotate(0 {x+bw/2} {height-pad+14})">{m[5:]}</text>')
    out.append(f'<text x="{pad}" y="{pad-12}" fill="var(--muted)">материалов/мес (max {mx})</text>')
    out.append("</svg>")
    return "\n".join(out)

def week_hist_svg(week_counts, width=680, height=200, pad=30):
    """Гистограмма 'тихие vs обвальные недели': распределение недель по числу материалов."""
    if not week_counts: return "<p>—</p>"
    dist = Counter(week_counts.values())          # сколько_материалов -> сколько_недель
    buckets = list(range(0, max(dist)+1))
    mx = max(dist.values()) or 1
    plot_w = width - pad*2; plot_h = height - pad*2
    bw = plot_w / max(len(buckets),1)
    out = [f'<svg viewBox="0 0 {width} {height}" width="100%" style="max-width:{width}px" xmlns="http://www.w3.org/2000/svg" font-family="system-ui,sans-serif" font-size="11">']
    out.append(f'<line x1="{pad}" y1="{height-pad}" x2="{width-pad}" y2="{height-pad}" stroke="var(--muted)"/>')
    for i, b in enumerate(buckets):
        v = dist.get(b, 0); bh = int(plot_h * v / mx)
        x = pad + i*bw
        out.append(f'<rect x="{x+2}" y="{height-pad-bh}" width="{bw-4}" height="{bh}" rx="2" fill="#a5673b"/>')
        if v: out.append(f'<text x="{x+bw/2}" y="{height-pad-bh-3}" text-anchor="middle" fill="var(--fg)">{v}</text>')
        out.append(f'<text x="{x+bw/2}" y="{height-pad+14}" text-anchor="middle" fill="var(--muted)">{b}</text>')
    out.append(f'<text x="{width//2}" y="{height-6}" text-anchor="middle" fill="var(--muted)">материалов за неделю (X) → число таких недель (Y)</text>')
    out.append("</svg>")
    return "\n".join(out)

def iso_week(datestr):
    """YYYY-MM-DD|YYYY-MM|YYYY -> ISO 'YYYY-Www' (недостающее добиваем до 1-го)."""
    p = str(datestr).split("-")
    y = int(p[0]); m = int(p[1]) if len(p) > 1 else 1; d = int(p[2]) if len(p) > 2 else 1
    try:
        iso = datetime.date(y, m, d).isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"
    except Exception:
        return None

def compute(rows):
    st = {}
    st["total"] = len(rows)
    st["by_cat"] = Counter(r["category"] for r in rows)
    st["by_area"] = Counter((r["area"] or "—не определён—") for r in rows)
    st["by_type"] = Counter(r["type"] for r in rows)
    months = Counter()
    weeks = Counter()
    for r in rows:
        if r["date"]:
            months[str(r["date"])[:7]] += 1
            w = iso_week(r["date"])
            if w: weeks[w] += 1
    st["months"] = months
    st["weeks"] = weeks
    st["quanta"] = sum(1 for r in rows if r["tags"] and "is_quanta" in r["tags"])
    st["breadth3"] = sum(1 for r in rows if (r["breadth_score"] or 0) >= 3)
    st["breadth4"] = sum(1 for r in rows if (r["breadth_score"] or 0) >= 4)
    # недельная статистика: полный набор ISO-недель окна (перебор дней)
    d0 = datetime.date(*map(int, FROM.split("-")))
    d1 = datetime.date(*map(int, UNTIL.split("-")))
    all_weeks = set()
    d = d0
    while d <= d1:
        iso = d.isocalendar(); all_weeks.add(f"{iso[0]}-W{iso[1]:02d}"); d += datetime.timedelta(days=7)
    total_weeks = len(all_weeks)
    wv = [weeks.get(w, 0) for w in all_weeks]        # включая тихие недели = 0
    st["total_weeks"] = total_weeks
    st["wk_mean"] = round(st["total"] / total_weeks, 1)
    st["wk_min"] = min(wv) if wv else 0
    st["wk_max"] = max(wv) if wv else 0
    st["silent_weeks"] = max(0, sum(1 for v in wv if v == 0))
    # для гистограммы недель — только недели окна
    st["weeks"] = {w: weeks.get(w, 0) for w in all_weeks}
    return st

def render_md(st):
    L = []
    L.append(f"# MATEMDIGEST · карта года — отчёт о распределении\n")
    L.append(f"Окно: **{FROM} → {UNTIL}**. Сгенерировано: {datetime.datetime.now():%Y-%m-%d %H:%M}.\n")
    L.append(f"**Всего материалов-кандидатов: {st['total']}**\n")
    L.append("## По категориям")
    for k in ["A","B","C","D","E"]:
        L.append(f"- {CAT_NAMES[k]}: **{st['by_cat'].get(k,0)}**")
    L.append(f"\n## По разделам математики ({len([a for a in st['by_area'] if a!='—не определён—'])} определённых)")
    for a, v in st["by_area"].most_common():
        L.append(f"- {a}: {v}")
    L.append("\n## По месяцам")
    for m, v in sorted(st["months"].items()):
        L.append(f"- {m}: {v}")
    L.append("\n## Недельный ритм («реально ли 5–8/нед?»)")
    L.append(f"- недель в окне: {st['total_weeks']}; среднее **{st['wk_mean']}/нед**; "
             f"недельный min={st['wk_min']}, max={st['wk_max']}; тихих недель (0 материалов): {st['silent_weeks']}")
    L.append("\n## Ключевые доли")
    L.append(f"- **доля Quanta: {100*st['quanta']/st['total']:.1f}%** (потолок ~25% — {'OK' if st['quanta']/st['total']<=0.25 else 'ПРЕВЫШЕН'})")
    L.append(f"- материалов с breadth_score ≥ 3: **{st['breadth3']}** ({100*st['breadth3']/st['total']:.0f}%)")
    L.append(f"- материалов с breadth_score ≥ 4 (высшая широта): **{st['breadth4']}**")
    L.append(f"\n## По типам")
    for t, v in st["by_type"].most_common():
        L.append(f"- {t}: {v}")
    return "\n".join(L) + "\n"

def render_html(st):
    cat_pairs = [(CAT_NAMES[k], st["by_cat"].get(k,0)) for k in ["A","B","C","D","E"]]
    area_pairs = st["by_area"].most_common()
    type_pairs = st["by_type"].most_common()
    q_share = 100*st["quanta"]/st["total"]
    css = """
    :root{--fg:#1a1a1a;--muted:#888;--bg:#ffffff;--card:#f6f7f9;--accent:#3b6ea5}
    @media (prefers-color-scheme:dark){:root{--fg:#e8e8e8;--muted:#999;--bg:#14161a;--card:#1e2229;--accent:#5b8fc9}}
    :root[data-theme=dark]{--fg:#e8e8e8;--muted:#999;--bg:#14161a;--card:#1e2229;--accent:#5b8fc9}
    :root[data-theme=light]{--fg:#1a1a1a;--muted:#888;--bg:#ffffff;--card:#f6f7f9;--accent:#3b6ea5}
    *{box-sizing:border-box}body{margin:0;font-family:system-ui,-apple-system,sans-serif;background:var(--bg);color:var(--fg);line-height:1.5}
    .wrap{max-width:820px;margin:0 auto;padding:32px 20px 80px}
    h1{font-size:26px;margin:0 0 4px}h2{font-size:18px;margin:34px 0 12px;border-bottom:1px solid var(--muted);padding-bottom:6px}
    .sub{color:var(--muted);font-size:14px}
    .kpis{display:flex;flex-wrap:wrap;gap:12px;margin:22px 0}
    .kpi{background:var(--card);border-radius:10px;padding:14px 18px;flex:1 1 140px}
    .kpi b{font-size:26px;display:block}.kpi span{color:var(--muted);font-size:13px}
    .card{background:var(--card);border-radius:10px;padding:16px;margin:10px 0;overflow-x:auto}
    .note{color:var(--muted);font-size:13px;margin-top:6px}
    """
    def kpi(v, label): return f'<div class="kpi"><b>{v}</b><span>{html.escape(label)}</span></div>'
    parts = [f"<title>MATEMDIGEST · карта года</title><style>{css}</style>",
        '<div class="wrap">',
        "<h1>MATEMDIGEST · карта года</h1>",
        f'<div class="sub">Отчёт о распределении кандидатов · окно {FROM} → {UNTIL} · {datetime.datetime.now():%Y-%m-%d %H:%M}</div>',
        '<div class="kpis">',
        kpi(st["total"], "всего кандидатов"),
        kpi(f"{st['wk_mean']}", "в среднем / неделю"),
        kpi(f"{q_share:.1f}%", "доля Quanta (≤25%)"),
        kpi(st["breadth3"], "breadth ≥ 3"),
        kpi(len([a for a in st['by_area'] if a!='—не определён—']), "разделов математики"),
        "</div>",
        "<h2>По категориям источников</h2>", f'<div class="card">{bar_svg(cat_pairs)}</div>',
        "<h2>По разделам математики</h2>", f'<div class="card">{bar_svg(area_pairs, color="#5a8a4a")}</div>',
        "<h2>По месяцам</h2>", f'<div class="card">{month_hist_svg(st["months"])}</div>',
        "<h2>Недельный ритм: тихие vs обвальные недели</h2>",
        f'<div class="card">{week_hist_svg(st["weeks"])}',
        f'<div class="note">недель в окне ≈ {st["total_weeks"]}, из них тихих (0 материалов): {st["silent_weeks"]}; '
        f'недельный размах {st["wk_min"]}–{st["wk_max"]}. Вопрос захода «реально ли 5–8/нед» → '
        f'среднее {st["wk_mean"]}/нед.</div></div>',
        "<h2>По типам материала</h2>", f'<div class="card">{bar_svg(type_pairs, color="#8a5a7a")}</div>',
        '<div class="note">Числа берутся прямым запросом к materials.db. Скоринг — прозрачная эвристика (см. README).</div>',
        "</div>"]
    return "\n".join(parts)

def main():
    c, rows = load()
    st = compute(rows)
    open("report.md", "w", encoding="utf-8").write(render_md(st))
    open("report.html", "w", encoding="utf-8").write(render_html(st))
    print(f"report.md + report.html: total={st['total']}, Quanta={100*st['quanta']/st['total']:.1f}%, "
          f"breadth>=3={st['breadth3']}, wk_mean={st['wk_mean']}, silent_weeks={st['silent_weeks']}")

if __name__ == "__main__":
    main()

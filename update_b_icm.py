#!/usr/bin/env python3
"""ZAHOD-7 · направление B — централизованный UPDATE 5 подтверждённых ICM-2026 плёнарок.
Одноразовый скрипт (§2 границ: только код в корне, existing rows кроме 16 ICM не трогает).
Данные собраны субагентами (arXiv, полный текст прочитан), даты сверены напрямую curl->arXiv abs.
"""
import sqlite3, datetime

DB = "materials.db"
TODAY = "2026-07-16"

ROWS = [
    dict(
        id="cb068fd9b4bf6663",  # Dennis Gaitsgory
        authors="Dennis Gaitsgory",
        date="2025-09-29",
        url="https://arxiv.org/abs/2509.24902",
        type="plenary",
        summary="Write-up к пленарному докладу ICM 2026: системный подход к вопросу программы "
                "Ленглендса над функциональными полями — как описать пространство автоморфных "
                "функций через спектральные параметры Ленглендса (высшие категории, категорный "
                "след Фробениуса).",
        g1=2, g2=1, g3=1, g4=3, g5=2,
        areas_multi="теория чисел;алгебра;теория представлений",
        interdisc=1,
        read_note="Официальный write-up к пленарному докладу ICM-2026 о геометрической программе "
                   "Ленглендса — событие года в математике, но текст плотный и техничный, требует "
                   "серьёзной подготовки в алгебраической геометрии и теории представлений.",
        content_read=1,
        notes="Открытый доступ (arXiv), английский; abstract прямо содержит фразу "
              "'This is a write-up for the plenary ICM talk, 2026.'",
        keep=1, fit_reason="event",
    ),
    dict(
        id="58bd1f1a5c2b394d",  # Alex Kontorovich
        authors="Alex Kontorovich",
        date="2025-10-03",
        url="https://arxiv.org/abs/2510.15924",
        type="plenary",
        summary="«The Shape of Math To Come» — обзор о том, как большие языковые модели и системы "
                "формальной верификации (Lean, Mathlib) меняют математическую практику: поиск "
                "доказательств, преподавание, коммуникацию в сообществе.",
        g1=2, g2=3, g3=2, g4=2, g5=3,
        areas_multi="computer science;история/философия;образование",
        interdisc=1,
        read_note="Осознанно написанный мост для широкой математической аудитории о культуре и "
                   "будущем профессии на фоне ИИ и формальной верификации, без глубокого "
                   "технического жаргона.",
        content_read=1,
        notes="Открытый доступ (arXiv HTML+PDF), английский, самодостаточен; comments явно "
              "указывают 'for Proceedings of the ICM 2026'.",
        keep=1, fit_reason="popsci",
    ),
    dict(
        id="78ae8d54a3bfe308",  # Ciprian Manolescu
        authors="Ciprian Manolescu",
        date="2026-01-08",
        url="https://arxiv.org/abs/2601.05425",
        type="plenary",
        summary="«From Knots to Four-Manifolds» — обзор связи теории узлов и 4-мерной топологии: "
                "любое 4-многообразие кодируется диаграммой Кирби через зацепление на его границе, "
                "что даёт вычислимые инварианты экзотических гладких структур (Хегора–Флоер, "
                "скейн-лазанья-модули).",
        g1=2, g2=2, g3=2, g4=2, g5=3,
        areas_multi="топология;геометрия",
        interdisc=1,
        read_note="Мост между теорией узлов (маломерная топология) и топологией 4-многообразий "
                   "для широкой аудитории геометров-топологов, написан специально к ICM-2026.",
        content_read=1,
        notes="Открытый доступ (arXiv), английский; comments 'to appear in Proceedings of the "
              "ICM 2026'.",
        keep=1, fit_reason="bridge",
    ),
    dict(
        id="50db3514c764ba9c",  # Robert Morris
        authors="Robert Morris",
        date="2026-01-08",
        url="https://arxiv.org/abs/2601.05221",
        type="plenary",
        summary="«Some recent results in Ramsey theory» — доступное введение в недавние прорывы "
                "диагональной, почти-диагональной и многоцветной рэмсеевской теории: экспоненциальные "
                "улучшения оценок чисел Рамсея, границы для R(3,k) и R(4,k), индуцированные числа "
                "Рамсея.",
        g1=1, g2=3, g3=2, g4=2, g5=2,
        areas_multi="комбинаторика",
        interdisc=0,
        read_note="Написан как доступный обзор для широкой аудитории математиков, но тема остаётся "
                   "внутри комбинаторики; автор — один из соавторов описываемых прорывов.",
        content_read=1,
        notes="Открытый доступ (arXiv), английский. Совпадение темы/названия с анонсированной "
              "темой пленарной лекции ICM-2026 (29 июля) подтверждено вторичными источниками "
              "(ABC/IPAM), явной пометки 'Proceedings of ICM' в comments нет.",
        keep=1, fit_reason="bridge",
    ),
    dict(
        id="64e401beeceaec16",  # Hee Oh
        authors="Hee Oh",
        date="2025-10-12",
        url="https://arxiv.org/abs/2510.10771",
        type="plenary",
        summary="«Dynamics and Rigidity through the Lens of Circles» — обзор организован вокруг "
                "четырёх наглядных вопросов о круговых упаковках, связывающих однородную динамику "
                "в бесконечном объёме, гиперболическую геометрию, меры Паттерсона—Салливан и "
                "теоретико-представленческую жёсткость клейновых групп.",
        g1=3, g2=2, g3=2, g4=2, g5=3,
        areas_multi="геометрия;динамические системы;теория чисел",
        interdisc=1,
        read_note="Визуальная тема (круги, упаковки) как точка входа для широкой аудитории "
                   "математиков, ведущая к серьёзным современным результатам; написан специально "
                   "для ICM-2026.",
        content_read=1,
        notes="Открытый доступ (arXiv), английский, самодостаточный обзорный текст с рисунками; "
              "comments 'To appear in the Proceedings of the ICM 2026'.",
        keep=1, fit_reason="bridge",
    ),
]

con = sqlite3.connect(DB)
cur = con.cursor()

before = cur.execute("SELECT count(*) FROM materials").fetchone()[0]

for r in ROWS:
    score_total = 2 * r["g1"] + 2 * r["g3"] + r["g2"] + r["g4"]
    cur.execute(
        """UPDATE materials SET
             authors=?, date=?, url=?, type=?, summary=?,
             g1_breadth=?, g2_bridge=?, g3_clarity=?, g4_signif=?, g5_extract=?, score_total=?,
             areas_multi=?, interdisc=?, read_note=?, content_read=?, notes=?,
             scored_from='precise', keep=?, fitness=3, fit_reason=?, retrieved_at=?
           WHERE id=?""",
        (
            r["authors"], r["date"], r["url"], r["type"], r["summary"],
            r["g1"], r["g2"], r["g3"], r["g4"], r["g5"], score_total,
            r["areas_multi"], r["interdisc"], r["read_note"], r["content_read"], r["notes"],
            r["keep"], r["fit_reason"], TODAY,
            r["id"],
        ),
    )
    assert cur.rowcount == 1, f"UPDATE не задело ровно 1 строку для id={r['id']} (rowcount={cur.rowcount})"

con.commit()
after = cur.execute("SELECT count(*) FROM materials").fetchone()[0]
assert before == after == 858, f"count(*) изменился: {before} -> {after}, ожидалось 858 (только UPDATE, не INSERT)"

print(f"OK: {len(ROWS)} строк ICM обновлено (UPDATE), count(*) не изменился = {after}")
for r in ROWS:
    row = cur.execute(
        "SELECT title, score_total, g2_bridge FROM materials WHERE id=?", (r["id"],)
    ).fetchone()
    passed = row[1] is not None and row[1] >= 10 and row[2] >= 1
    print(f"  {r['id']}  {row[0]:45}  score_total={row[1]:>2}  {'ПРОШЁЛ' if passed else 'не прошёл'}")

con.close()

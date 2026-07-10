#!/usr/bin/env python3
"""Общие константы карты. Перезапуск на новом окне = правка ДВУХ констант ниже."""

FROM  = "2025-07-01"          # начало скользящего окна (12 мес)
UNTIL = "2026-07-10"          # конец окна (сегодня)
MAILTO = "claude.17957@gmail.com"   # Crossref polite pool + вежливый User-Agent

DB_PATH = "materials.db"
UA = f"Mozilla/5.0 (matemdigest-map research; {MAILTO})"

# заголовок запросов для всех HTTP
HEADERS = {"User-Agent": UA}

# для сравнения дат
def in_window(date_str):
    """date_str = 'YYYY-MM-DD' | 'YYYY-MM' | 'YYYY' | None -> bool (в окне?)."""
    if not date_str:
        return True                       # неизвестную дату не режем (§2)
    s = str(date_str)[:10]
    # добить до YYYY-MM-DD для сравнения
    parts = s.split("-")
    if len(parts) == 1:
        s = f"{parts[0]}-01-01"
    elif len(parts) == 2:
        s = f"{parts[0]}-{parts[1]}-01"
    return FROM <= s <= UNTIL

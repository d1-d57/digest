ЗАЯВКА: 2026-08-23T11:28 · автор: sandbox · арка: 2026-08-22_ratsionalnost
СРОЧНОСТЬ: obychnaya
РОД: git-operaciya

Закоммитить работу сессии 2 арки «рациональность» — фаза raskladka выпуска 05 принята владельцем, гейт фазы зелёный целиком (скрипт и верификатор на одном хеше). Из песочницы Cowork коммит не проходит по построению.

Три зоны, три коммита.

1. зона vypuski/2026-08-29-vypusk-05 — новая папка выпуска
   Сообщение: выпуск 05: раскладка принята, шесть разделов, ядро — метод специализации
   Пути: vypuski/2026-08-29-vypusk-05/RASKLADKA.md · OTCHET.md · .proverki.json
   ⚠ .proverki.json — отметки гейта (скрипт + верификатор, оба по хешу RASKLADKA.md). Если
   порождаемое, а не источник, — снять и внести в .gitignore, решает закрывающий заход.

2. зона docs — дневник интервью и долги
   Сообщение: рациональность: условия У16-У19 раскладки, долги Д42-Д43
   Пути: docs/dnevnik-intervyu-ratsionalnost.md (новый, весь артефакт фазы kalibrovka) ·
   docs/DOLGI.md (Д42 — имя строки приёмки расходится между фазой и скриптом; Д43 — анкета
   раскладки не знает трёх решений своей же фазы)

3. зона zhurnal/2026-08-22_ratsionalnost — память арки
   Сообщение: арка рациональность: раскладка закрыта, сессия 2 в дневнике
   Пути: NAVIGATOR.md · PLAN.md · SESSIYA.md · HANDOFF-2026-08-22.md · ZAYAVKA-NA-KOMMIT.md

Заявка ZAYAVKA-NA-KOMMIT.md в папке арки открыта с 22.08 и покрывает работу сессии 1 (фазы
kalibrovka и razvedka, картотека, семь фаз в PORYADOK). Эта заявка её дополняет, а не заменяет:
закрывающему заходу удобнее закрыть обе одним прогоном plan → commit.

Чужого в дереве много и оно НЕ наше: _studio/zhurnal/_INFRA-git/INCIDENTY.md, docs/PROTOKOL-VYPUSKA.md,
docs/fazy/razvedka.md, vypuski/proverki.py, docs/reestr-syuzhetov.md, docs/pravila-vypuska.md,
docs/kandidat-diskrepans.md, docs/razvedka-diskrepans.md, docs/SHABLON-razvedki.md,
docs/razvedka-topologiya-i-analiz.md, docs/zapros-portretnyy-vypusk.md, два kod_*.md в чужих арках.
Часть покрыта заявками 16.08-20.08 в zhurnal/_INFRA-git/. Не подметать под наши сообщения.
ЗАКРЫТО: 2026-09-17T23:56 · EXECUTED IN FACT by git revision G1, 2026-09-17: the session-2 backlog of the рациональность arc including выпуск 05 is committed to rabota (ef14718) and pushed to origin/rabota; status --porcelain on that branch is 0

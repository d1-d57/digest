ЗАЯВКА: 2026-08-17T20:29 · автор: sandbox · арка: 2026-08-15_vypusk-04
СРОЧНОСТЬ: obychnaya
РОД: git-operaciya

Закоммитить зону подводки к выпуску 4 и три правки в сам выпуск. Полная развёртка с проверками и разбором конфликта — zhurnal/_INFRA-git/ZAYAVKA-2026-08-17-post-vypusk-04.md, читать её целиком.

МОЯ ЗОНА, семь путей, ничего чужого:
  posty/2026-08-17-vypusk-04/{SYRYO,FAKTY,PLAN,CHERNOVIK,post}.md   память семи фаз kt-channel-editor
  vypuski/2026-08-15-vypusk-04/post.md                              пост в архиве выпуска, как в 1-3
  vypuski/2026-08-15-vypusk-04/vypusk.md                            ТРИ правки с интервью владельца 17.08

Три правки в vypusk.md: areas раздела 1 'история математики' -> 'геометрия'; areas раздела 6 'геометрия чисел' -> 'выпуклая геометрия'; ссылка на интервью Вязовской в разделе 3 заменена на https://d1-d57.github.io/digest/vyazovskaya/ с пометкой '(русский перевод)', дата исправлена с 'июнь 2022, двенадцать страниц' на 'февраль 2022' - переведена февральская часть.

КОНФЛИКТ, решать заходу: тот же vypusk.md взят под своё сообщение соседней сессией (zhurnal/2026-08-15_vypusk-04/ZAYAVKA-NA-KOMMIT.md, дополнение '17.08, вечер'). Построчно не пересекаемся - она правит прозу блоков, я правил две строки areas и одну link. Файл один, разделить нельзя: один коммит, сообщение соседней сессии дополнить строкой про три правки с интервью. Кто закрывает первым - забирает файл целиком и называет смешение.

ПЕРВЫМ ХОДОМ пересобрать виды: cd vypuski && python3 build_vypusk.py 2026-08-15-vypusk-04/vypusk.md - vypusk.html, vypusk.telegram.txt и vypusk.teaser.txt на диске отстают от источника: я собирал их сразу после своих правок, а vypusk.md правился соседней сессией дальше. Виды едут тем же коммитом, что и источник.

ПРОВЕРИТЬ ПЕРЕД КОММИТОМ:
  grep -n 'areas: геометрия$|areas: выпуклая геометрия|digest/vyazovskaya' vypuski/2026-08-15-vypusk-04/vypusk.md   ждём три строки
  python3 ~/Documents/GitHub/disciplina/skills/kt-channel-editor/tools/check_post.py posty/2026-08-17-vypusk-04/post.md --fakty posty/2026-08-17-vypusk-04/FAKTY.md --syryo posty/2026-08-17-vypusk-04/SYRYO.md --max-abzacev 5 --registr obychnyj   ждём ЗЕЛЁНЫЙ

НЕ ПОДМЕТАТЬ: posty/2026-08-17-vyazovskaya/**, vypuski/check_stil.py, check_idioma.py, karta_zamen.jsonl, oboroty_*, portret_objektov.json.gz, profil_stilya.json, svyazki.tsv, upravlenie.tsv, reestr_korpusa.tsv, docs/DOLGI.md, docs/fazy/stil.md, zhurnal/2026-08-15_vypusk-04/** - чужие сессии, идут параллельно.

Сообщение коммита для моей зоны - в развёртке, раздел 5. --push не забыть.
ЗАКРЫТО: 2026-08-17T20:58 · закрыта заходом kod_git-podmesti-vse: зона поста — коммит 0534836 (posty/2026-08-17-vypusk-04/** и vypuski/2026-08-15-vypusk-04/post.md), vypusk.md с тремя правками интервью — коммит 1125fa3 одним коммитом вместе с соседней сессией по решению §3 самой заявки. Виды пересобраны build_vypusk.py ДО коммита. Сверх заявки: выпуск 4 выложен на сайт (94c5bac, https://d1-d57.github.io/digest/4/) по решению владельца.

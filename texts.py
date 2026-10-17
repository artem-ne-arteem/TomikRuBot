"""Тексты бота на двух языках. Плейсхолдеры в фигурных скобках подставляются через tl()."""

RU = {
    # --- общее ---
    "start": (
        "📚 <b>Томик</b> — твоя книжная полка.\n\n"
        "Напиши название книги или ISBN либо пришли фото штрихкода, и я добавлю книгу на полку.\n\n"
        "/shelf — полка и теги\n"
        "/timer — таймер чтения\n"
        "/recs — что почитать дальше\n"
        "/stats — статистика\n"
        "/week — итоги недели\n"
        "/goal — цель на месяц\n"
        "/remind — напоминание почитать\n"
        "/read 30 — записать прочитанные страницы\n"
        "/add — добавить книгу вручную\n"
        "/import — импорт из Goodreads / Livelib (CSV)\n"
        "/export — заметки и цитаты\n"
        "/lang — язык\n\n"
        "👥 Добавь меня в группу с друзьями: рейтинг чтения, итоги дня и недели, общий челлендж."
    ),
    "cancelled": "Ок, отменил.",
    "not_found": "Не нашёл эту книгу.",
    "saved": "Сохранено ✅",
    "deleted": "🗑 Удалено.",
    "deleted_short": "Удалено",
    "status_updated": "Статус обновлён",
    "rating_saved": "Оценка сохранена",
    "unknown_author": "Автор неизвестен",
    "unrated": "не оценена",
    "lang_prompt": "🌐 Выбери язык / Choose language",
    "lang_set": "Язык: русский 🇷🇺",
    # --- поиск и добавление ---
    "searching": "🔎 Ищу...",
    "nothing_found": "Ничего не нашёл 😕 Попробуй другой запрос или добавь книгу вручную.",
    "pick_book": "Выбери свою книгу:",
    "search_expired": "Поиск устарел, повтори запрос",
    "manual_btn": "✍️ Добавить вручную",
    "manual_btn_list": "✍️ Моей книги нет, добавить вручную",
    "m_start_blank": "Добавляем книгу вручную. /cancel — отмена.",
    "m_start_query": "Добавляем вручную. Название: «{q}»\nНазвание не то? /cancel, затем /add.",
    "m_title": "📖 Как называется книга?",
    "m_author": "✍️ Кто автор? («-» если не знаешь)",
    "m_pages": "📄 Сколько страниц? («-» чтобы пропустить)",
    "m_year": "📅 Год издания? («-» чтобы пропустить)",
    "m_pages_err": "Напиши число страниц, например 320, или «-» чтобы пропустить.",
    "m_year_err": "Год — четыре цифры, например 1881, или «-» чтобы пропустить.",
    # --- карточка ---
    "card_added": "Добавлено на полку ✨",
    "card_status": "Статус: {s}",
    "card_pages": "📄 Страниц: {n}",
    "card_started": "Начата: {d}",
    "card_finished": "Закончена: {d}",
    "card_notes": "📝 Заметок: {n}",
    "card_rating": "Оценка: {r}",
    "pg_only": "стр. {p}",
    "pg_full": "{bar} {pct}% (стр. {p}/{n})",
    "b_progress": "📈 Прогресс",
    "b_notes": "📝 Заметки",
    "b_tags": "🏷 Теги",
    "b_edit": "✏️ Изменить",
    "b_delete": "🗑 Удалить",
    "b_back": "⬅️ К полке",
    "b_to_book": "⬅️ К книге",
    "st_want": "📌 Хочу прочитать",
    "st_reading": "📖 Читаю",
    "st_done": "✅ Прочитано",
    "st_dropped": "🚫 Брошено",
    # --- полка и теги ---
    "f_all": "📚 Все",
    "f_tags": "🏷 Теги",
    "shelf_title": "📚 Твоя полка",
    "shelf_empty": "Полка пока пуста. Напиши название книги, чтобы добавить.",
    "shelf_empty_filter": "Тут пока пусто.",
    "tags_title": "🏷 Теги книги «{title}»",
    "tags_empty": "Тегов пока нет. Добавь первый 👇",
    "tag_new": "➕ Новый тег",
    "tag_prompt": "Пришли теги через запятую, например: фантастика, на лето, подарить. /cancel — отмена",
    "tag_limit": "Не больше 10 тегов на книгу",
    "tags_none": "Тегов пока нет. Добавь их в карточке книги: «🏷 Теги»",
    "taglist_title": "🏷 Твои теги. Нажми, чтобы увидеть книги:",
    # --- редактирование ---
    "edit_title": "✏️ Что изменить в «{title}»?",
    "ef_title": "Название",
    "ef_author": "Автор",
    "ef_pages": "Страницы",
    "ef_year": "Год",
    "ef_cover": "Обложка",
    "ep_title": "Пришли новое название. /cancel — отмена",
    "ep_author": "Пришли автора («-» чтобы очистить). /cancel — отмена",
    "ep_pages": "Сколько страниц? («-» чтобы очистить). /cancel — отмена",
    "ep_year": "Год издания? («-» чтобы очистить). /cancel — отмена",
    "ep_cover": "Пришли фото обложки или ссылку на картинку (http...). /cancel — отмена",
    # --- прогресс и серии ---
    "prog_prompt": (
        "📈 «{title}»: до какой страницы дошёл?\n"
        "Напиши 120 (страница), 45% (процент) или 120/350 (страница/всего). /cancel — отмена"
    ),
    "prog_prompt_nopages": (
        "📈 «{title}»: до какой страницы дошёл?\n"
        "Напиши 120/350 (страница/всего) или просто 120. /cancel — отмена"
    ),
    "prog_need_pages": "Я не знаю, сколько в книге страниц. Напиши так: 120/350 (страница/всего).",
    "prog_updated": "Прогресс обновлён ✅",
    "book_done": "🎉 Книга прочитана!",
    "streak_line": "🔥 Серия: {n} дн. подряд",
    "read_usage": "Напиши число страниц, например: /read 30",
    "read_ok": "✅ +{n} стр. Сегодня всего: {total}",
    # --- заметки ---
    "notes_title": "📝 <b>{title}</b>: заметки и цитаты",
    "notes_empty": "Пока пусто. Добавь первую цитату или мысль 👇",
    "notes_more": "Показаны последние {k} из {n}. Все заметки: /export",
    "note_add_quote": "➕ Цитата",
    "note_add_note": "➕ Заметка",
    "note_hint_quote": "Пришли цитату. Если знаешь страницу, допиши в конце: «стр. 45». /cancel — отмена",
    "note_hint_note": "Пришли текст заметки. /cancel — отмена",
    "note_page": " (стр. {p})",
    "export_head": "# Заметки и цитаты — Томик",
    "export_empty": "Заметок пока нет. Открой книгу и нажми «📝 Заметки».",
    "export_caption": "📝 Все твои заметки и цитаты",
    # --- цель ---
    "goal_progress": "🎯 Цель на месяц: {n}/{g} {bar}",
    "goal_none": "🎯 Цель на месяц не задана.",
    "goal_hint": "Выбери, сколько книг хочешь прочитать за месяц, или напиши /goal 5",
    "goal_set": "🎯 Цель на месяц установлена: {n}",
    "goal_off": "Цель выключена.",
    "goal_btn_off": "🚫 Без цели",
    # --- напоминания ---
    "rem_usage": "Время в формате ЧЧ:ММ, например /remind 20:30",
    "rem_set": "🔔 Буду напоминать каждый день в {t}.",
    "rem_cur": "Сейчас напоминание: {t}",
    "rem_off_now": "Напоминание выключено.",
    "rem_pick": "Выбери время или напиши своё: /remind 20:30",
    "rem_off": "🔕 Напоминание выключено.",
    "rem_btn_off": "🔕 Выключить",
    "rem_title": "📖 <b>Время почитать!</b>",
    "rem_in_progress": "Сейчас в процессе:",
    "rem_empty": "Напиши название книги, и я добавлю её на полку.",
    "rem_streak": "🔥 Серия {n} дн. — прочитай хоть страницу, чтобы не прервать!",
    # --- статистика ---
    "st_head": "📊 <b>Статистика</b>",
    "st_shelf": "📚 Полка: {s}",
    "st_avg": "⭐ Средняя оценка: {a}",
    "st_avg_none": "⭐ Оценок пока нет",
    "st_month": "📅 <b>{m}</b>: книг {b}, страниц {p}",
    "st_year": "🗓 <b>Год</b>: книг {b}, страниц {p}",
    "st_total": "📄 Всего страниц: {p} · в среднем {a}/день за 30 дней",
    "st_streak": "🔥 Серия: {c} дн. (рекорд {b})",
    "st_goal_none": "🎯 Цель на месяц не задана (/goal)",
    "st_authors": "✍️ Любимые авторы: {l}",
    "st_genres": "🎭 Жанры: {l}",
    "st_tags": "🏷 Теги: {l}",
    "st_months": "📈 Прочитано книг по месяцам:",
    # --- группы ---
    "g_hello": (
        "📚 Привет! Я Томик, книжный бот.\n\n"
        "Чтобы попасть в рейтинг чтения, напиши /join. Страницы считаются, когда ты "
        "обновляешь прогресс у меня в личке (@{bot}) или пишешь здесь /read 30.\n\n"
        "Каждый вечер я буду показывать, кто сколько прочитал и кто лидирует. "
        "/top — рейтинг прямо сейчас."
    ),
    "g_help": (
        "📚 <b>Томик</b>: чтение в группе\n\n"
        "/join — участвовать в рейтинге\n"
        "/leave — выйти из рейтинга\n"
        "/read 30 — записать прочитанные страницы\n"
        "/top — рейтинг (сегодня, неделя, месяц)\n"
        "/challenge 3000 — общая цель группы на месяц (админы)\n"
        "/weekly on|off — итоги недели по понедельникам (админы)\n"
        "/digest 21:00 — время вечерних итогов (админы), /digest off — выключить\n"
        "/lang — язык группы (админы)\n\n"
        "Прогресс по своим книгам веди у меня в личке: @{bot}"
    ),
    "g_joined": "✅ {name} в рейтинге! Пиши /read 30 после чтения или обновляй прогресс у меня в личке: @{bot}",
    "g_already": "{name}, ты уже в рейтинге 😉",
    "g_left": "👋 {name} вышел из рейтинга.",
    "g_no_members": "Пока в рейтинге никого. Напиши /join, чтобы участвовать!",
    "g_head_day": "📊 <b>Итоги дня ({d})</b>",
    "g_head_week": "📊 <b>Неделя</b> (с понедельника)",
    "g_head_month": "📊 <b>Месяц</b>",
    "g_nobody": "Пока никто не записал страницы 😴",
    "g_pages": "{n} стр.",
    "g_idle": "💤 Пока без страниц: {names}",
    "g_leader_week": "🏆 Лидер недели: {name} — {n} стр.",
    "g_leader_month": "🏆 Лидер месяца: {name} — {n} стр.",
    "g_read_ok": "✅ {name}: +{n} стр. Сегодня: {total}",
    "g_digest_cur": "Итоги дня выходят в {t}. Изменить: /digest 20:00 или /digest off (админы)",
    "g_digest_off": "Ежедневные итоги выключены. Включить: /digest 21:00 (админы)",
    "g_digest_off_set": "🔕 Ежедневные итоги выключены.",
    "g_digest_set": "🔔 Итоги дня будут выходить каждый день в {t}.",
    "g_digest_usage": "Время в формате ЧЧ:ММ, например /digest 21:00, или /digest off",
    "g_admin_only": "Это могут только администраторы группы.",
    "per_day": "Сегодня",
    "per_week": "Неделя",
    "per_month": "Месяц",
    # --- меню команд ---
    "cmd_shelf": "Моя полка",
    "cmd_stats": "Статистика",
    "cmd_goal": "Цель на месяц",
    "cmd_remind": "Напоминание почитать",
    "cmd_add": "Добавить книгу вручную",
    "cmd_read": "Записать прочитанные страницы",
    "cmd_export": "Экспорт заметок (Markdown)",
    "cmd_lang": "Язык",
    "cmd_cancel": "Отмена ввода",
    "cmd_join": "Участвовать в рейтинге",
    "cmd_leave": "Выйти из рейтинга",
    "cmd_top": "Рейтинг чтения",
    "cmd_digest": "Время вечерних итогов",
    # --- штрихкоды и ISBN ---
    "scan_working": "📷 Ищу штрихкод...",
    "scan_nolib": "Для штрихкодов нужны библиотеки: pip install zxing-cpp pillow. А пока можно прислать ISBN текстом.",
    "scan_fail": "Не смог прочитать штрихкод 😕 Сфотографируй ближе и ровнее (лучше отправить файлом, без сжатия) или пришли ISBN текстом.",
    "nothing_found_isbn": "По ISBN {isbn} ничего не нашёл 😕 Добавь книгу вручную.",
    "doc_unknown": "Я принимаю CSV для импорта (/import) и фото штрихкодов.",
    # --- таймер ---
    "b_timer": "⏱ Таймер",
    "timer_status": "⏱ <b>Идёт чтение</b>\n«{title}»\nС {since} · {m}",
    "timer_btn_stop": "⏹ Стоп",
    "timer_btn_refresh": "🔄 Обновить",
    "timer_btn_cancel": "✖ Отменить",
    "timer_already": "У тебя уже идёт таймер.",
    "timer_done": "⏹ Готово! Читал {m}.",
    "timer_capped": "Таймер шёл очень долго, засчитал максимум 4 часа.",
    "timer_skip_hint": "Чтобы пропустить, пришли «-».",
    "timer_cancelled": "Таймер отменён.",
    "timer_gone": "Этот таймер уже остановлен.",
    "timer_none": "Нет книг в статусе «Читаю». Открой книгу и нажми «⏱ Таймер».",
    "timer_pick": "⏱ Выбери книгу для таймера:",
    "fmt_hm": "{h} ч {m} мин",
    "fmt_m": "{m} мин",
    "skipped": "Ок, пропустил.",
    "st_time": "⏱ Время чтения: {m} за месяц · {a} всего",
    # --- рекомендации ---
    "recs_wait": "🔎 Подбираю книги...",
    "recs_title_google": "🎯 <b>Что почитать дальше</b> (по твоим оценкам и жанрам):",
    "recs_title_ai": "🤖 <b>Что почитать дальше</b> (подборка ИИ):",
    "recs_need_data": "Пока мало данных 🙈 Добавь несколько прочитанных книг и поставь оценки 4–5 тем, что понравились, и я подберу рекомендации.",
    "recs_why_author": "Ты высоко оценил автора: {a}",
    "recs_why_genre": "Похоже на то, что ты читаешь: {g}",
    "recs_fail": "Не получилось подобрать рекомендации, попробуй позже.",
    # --- итоги недели (личные) ---
    "weekdays": "Пн Вт Ср Чт Пт Сб Вс",
    "wk_head": "📅 <b>Неделя {a} – {b}</b>",
    "wk_total": "📄 Страниц: {p} · ⏱ {tm}",
    "wk_books": "📚 Закончено книг: {n}",
    "wk_diff": "📊 К прошлой неделе: {d} стр.",
    "wk_btn_this": "Эта неделя",
    "wk_btn_last": "Прошлая неделя",
    "wk_on": "🔔 Итоги недели будут приходить по понедельникам в 10:00.",
    "wk_off": "🔕 Итоги недели по понедельникам выключены.",
    "wk_hint": "Присылать итоги каждый понедельник: /week on (выключить: /week off)",
    # --- итоги недели и челлендж (группы) ---
    "gw_head": "📅 <b>Итоги недели {a} – {b}</b>",
    "gw_empty": "На прошлой неделе никто не записал страницы 😴",
    "gw_total": "📄 Всего прочитано: {p} стр., читателей: {n}",
    "gw_books": "📚 Закончено книг: {n}",
    "gw_streak": "🔥 Лучшая серия: {name} — {n} дн.",
    "g_weekly_on": "🔔 Итоги недели будут выходить по понедельникам в 10:00.",
    "g_weekly_off": "🔕 Итоги недели выключены.",
    "g_weekly_cur_on": "Итоги недели включены (понедельник, 10:00). Выключить: /weekly off (админы)",
    "g_weekly_cur_off": "Итоги недели выключены. Включить: /weekly on (админы)",
    "ch_head": "🎯 <b>Челлендж группы</b>",
    "ch_progress": "{done}/{target} стр. {bar} {pct}%",
    "ch_left": "📆 Осталось дней: {days}, нужно ~{per} стр. в день на всех",
    "ch_top": "🏅 Вклад: {l}",
    "ch_done": "🎉 Цель месяца выполнена!",
    "ch_set": "🎯 Челлендж на месяц: {n} стр. на всю группу.",
    "ch_off": "Челлендж выключен.",
    "ch_none": "Челлендж не задан. Админы: /challenge 3000",
    "ch_usage": "Напиши цель в страницах, например /challenge 3000, или /challenge off",
    "ch_complete": "🎉 <b>Челлендж выполнен!</b> Группа прочитала {target} стр.",
    # --- импорт ---
    "import_help": (
        "📥 <b>Импорт книг</b>\n\n"
        "Пришли мне CSV-файл, и я перенесу твою библиотеку: названия, авторов, оценки, статусы, даты прочтения и теги.\n\n"
        "<b>Goodreads:</b> My Books → Import and export → Export Library, скачай CSV.\n"
        "<b>Livelib и другие сервисы:</b> подойдёт любой CSV с колонками вроде «Название», «Автор», «Оценка», «Статус».\n\n"
        "Дубли не добавляются, а страницы импортированных книг не идут в рейтинги и серии."
    ),
    "import_working": "📥 Импортирую...",
    "import_big": "Файл слишком большой (максимум 5 МБ).",
    "import_bad_format": "Не нашёл в файле колонку с названиями книг (Title / Название). Проверь, что это CSV-экспорт.",
    "import_done": "✅ Импорт завершён.\nДобавлено: {added}\nПропущено дублей: {dups}\nНе удалось разобрать: {bad}",
    # --- меню команд ---
    "cmd_timer": "Таймер чтения",
    "cmd_recs": "Что почитать дальше",
    "cmd_week": "Итоги недели",
    "cmd_import": "Импорт из CSV",
    "cmd_challenge": "Челлендж группы",
    "cmd_weekly": "Итоги недели в группе",
}

EN = {
    # --- general ---
    "start": (
        "📚 <b>Tomik</b>: your bookshelf.\n\n"
        "Send a book title or ISBN, or a photo of the barcode, and I'll add the book to your shelf.\n\n"
        "/shelf: shelf and tags\n"
        "/timer: reading timer\n"
        "/recs: what to read next\n"
        "/stats: statistics\n"
        "/week: weekly recap\n"
        "/goal: monthly goal\n"
        "/remind: reading reminder\n"
        "/read 30: log pages you read\n"
        "/add: add a book manually\n"
        "/import: import from Goodreads / Livelib (CSV)\n"
        "/export: notes and quotes\n"
        "/lang: language\n\n"
        "👥 Add me to a group with friends: reading leaderboard, daily and weekly summaries, shared challenge."
    ),
    "cancelled": "Okay, cancelled.",
    "not_found": "Couldn't find that book.",
    "saved": "Saved ✅",
    "deleted": "🗑 Deleted.",
    "deleted_short": "Deleted",
    "status_updated": "Status updated",
    "rating_saved": "Rating saved",
    "unknown_author": "Unknown author",
    "unrated": "not rated",
    "lang_prompt": "🌐 Выбери язык / Choose language",
    "lang_set": "Language: English 🇬🇧",
    # --- search and adding ---
    "searching": "🔎 Searching...",
    "nothing_found": "Nothing found 😕 Try another query or add the book manually.",
    "pick_book": "Pick your book:",
    "search_expired": "Search expired, please search again",
    "manual_btn": "✍️ Add manually",
    "manual_btn_list": "✍️ My book isn't here, add manually",
    "m_start_blank": "Adding a book manually. /cancel to stop.",
    "m_start_query": "Adding manually. Title: «{q}»\nWrong title? /cancel, then /add.",
    "m_title": "📖 What's the book called?",
    "m_author": "✍️ Who's the author? (\"-\" if unknown)",
    "m_pages": "📄 How many pages? (\"-\" to skip)",
    "m_year": "📅 Year of publication? (\"-\" to skip)",
    "m_pages_err": "Send the number of pages, e.g. 320, or \"-\" to skip.",
    "m_year_err": "Year should be four digits, e.g. 1881, or \"-\" to skip.",
    # --- card ---
    "card_added": "Added to your shelf ✨",
    "card_status": "Status: {s}",
    "card_pages": "📄 Pages: {n}",
    "card_started": "Started: {d}",
    "card_finished": "Finished: {d}",
    "card_notes": "📝 Notes: {n}",
    "card_rating": "Rating: {r}",
    "pg_only": "p. {p}",
    "pg_full": "{bar} {pct}% (p. {p}/{n})",
    "b_progress": "📈 Progress",
    "b_notes": "📝 Notes",
    "b_tags": "🏷 Tags",
    "b_edit": "✏️ Edit",
    "b_delete": "🗑 Delete",
    "b_back": "⬅️ To shelf",
    "b_to_book": "⬅️ To book",
    "st_want": "📌 Want to read",
    "st_reading": "📖 Reading",
    "st_done": "✅ Finished",
    "st_dropped": "🚫 Dropped",
    # --- shelf and tags ---
    "f_all": "📚 All",
    "f_tags": "🏷 Tags",
    "shelf_title": "📚 Your shelf",
    "shelf_empty": "Your shelf is empty. Send a book title to add one.",
    "shelf_empty_filter": "Nothing here yet.",
    "tags_title": "🏷 Tags for «{title}»",
    "tags_empty": "No tags yet. Add the first one 👇",
    "tag_new": "➕ New tag",
    "tag_prompt": "Send tags separated by commas, e.g.: sci-fi, summer, gift. /cancel to stop",
    "tag_limit": "No more than 10 tags per book",
    "tags_none": "No tags yet. Add them in a book card: «🏷 Tags»",
    "taglist_title": "🏷 Your tags. Tap one to see its books:",
    # --- editing ---
    "edit_title": "✏️ What do you want to change in «{title}»?",
    "ef_title": "Title",
    "ef_author": "Author",
    "ef_pages": "Pages",
    "ef_year": "Year",
    "ef_cover": "Cover",
    "ep_title": "Send the new title. /cancel to stop",
    "ep_author": "Send the author (\"-\" to clear). /cancel to stop",
    "ep_pages": "How many pages? (\"-\" to clear). /cancel to stop",
    "ep_year": "Year of publication? (\"-\" to clear). /cancel to stop",
    "ep_cover": "Send a cover photo or an image link (http...). /cancel to stop",
    # --- progress and streaks ---
    "prog_prompt": (
        "📈 «{title}»: which page are you on?\n"
        "Send 120 (page), 45% (percent) or 120/350 (page/total). /cancel to stop"
    ),
    "prog_prompt_nopages": (
        "📈 «{title}»: which page are you on?\n"
        "Send 120/350 (page/total) or just 120. /cancel to stop"
    ),
    "prog_need_pages": "I don't know how many pages the book has. Send it like this: 120/350 (page/total).",
    "prog_updated": "Progress updated ✅",
    "book_done": "🎉 Book finished!",
    "streak_line": "🔥 Day streak: {n}",
    "read_usage": "Send the number of pages, e.g.: /read 30",
    "read_ok": "✅ +{n} p. Total today: {total}",
    # --- notes ---
    "notes_title": "📝 <b>{title}</b>: notes and quotes",
    "notes_empty": "Nothing yet. Add your first quote or thought 👇",
    "notes_more": "Showing the last {k} of {n}. All notes: /export",
    "note_add_quote": "➕ Quote",
    "note_add_note": "➕ Note",
    "note_hint_quote": "Send the quote. If you know the page, add it at the end: \"p. 45\". /cancel to stop",
    "note_hint_note": "Send the note text. /cancel to stop",
    "note_page": " (p. {p})",
    "export_head": "# Notes and quotes — Tomik",
    "export_empty": "No notes yet. Open a book and tap «📝 Notes».",
    "export_caption": "📝 All your notes and quotes",
    # --- goal ---
    "goal_progress": "🎯 Monthly goal: {n}/{g} {bar}",
    "goal_none": "🎯 No monthly goal set.",
    "goal_hint": "Pick how many books you want to finish per month, or send /goal 5",
    "goal_set": "🎯 Monthly goal set: {n}",
    "goal_off": "Goal turned off.",
    "goal_btn_off": "🚫 No goal",
    # --- reminders ---
    "rem_usage": "Time format is HH:MM, e.g. /remind 20:30",
    "rem_set": "🔔 I'll remind you every day at {t}.",
    "rem_cur": "Current reminder: {t}",
    "rem_off_now": "Reminder is off.",
    "rem_pick": "Pick a time or send your own: /remind 20:30",
    "rem_off": "🔕 Reminder turned off.",
    "rem_btn_off": "🔕 Turn off",
    "rem_title": "📖 <b>Time to read!</b>",
    "rem_in_progress": "Currently reading:",
    "rem_empty": "Send a book title and I'll add it to your shelf.",
    "rem_streak": "🔥 {n}-day streak: read at least a page to keep it going!",
    # --- statistics ---
    "st_head": "📊 <b>Statistics</b>",
    "st_shelf": "📚 Shelf: {s}",
    "st_avg": "⭐ Average rating: {a}",
    "st_avg_none": "⭐ No ratings yet",
    "st_month": "📅 <b>{m}</b>: books {b}, pages {p}",
    "st_year": "🗓 <b>This year</b>: books {b}, pages {p}",
    "st_total": "📄 Total pages: {p} · avg {a}/day over 30 days",
    "st_streak": "🔥 Day streak: {c} (record {b})",
    "st_goal_none": "🎯 No monthly goal set (/goal)",
    "st_authors": "✍️ Favorite authors: {l}",
    "st_genres": "🎭 Genres: {l}",
    "st_tags": "🏷 Tags: {l}",
    "st_months": "📈 Books finished by month:",
    # --- groups ---
    "g_hello": (
        "📚 Hi! I'm Tomik, a book bot.\n\n"
        "To join the reading leaderboard, send /join. Pages count when you update your progress "
        "in a private chat with me (@{bot}) or send /read 30 here.\n\n"
        "Every evening I'll show who read how much and who's leading. "
        "/top shows the leaderboard right now."
    ),
    "g_help": (
        "📚 <b>Tomik</b>: group reading\n\n"
        "/join: join the leaderboard\n"
        "/leave: leave the leaderboard\n"
        "/read 30: log pages you read\n"
        "/top: leaderboard (today, week, month)\n"
        "/challenge 3000: shared monthly goal for the group (admins)\n"
        "/weekly on|off: Monday weekly summary (admins)\n"
        "/digest 21:00: evening summary time (admins), /digest off to disable\n"
        "/lang: group language (admins)\n\n"
        "Track your own books in a private chat with me: @{bot}"
    ),
    "g_joined": "✅ {name} is on the leaderboard! Send /read 30 after reading or update progress in my private chat: @{bot}",
    "g_already": "{name}, you're already on the leaderboard 😉",
    "g_left": "👋 {name} left the leaderboard.",
    "g_no_members": "Nobody is on the leaderboard yet. Send /join to take part!",
    "g_head_day": "📊 <b>Daily summary ({d})</b>",
    "g_head_week": "📊 <b>This week</b> (since Monday)",
    "g_head_month": "📊 <b>This month</b>",
    "g_nobody": "Nobody has logged pages yet 😴",
    "g_pages": "{n} p.",
    "g_idle": "💤 No pages yet: {names}",
    "g_leader_week": "🏆 Leader of the week: {name} — {n} p.",
    "g_leader_month": "🏆 Leader of the month: {name} — {n} p.",
    "g_read_ok": "✅ {name}: +{n} p. Today: {total}",
    "g_digest_cur": "The daily summary goes out at {t}. Change: /digest 20:00 or /digest off (admins)",
    "g_digest_off": "Daily summaries are off. Turn on: /digest 21:00 (admins)",
    "g_digest_off_set": "🔕 Daily summaries turned off.",
    "g_digest_set": "🔔 The daily summary will go out every day at {t}.",
    "g_digest_usage": "Time format is HH:MM, e.g. /digest 21:00, or /digest off",
    "g_admin_only": "Only group admins can do this.",
    "per_day": "Today",
    "per_week": "Week",
    "per_month": "Month",
    # --- command menu ---
    "cmd_shelf": "My shelf",
    "cmd_stats": "Statistics",
    "cmd_goal": "Monthly goal",
    "cmd_remind": "Reading reminder",
    "cmd_add": "Add a book manually",
    "cmd_read": "Log pages you read",
    "cmd_export": "Export notes (Markdown)",
    "cmd_lang": "Language",
    "cmd_cancel": "Cancel input",
    "cmd_join": "Join the leaderboard",
    "cmd_leave": "Leave the leaderboard",
    "cmd_top": "Reading leaderboard",
    "cmd_digest": "Evening summary time",
    # --- barcodes and ISBN ---
    "scan_working": "📷 Looking for a barcode...",
    "scan_nolib": "Barcodes need extra libraries: pip install zxing-cpp pillow. Meanwhile, you can send the ISBN as text.",
    "scan_fail": "Couldn't read the barcode 😕 Take a closer, straighter photo (sending it as a file avoids compression) or send the ISBN as text.",
    "nothing_found_isbn": "Nothing found for ISBN {isbn} 😕 Add the book manually.",
    "doc_unknown": "I accept CSV files for import (/import) and barcode photos.",
    # --- timer ---
    "b_timer": "⏱ Timer",
    "timer_status": "⏱ <b>Reading now</b>\n«{title}»\nSince {since} · {m}",
    "timer_btn_stop": "⏹ Stop",
    "timer_btn_refresh": "🔄 Refresh",
    "timer_btn_cancel": "✖ Cancel",
    "timer_already": "You already have a timer running.",
    "timer_done": "⏹ Done! You read for {m}.",
    "timer_capped": "The timer ran very long, so I counted 4 hours at most.",
    "timer_skip_hint": "Send \"-\" to skip.",
    "timer_cancelled": "Timer cancelled.",
    "timer_gone": "That timer is already stopped.",
    "timer_none": "No books marked «Reading». Open a book and tap «⏱ Timer».",
    "timer_pick": "⏱ Pick a book for the timer:",
    "fmt_hm": "{h} h {m} min",
    "fmt_m": "{m} min",
    "skipped": "Okay, skipped.",
    "st_time": "⏱ Reading time: {m} this month · {a} total",
    # --- recommendations ---
    "recs_wait": "🔎 Picking books...",
    "recs_title_google": "🎯 <b>What to read next</b> (based on your ratings and genres):",
    "recs_title_ai": "🤖 <b>What to read next</b> (AI picks):",
    "recs_need_data": "Not enough data yet 🙈 Add a few finished books and rate the ones you liked 4–5, and I'll find recommendations.",
    "recs_why_author": "You rated this author highly: {a}",
    "recs_why_genre": "Similar to what you read: {g}",
    "recs_fail": "Couldn't put recommendations together, please try later.",
    # --- weekly recap (personal) ---
    "weekdays": "Mon Tue Wed Thu Fri Sat Sun",
    "wk_head": "📅 <b>Week {a} – {b}</b>",
    "wk_total": "📄 Pages: {p} · ⏱ {tm}",
    "wk_books": "📚 Books finished: {n}",
    "wk_diff": "📊 vs last week: {d} p.",
    "wk_btn_this": "This week",
    "wk_btn_last": "Last week",
    "wk_on": "🔔 I'll send your weekly recap on Mondays at 10:00.",
    "wk_off": "🔕 Monday recaps turned off.",
    "wk_hint": "Get a recap every Monday: /week on (turn off: /week off)",
    # --- weekly recap and challenge (groups) ---
    "gw_head": "📅 <b>Weekly summary {a} – {b}</b>",
    "gw_empty": "Nobody logged pages last week 😴",
    "gw_total": "📄 Total read: {p} p., readers: {n}",
    "gw_books": "📚 Books finished: {n}",
    "gw_streak": "🔥 Best streak: {name} — {n} days",
    "g_weekly_on": "🔔 The weekly summary will go out on Mondays at 10:00.",
    "g_weekly_off": "🔕 Weekly summaries turned off.",
    "g_weekly_cur_on": "Weekly summaries are on (Monday, 10:00). Turn off: /weekly off (admins)",
    "g_weekly_cur_off": "Weekly summaries are off. Turn on: /weekly on (admins)",
    "ch_head": "🎯 <b>Group challenge</b>",
    "ch_progress": "{done}/{target} p. {bar} {pct}%",
    "ch_left": "📆 Days left: {days}, the group needs ~{per} p. per day",
    "ch_top": "🏅 Contributions: {l}",
    "ch_done": "🎉 Monthly goal reached!",
    "ch_set": "🎯 Monthly challenge: {n} pages for the whole group.",
    "ch_off": "Challenge turned off.",
    "ch_none": "No challenge set. Admins: /challenge 3000",
    "ch_usage": "Send the goal in pages, e.g. /challenge 3000, or /challenge off",
    "ch_complete": "🎉 <b>Challenge complete!</b> The group read {target} pages.",
    # --- import ---
    "import_help": (
        "📥 <b>Import books</b>\n\n"
        "Send me a CSV file and I'll move your library over: titles, authors, ratings, statuses, read dates and tags.\n\n"
        "<b>Goodreads:</b> My Books → Import and export → Export Library, download the CSV.\n"
        "<b>Livelib and others:</b> any CSV with columns like Title, Author, Rating, Status will do.\n\n"
        "Duplicates are skipped, and pages of imported books don't count towards leaderboards or streaks."
    ),
    "import_working": "📥 Importing...",
    "import_big": "The file is too large (5 MB max).",
    "import_bad_format": "I couldn't find a book title column (Title / Название). Make sure it's a CSV export.",
    "import_done": "✅ Import finished.\nAdded: {added}\nDuplicates skipped: {dups}\nCouldn't parse: {bad}",
    # --- command menu ---
    "cmd_timer": "Reading timer",
    "cmd_recs": "What to read next",
    "cmd_week": "Weekly recap",
    "cmd_import": "Import from CSV",
    "cmd_challenge": "Group challenge",
    "cmd_weekly": "Weekly group summary",
}

TEXTS = {"ru": RU, "en": EN}


def tl(lang: str, key: str, **kw) -> str:
    """Текст по ключу на нужном языке (если перевода нет, берём русский)."""
    s = TEXTS.get(lang, RU).get(key)
    if s is None:
        s = RU[key]
    return s.format(**kw) if kw else s
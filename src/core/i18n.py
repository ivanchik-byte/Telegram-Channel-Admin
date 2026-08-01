import logging
from src.core.config import settings

_logger = logging.getLogger("TG_Admin")

TRANSLATIONS = {
    'ru': {
        # --- Buttons (moderation card) ---
        'btn_publish': '✅ Опубликовать',
        'btn_reject': '❌ Отклонить',
        'btn_edit': '📝 Текст',
        'btn_change_media': '🖼 Медиа',
        'btn_ai_edit': '✨ ИИ Редактор',

        # --- Moderation messages ---
        'msg_access_denied': 'Доступ запрещен',
        'msg_already_processed': 'Пост уже обработан или не найден.',
        'msg_no_text_to_publish': 'Ошибка: нет текста для публикации.',
        'msg_published': '<b>Опубликовано</b>',
        'msg_published_alert': 'Опубликовано!',
        'msg_publish_error': 'Ошибка при публикации.',
        'msg_rejected': '<b>Отклонено</b>',
        'msg_rejected_alert': 'Пост отклонен.',
        'msg_edit_instruction': 'Для редактирования скопируйте текст ниже, внесите правки и отправьте команду:\n<code>/edit {post_id} Ваш исправленный текст</code>',
        'msg_edit_wrong_format': 'Неверный формат команды. Используйте:\n/edit <ID_поста> <Новый текст>',
        'msg_edit_id_not_number': 'Неверный формат или ID не является числом.',
        'msg_edit_post_not_found': 'Пост не найден или уже не находится на модерации (возможно, уже обработан).',
        'msg_edit_success': 'Текст обновлен! Новая карточка отправлена.',
        'card_new_post': '<b>Новый пост из источника {channel_id}</b>',
        'card_edited_post': '<b>Новый пост из источника {channel_id} (Исправлено)</b>',

        # --- Reply keyboard buttons ---
        'kb_moderation': '\U0001f4cb Модерация',
        'kb_status': '\U0001f4ca Статус',
        'kb_parse_now': '\U0001f504 Парсить сейчас',
        'kb_find_best': '\u2b50 Найти лучший пост',
        'kb_pause_8h': '\u23f8 Пауза 8ч',
        'kb_resume': '\u25b6 Возобновить',
        'kb_clear_all': '🗑 Очистить все',
        'kb_clear_db': '🗄 Очистить БД',
        'kb_input_placeholder': 'Выберите действие...',

        # --- Inline keyboard buttons (status dashboard) ---
        'ib_moderation': '📋 Модерация',
        'ib_refresh_status': '🔄 Обновить статус',
        'ib_parse_now': '⚡️ Парсить сейчас',
        'ib_find_best': '⭐️ Найти лучший пост',
        'ib_pause_8h': '⏸ Пауза 8ч',
        'ib_resume': '▶️ Возобновить',
        'ib_clear_all': '🗑 Очистить все',
        'ib_clear_db': '🗄 Очистить БД',

        # --- action_by label ---
        'action_by': '👤 Действие от: {username}',
        'publish_error': '❌ Ошибка публикации: {error}',
        'extra_links': '<b>Дополнительные ссылки:</b>',
        'source_link': '<b>Источник:</b> <a href=\'{url}\'>Перейти к оригиналу</a>',

        # --- /start ---
        'start_access_denied': 'Доступ запрещен. Ваш Telegram ID: <code>{user_id}</code>. Добавьте его в ADMIN_IDS в файле .env.\n\nЕсли вы нашли этого бота случайно, вы можете ознакомиться с проектом на GitHub:\nhttps://github.com/ivanchik-byte/Telegram-Channel-Admin',
        'start_welcome': '<b>Привет! Я бот-модератор каналов.</b>\n\nИспользуйте кнопки меню внизу экрана для быстрого управления или отправьте команду /help для полной справки.',

        # --- Moderation flow ---
        'mod_extracting': '🔄 Извлекаю следующий пост из очереди и запускаю ИИ-рерайт...',
        'mod_ai_failed': '❌ Не удалось переписать пост с помощью ИИ.',
        'mod_already_processing': 'Пост уже обрабатывается. Пожалуйста, нажмите «Модерация» еще раз через пару секунд.',
        'mod_queue_empty': 'Очередь модерации и входящих постов пуста.',
        'mod_remaining': 'На модерации осталось постов: {count}',
        'edit_error_id': 'Ошибка ID',
        'edit_post_processed': 'Пост уже обработан',
        'edit_send_new_text': 'Пришлите новый текст для поста {post_id}:',
        'edit_text_not_received': 'Текст не получен или ID потерян. Отмена.',
        'edit_post_not_found': 'Пост уже обработан или не найден.',

        # --- /mode ---
        'mode_usage': 'Использование: /mode auto | curation\n\nauto: 1 пост на модерации, 5 в очереди.\ncuration: тихий сбор всех постов (команда /best).',
        'mode_changed': 'Режим успешно изменен на: <b>{mode}</b>',

        # --- /queue ---
        'queue_current': 'Текущий лимит очереди публикации: <b>{limit}</b> постов.\n\nИспользование: <code>/queue [число]</code> (например: /queue 20).',
        'queue_invalid': 'Пожалуйста, укажите корректное число от 1 до 1000.',
        'queue_changed': 'Лимит очереди публикации успешно изменен на: <b>{limit}</b> постов.',

        # --- /best ---
        'best_invalid_time': 'Неверный формат времени. Пример: /best 12h',
        'best_searching': 'Запущен поиск лучшего поста за последние {hours} часов. Ожидайте...',

        # --- /interval ---
        'interval_usage': 'Использование: /interval <min>-<max> (например: /interval 20m-50m)\nИли /interval 0 для отключения.',
        'interval_disabled': 'Интервал успешно отключен! Посты будут выходить по мере готовности.',
        'interval_set': '<b>Интервал успешно установлен:</b>\nот <b>{min_val}</b> до <b>{max_val}</b>.',
        'interval_invalid': 'Неверный формат. Пример: /interval 20m-50m или /interval 30-60',

        # --- /pause, /resume ---
        'pause_forever': '<b>Бот поставлен на ВЕЧНУЮ паузу.</b>\nПарсер отключен. Для возобновления работы отправьте /resume.',
        'pause_timed': '<b>Бот поставлен на паузу на {duration}</b> (до {until} UTC).',
        'pause_invalid_time': 'Неверный формат времени. Пример: /pause 8h или /pause 30s',
        'resume_done': '<b>Бот возобновил работу.</b> Пауза снята, парсер активен.',

        # --- /status ---
        'status_title': '<b>Текущий статус бота:</b>\n',
        'status_mode': '• <b>Режим:</b> <code>{mode}</code>',
        'status_interval': '• <b>Интервал:</b> <code>{min_val} - {max_val}</code>',
        'status_pause_forever': '• <b>Пауза:</b> <code>Навсегда</code>',
        'status_pause_until': '• <b>Пауза до:</b> <code>{until} UTC</code> (~{remaining})',
        'status_active': '• <b>Пауза:</b> <code>Активен</code>',
        'status_next_post': '• <b>Следующий пост через:</b> <code>{delay}</code>',
        'status_moderating': '• <b>На модерации:</b> <code>{count} / 1</code>',
        'status_queued': '• <b>В очереди (auto):</b> <code>{count} / {limit}</code>',
        'status_accumulated': '• <b>В корзине (curation):</b> <code>{count}</code>',
        'status_updated': 'Статус обновлен',

        # --- /clear, /clear_db ---
        'clear_done': '<b>Очередь публикации, модерация и кураторская корзина полностью очищены.</b>',
        'clear_db_done': '<b>База данных полностью очищена.</b> Удалено записей: {count}.',
        'clear_confirm': 'Вы действительно хотите полностью очистить очередь публикации, модерацию и кураторскую корзину?',
        'clear_confirm_yes': 'Да, очистить',
        'clear_confirm_no': 'Отмена',
        'clear_cancelled': 'Очистка отменена',
        'clear_db_confirm': 'Вы действительно хотите полностью очистить БАЗУ ДАННЫХ постов? Это действие удалит всю историю постов.',
        'clear_db_confirm_yes': 'Да, очистить БД',
        'clear_db_confirm_no': 'Отмена',
        'clear_db_cancelled': 'Отменено',

        # --- /help ---
        'help_text': (
            '<b>Справка по командам бота-модератора</b>\n\n'
            '<b>Интерактивные кнопки меню:</b>\n'
            '- Модерация — показать один старейший пост, ожидающий проверки.\n'
            '- Парсить сейчас — принудительно загрузить последние 10 сообщений из каналов.\n'
            '- Найти лучший пост — загрузить посты, сбросить интервал и выбрать ТОП-6 (1 на модерацию, 5 в очередь).\n'
            '- Статус — настройки, режим работы, текущая очередь и задержки.\n'
            '- Возобновить / Пауза 8ч / Очистить queue.\n\n'
            '<b>Управление режимами:</b>\n'
            '- /mode auto — автоматический режим (1 пост на модерации, остальные в очереди).\n'
            '- /mode curation — режим кураторства (все посты собираются в корзину без рерайта).\n\n'
            '<b>Управление интервалами:</b>\n'
            '- /interval [мин]-[макс] — случайная задержка. Поддерживает суффиксы: s (сек), m (мин), h (ч), d (д).\n'
            '  Пример: /interval 20m-50m или /interval 30s-1h\n'
            '- /interval [время] — фиксированная задержка. Пример: /interval 30s\n'
            '- /interval 0 — отключить задержку.\n\n'
            '<b>Пауза и возобновление:</b>\n'
            '- /pause — поставить бота на вечную паузу.\n'
            '- /pause [время] — поставить на паузу на указанное время. Пример: /pause 8h\n'
            '- /resume — возобновить работу бота (снять паузу).\n\n'
            '<b>Другие команды:</b>\n'
            '- /status — посмотреть настройки, режим и статистику.\n'
            '- /best [время] — принудительно запустить парсер и выбрать ТОП-6 лучших постов за период.\n'
            '  Пример: /best 24h или /best 12h\n'
            '- /parse [кол-во или время],[кол-во каналов] — ручной парсинг.\n'
            '  Пример: /parse 24h,5 (парсинг постов за 24ч из 5 случайных каналов)\n'
            '  Пример: /parse 10,2 (парсинг последних 10 постов из 2 случайных каналов)\n'
            '  Пример: /parse 5 (парсинг 5 последних постов со всех каналов)\n'
            '- /clear — полностью очистить очередь публикации и корзину.\n'
            '- /clear_db — полностью очистить базу данных постов.\n'
            '- /queue [лимит] — изменить максимальный размер очереди (по умолчанию 5, например: /queue 20).\n'
        ),

        # --- AI custom edit ---
        'ai_edit_prompt': 'Напишите, что ИИ должен сделать с текстом поста <b>#{post_id}</b> (например: <i>\'сделай короче\'</i>, <i>\'добавь больше деталей\'</i>, <i>\'перепиши в шутливом тоне\'</i>).\n\nДля отмены отправьте /cancel.',
        'ai_edit_send_instruction': 'Пожалуйста, отправьте текстовую инструкцию.',
        'ai_edit_cancelled': 'Корректировка отменена.',
        'ai_edit_progress': '⏳ <b>Нейросеть правит пост по вашему запросу...</b>',
        'ai_edit_failed': '❌ Не удалось изменить пост с помощью ИИ. Попробуйте еще раз.',
        'ai_edit_success': '✨ Текст поста успешно обновлен нейросетью!',
        'ai_edit_instruction': 'Сделай следующее с текстом поста: {instruction}. Формат и стиль (заголовок жирным, жирные ключевые слова) сохрани.',

        # --- Media replacement ---
        'media_send_new': 'Пришлите новое медиа (фото/видео/файл) для поста {post_id}:',
        'media_send_prompt': 'Отправьте новое фото, видео или документ для поста <b>#{post_id}</b>. Для отмены отправьте /cancel.',
        'media_send_please': 'Пожалуйста, отправьте медиа (фото/видео/документ).',
        'media_save_failed': 'Не удалось сохранить медиа: {error}',

        # --- /parse ---
        'parse_channels_random': '{count} случайных каналов',
        'parse_channels_all': 'всех каналов',
        'parse_signal_time': 'Сигнал отправлен. Парсер загружает сообщения за последние {time} из {channels}...',
        'parse_signal_limit': 'Сигнал отправлен. Парсер загружает последние {limit} сообщений из {channels}...',
        'parse_signal_error': 'Ошибка при отправке сигнала парсеру: {error}',
        'parse_done': 'Ручной парсинг успешно завершен. Импортировано новых уникальных постов: {count}.',

        # --- Pause 8h (reply button) ---
        'pause_8h_done': 'Бот поставлен на паузу на 8 часов (до {until} UTC).',

        # --- Manual post ---
        'manual_send_text': 'Пожалуйста, отправьте текст или медиа с подписью.',
        'manual_text_short': '⚠️ Текст слишком короткий. Отправьте нормальный текст для рерайта (минимум 5 символов), чтобы избежать выдумок ИИ.',
        'manual_download_failed': 'Не удалось скачать медиафайл. Попробуйте еще раз.',
        'manual_db_failed': 'Не удалось создать пост в базе данных.',
        'manual_accepted': 'Пост принят для ручной обработки (ID: {post_id}). Запускаю ИИ-рерайт...',
        'manual_source': 'Ручной пост',

        # --- Dashboard callbacks ---
        'cb_launching_parse': 'Запускаю парсинг...',
        'cb_selecting_best': 'Выбираю лучший пост...',
        'cb_pause_8h': 'Пауза на 8 часов',
        'cb_resumed': 'Бот возобновил работу',
        'cb_clearing_queue': 'Очистка очереди...',
        'cb_clearing_db': 'Очистка базы данных...',

        # --- Worker/tasks ---
        'worker_no_posts': 'Нет накопленных постов за последние {hours}ч.',
        'worker_best_selected': 'Выбрано {selected} постов из {total} кандидатов. Лучший пост сразу отправлен на модерацию, остальные {queued} добавлены в очередь.',

        # --- Language Setup & Settings ---
        'start_select_ui_lang': '🌐 <b>Шаг 1 из 2: Выберите язык интерфейса бота</b>\n(Select bot interface language):',
        'start_select_post_lang': '✍️ <b>Шаг 2 из 2: Выберите язык рерайта постов нейросетью</b>\n(Select language for AI-generated posts):',
        'lang_ui_set': '✅ Язык интерфейса установлен: <b>{lang}</b>',
        'lang_post_set': '✅ Язык постов (ИИ) установлен: <b>{lang}</b>',
        'lang_setup_complete': '🎉 <b>Настройка языков завершена!</b>\n\nВы всегда можете изменить их через меню настроек или команду /settings.',
        'btn_lang_ru': '🇷🇺 Русский (Russian)',
        'btn_lang_en': '🇬🇧 English (Английский)',
        'ib_languages': '🌐 Настройка языков',
        'menu_lang_title': '⚙️ <b>Настройки языков бота:</b>\n\n• 🌐 <b>Интерфейс:</b> <code>{ui_lang}</code>\n• ✍️ <b>Посты (ИИ):</b> <code>{post_lang}</code>',
        'btn_change_ui_lang': '🌐 Изменить язык интерфейса',
        'btn_change_post_lang': '✍️ Изменить язык постов (ИИ)',
        'status_ui_lang': '• <b>Язык интерфейса:</b> <code>{ui_lang}</code>',
        'status_post_lang': '• <b>Язык постов (ИИ):</b> <code>{post_lang}</code>',

        # --- Time units ---
        'time_days': 'д.',
        'time_hours': 'ч.',

        'time_minutes': 'мин.',
        'time_seconds': 'сек.',
    },
    'en': {
        # --- Buttons (moderation card) ---
        'btn_publish': '✅ Publish',
        'btn_reject': '❌ Reject',
        'btn_edit': '📝 Text',
        'btn_change_media': '🖼 Media',
        'btn_ai_edit': '✨ AI Editor',

        # --- Moderation messages ---
        'msg_access_denied': 'Access denied',
        'msg_already_processed': 'Post already processed or not found.',
        'msg_no_text_to_publish': 'Error: no text to publish.',
        'msg_published': '<b>Published</b>',
        'msg_published_alert': 'Published!',
        'msg_publish_error': 'Error during publication.',
        'msg_rejected': '<b>Rejected</b>',
        'msg_rejected_alert': 'Post rejected.',
        'msg_edit_instruction': 'To edit, copy the text below, make changes and send the command:\n<code>/edit {post_id} Your corrected text</code>',
        'msg_edit_wrong_format': 'Invalid command format. Use:\n/edit <post_ID> <New text>',
        'msg_edit_id_not_number': 'Invalid format or ID is not a number.',
        'msg_edit_post_not_found': 'Post not found or no longer in moderation (possibly already processed).',
        'msg_edit_success': 'Text updated! New card sent.',
        'card_new_post': '<b>New post from source {channel_id}</b>',
        'card_edited_post': '<b>New post from source {channel_id} (Edited)</b>',

        # --- Reply keyboard buttons ---
        'kb_moderation': '\U0001f4cb Moderation',
        'kb_status': '\U0001f4ca Status',
        'kb_parse_now': '\U0001f504 Parse now',
        'kb_find_best': '\u2b50 Find best post',
        'kb_pause_8h': '\u23f8 Pause 8h',
        'kb_resume': '\u25b6 Resume',
        'kb_clear_all': '🗑 Clear all',
        'kb_clear_db': '🗄 Clear DB',
        'kb_input_placeholder': 'Choose action...',

        # --- Inline keyboard buttons (status dashboard) ---
        'ib_moderation': '📋 Moderation',
        'ib_refresh_status': '🔄 Refresh status',
        'ib_parse_now': '⚡️ Parse now',
        'ib_find_best': '⭐️ Find best post',
        'ib_pause_8h': '⏸ Pause 8h',
        'ib_resume': '▶️ Resume',
        'ib_clear_all': '🗑 Clear all',
        'ib_clear_db': '🗄 Clear DB',

        # --- action_by label ---
        'action_by': '👤 Action by: {username}',
        'publish_error': '❌ Publish error: {error}',
        'extra_links': '<b>Additional links:</b>',
        'source_link': '<b>Source:</b> <a href=\'{url}\'>Go to original</a>',

        # --- /start ---
        'start_access_denied': 'Access denied. Your Telegram ID: <code>{user_id}</code>. Add it to ADMIN_IDS in the .env file.\n\nIf you found this bot by accident, you can check out the project on GitHub:\nhttps://github.com/ivanchik-byte/Telegram-Channel-Admin',
        'start_welcome': '<b>Hello! I\'m a channel moderation bot.</b>\n\nUse the menu buttons at the bottom of the screen for quick control, or send /help for the full command reference.',

        # --- Moderation flow ---
        'mod_extracting': '🔄 Extracting next post from queue and running AI rewrite...',
        'mod_ai_failed': '❌ Failed to rewrite post with AI.',
        'mod_already_processing': 'Post is already being processed. Please tap "Moderation" again in a few seconds.',
        'mod_queue_empty': 'Moderation queue and incoming posts are empty.',
        'mod_remaining': 'Posts remaining in moderation: {count}',
        'edit_error_id': 'ID error',
        'edit_post_processed': 'Post already processed',
        'edit_send_new_text': 'Send new text for post {post_id}:',
        'edit_text_not_received': 'Text not received or ID lost. Cancelled.',
        'edit_post_not_found': 'Post already processed or not found.',

        # --- /mode ---
        'mode_usage': 'Usage: /mode auto | curation\n\nauto: 1 post in moderation, 5 in queue.\ncuration: silent collection of all posts (/best command).',
        'mode_changed': 'Mode successfully changed to: <b>{mode}</b>',

        # --- /queue ---
        'queue_current': 'Current publish queue limit: <b>{limit}</b> posts.\n\nUsage: <code>/queue [number]</code> (e.g. /queue 20).',
        'queue_invalid': 'Please enter a valid number from 1 to 1000.',
        'queue_changed': 'Publish queue limit successfully changed to: <b>{limit}</b> posts.',

        # --- /best ---
        'best_invalid_time': 'Invalid time format. Example: /best 12h',
        'best_searching': 'Searching for the best post from the last {hours} hours. Please wait...',

        # --- /interval ---
        'interval_usage': 'Usage: /interval <min>-<max> (e.g. /interval 20m-50m)\nOr /interval 0 to disable.',
        'interval_disabled': 'Interval successfully disabled! Posts will be published as they are ready.',
        'interval_set': '<b>Interval successfully set:</b>\nfrom <b>{min_val}</b> to <b>{max_val}</b>.',
        'interval_invalid': 'Invalid format. Example: /interval 20m-50m or /interval 30-60',

        # --- /pause, /resume ---
        'pause_forever': '<b>Bot paused indefinitely.</b>\nParser disabled. Send /resume to continue.',
        'pause_timed': '<b>Bot paused for {duration}</b> (until {until} UTC).',
        'pause_invalid_time': 'Invalid time format. Example: /pause 8h or /pause 30s',
        'resume_done': '<b>Bot resumed.</b> Pause lifted, parser is active.',

        # --- /status ---
        'status_title': '<b>Current bot status:</b>\n',
        'status_mode': '• <b>Mode:</b> <code>{mode}</code>',
        'status_interval': '• <b>Interval:</b> <code>{min_val} - {max_val}</code>',
        'status_pause_forever': '• <b>Pause:</b> <code>Indefinite</code>',
        'status_pause_until': '• <b>Paused until:</b> <code>{until} UTC</code> (~{remaining})',
        'status_active': '• <b>Pause:</b> <code>Active</code>',
        'status_next_post': '• <b>Next post in:</b> <code>{delay}</code>',
        'status_moderating': '• <b>In moderation:</b> <code>{count} / 1</code>',
        'status_queued': '• <b>In queue (auto):</b> <code>{count} / {limit}</code>',
        'status_accumulated': '• <b>In basket (curation):</b> <code>{count}</code>',
        'status_updated': 'Status updated',

        # --- /clear, /clear_db ---
        'clear_done': '<b>Publish queue, moderation, and curation basket completely cleared.</b>',
        'clear_db_done': '<b>Database completely cleared.</b> Records deleted: {count}.',
        'clear_confirm': 'Are you sure you want to completely clear the publish queue, moderation, and curation basket?',
        'clear_confirm_yes': 'Yes, clear',
        'clear_confirm_no': 'Cancel',
        'clear_cancelled': 'Clear cancelled',
        'clear_db_confirm': 'Are you sure you want to completely clear the POST DATABASE? This action will delete all post history.',
        'clear_db_confirm_yes': 'Yes, clear DB',
        'clear_db_confirm_no': 'Cancel',
        'clear_db_cancelled': 'Cancelled',

        # --- /help ---
        'help_text': (
            '<b>Moderator bot command reference</b>\n\n'
            '<b>Interactive menu buttons:</b>\n'
            '- Moderation — show the oldest post awaiting review.\n'
            '- Parse now — force-load the last 10 messages from channels.\n'
            '- Find best post — load posts, reset interval, and pick TOP-6 (1 for moderation, 5 queued).\n'
            '- Status — settings, operating mode, current queue and delays.\n'
            '- Resume / Pause 8h / Clear queue.\n\n'
            '<b>Mode management:</b>\n'
            '- /mode auto — automatic mode (1 post in moderation, rest in queue).\n'
            '- /mode curation — curation mode (all posts collected in basket without rewrite).\n\n'
            '<b>Interval management:</b>\n'
            '- /interval [min]-[max] — random delay. Supports suffixes: s (sec), m (min), h (hr), d (day).\n'
            '  Example: /interval 20m-50m or /interval 30s-1h\n'
            '- /interval [time] — fixed delay. Example: /interval 30s\n'
            '- /interval 0 — disable delay.\n\n'
            '<b>Pause and resume:</b>\n'
            '- /pause — pause bot indefinitely.\n'
            '- /pause [time] — pause for a set duration. Example: /pause 8h\n'
            '- /resume — resume bot (lift pause).\n\n'
            '<b>Other commands:</b>\n'
            '- /status — view settings, mode, and statistics.\n'
            '- /best [time] — force-run parser and pick TOP-6 best posts for the period.\n'
            '  Example: /best 24h or /best 12h\n'
            '- /parse [count or time],[channel count] — manual parsing.\n'
            '  Example: /parse 24h,5 (parse posts from 24h across 5 random channels)\n'
            '  Example: /parse 10,2 (parse last 10 posts from 2 random channels)\n'
            '  Example: /parse 5 (parse 5 latest posts from all channels)\n'
            '- /clear — completely clear publish queue and basket.\n'
            '- /clear_db — completely clear the post database.\n'
            '- /queue [limit] — change max queue size (default 5, e.g. /queue 20).\n'
        ),

        # --- AI custom edit ---
        'ai_edit_prompt': 'Describe what AI should do with post <b>#{post_id}</b> text (e.g. <i>\'make it shorter\'</i>, <i>\'add more details\'</i>, <i>\'rewrite in a humorous tone\'</i>).\n\nTo cancel, send /cancel.',
        'ai_edit_send_instruction': 'Please send a text instruction.',
        'ai_edit_cancelled': 'Edit cancelled.',
        'ai_edit_progress': '⏳ <b>AI is editing the post per your request...</b>',
        'ai_edit_failed': '❌ Failed to edit post with AI. Try again.',
        'ai_edit_success': '✨ Post text successfully updated by AI!',
        'ai_edit_instruction': 'Do the following with the post text: {instruction}. Preserve the format and style (bold headline, bold keywords).',

        # --- Media replacement ---
        'media_send_new': 'Send new media (photo/video/file) for post {post_id}:',
        'media_send_prompt': 'Send a new photo, video, or document for post <b>#{post_id}</b>. To cancel, send /cancel.',
        'media_send_please': 'Please send media (photo/video/document).',
        'media_save_failed': 'Failed to save media: {error}',

        # --- /parse ---
        'parse_channels_random': '{count} random channels',
        'parse_channels_all': 'all channels',
        'parse_signal_time': 'Signal sent. Parser is loading messages from the last {time} from {channels}...',
        'parse_signal_limit': 'Signal sent. Parser is loading the last {limit} messages from {channels}...',
        'parse_signal_error': 'Error sending signal to parser: {error}',
        'parse_done': 'Manual parsing completed successfully. New unique posts imported: {count}.',

        # --- Pause 8h (reply button) ---
        'pause_8h_done': 'Bot paused for 8 hours (until {until} UTC).',

        # --- Manual post ---
        'manual_send_text': 'Please send text or media with a caption.',
        'manual_text_short': '⚠️ Text is too short. Send proper text for rewriting (minimum 5 characters) to avoid AI hallucinations.',
        'manual_download_failed': 'Failed to download media file. Please try again.',
        'manual_db_failed': 'Failed to create post in the database.',
        'manual_accepted': 'Post accepted for manual processing (ID: {post_id}). Running AI rewrite...',
        'manual_source': 'Manual post',

        # --- Dashboard callbacks ---
        'cb_launching_parse': 'Launching parse...',
        'cb_selecting_best': 'Selecting best post...',
        'cb_pause_8h': 'Paused for 8 hours',
        'cb_resumed': 'Bot resumed',
        'cb_clearing_queue': 'Clearing queue...',
        'cb_clearing_db': 'Clearing database...',

        # --- Worker/tasks ---
        'worker_no_posts': 'No accumulated posts from the last {hours}h.',
        'worker_best_selected': 'Selected {selected} posts out of {total} candidates. Best post sent to moderation immediately, remaining {queued} added to queue.',

        # --- Language Setup & Settings ---
        'start_select_ui_lang': '🌐 <b>Step 1 of 2: Select bot interface language</b>\n(Выберите язык интерфейса бота):',
        'start_select_post_lang': '✍️ <b>Step 2 of 2: Select language for AI-generated posts</b>\n(Выберите язык рерайта постов нейросетью):',
        'lang_ui_set': '✅ Interface language set to: <b>{lang}</b>',
        'lang_post_set': '✅ Posts language (AI) set to: <b>{lang}</b>',
        'lang_setup_complete': '🎉 <b>Language setup completed!</b>\n\nYou can change these settings anytime via the settings menu or the /settings command.',
        'btn_lang_ru': '🇷🇺 Русский (Russian)',
        'btn_lang_en': '🇬🇧 English (English)',
        'ib_languages': '🌐 Language Settings',
        'menu_lang_title': '⚙️ <b>Bot Language Settings:</b>\n\n• 🌐 <b>Interface:</b> <code>{ui_lang}</code>\n• ✍️ <b>Posts (AI):</b> <code>{post_lang}</code>',
        'btn_change_ui_lang': '🌐 Change interface language',
        'btn_change_post_lang': '✍️ Change posts language (AI)',
        'status_ui_lang': '• <b>UI Language:</b> <code>{ui_lang}</code>',
        'status_post_lang': '• <b>Posts Language (AI):</b> <code>{post_lang}</code>',

        # --- Time units ---
        'time_days': 'd',
        'time_hours': 'h',
        'time_minutes': 'min',
        'time_seconds': 'sec',
    }
}

class I18n:
    def __init__(self, default_lang: str = 'ru'):
        self.lang = default_lang

    def set_language(self, lang: str):
        if lang in TRANSLATIONS:
            self.lang = lang

    def get(self, key: str, lang: str | None = None, **kwargs) -> str:
        target_lang = lang or self.lang
        lang_dict = TRANSLATIONS.get(target_lang, TRANSLATIONS['ru'])
        text = lang_dict.get(key)
        if text is None:
            # Fallback to Russian if key is missing in current language
            text = TRANSLATIONS['ru'].get(key, key)
        if kwargs:
            try:
                text = text.format(**kwargs)
            except KeyError as ke:
                missing_key = ke.args[0] if ke.args else str(ke)
                _logger.warning(f"[i18n] Missing format key '{missing_key}' for i18n string '{key}' (lang={target_lang})")
        return text

# Global instance — reads from pydantic settings, consistent with the rest of the codebase
i18n = I18n(default_lang=settings.LANGUAGE)


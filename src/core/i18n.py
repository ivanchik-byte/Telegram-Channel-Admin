import logging
from src.core.config import settings

_logger = logging.getLogger("TG_Admin")

TRANSLATIONS = {
    'ru': {
        # --- Buttons (moderation card) ---
        'btn_publish': 'Опубликовать',
        'btn_reject': 'Отклонить',
        'btn_edit': 'Изменить текст',
        'btn_change_media': 'Медиа',
        'btn_ai_edit': 'Правка через ИИ',

        # --- Moderation messages ---
        'msg_access_denied': 'Доступ запрещен',
        'msg_already_processed': 'Пост уже обработан или не найден.',
        'msg_no_text_to_publish': 'Ошибка: нет текста для публикации.',
        'msg_published': '<b>Опубликовано</b>',
        'msg_published_alert': 'Пост опубликован.',
        'msg_rejected': '<b>Отклонено</b>',
        'msg_rejected_alert': 'Пост отклонен.',
        'msg_edit_wrong_format': 'Неверный формат команды. Используйте:\n/edit <ID_поста> <Новый текст>',
        'msg_edit_id_not_number': 'Неверный формат или ID не является числом.',
        'msg_edit_post_not_found': 'Пост не найден или уже не находится на модерации (возможно, уже обработан).',
        'msg_edit_success': 'Текст сохранён. Отправлена обновлённая карточка.',

        # --- Reply keyboard buttons ---
        'kb_moderation': 'Модерация',
        'kb_status': 'Статус',
        'kb_parse_now': 'Собрать посты',
        'kb_find_best': 'Отобрать лучшее',
        'kb_pause_8h': 'Пауза на 8 часов',
        'kb_resume': 'Возобновить',
        'kb_clear_all': 'Очистить очередь',
        'kb_clear_db': 'Очистить БД',
        'kb_input_placeholder': 'Текст поста или команда',

        # --- Inline keyboard buttons (status dashboard) ---
        'ib_moderation': 'Модерация',
        'ib_refresh_status': 'Обновить статус',
        'ib_parse_now': 'Собрать посты',
        'ib_find_best': 'Отобрать лучшее',
        'ib_pause_8h': 'Пауза на 8 часов',
        'ib_resume': 'Возобновить',
        'ib_clear_all': 'Очистить очередь',
        'ib_clear_db': 'Очистить БД',

        # --- action_by label ---
        'action_by': 'Модератор: {username}',
        'publish_error': 'Ошибка публикации: {error}',
        'extra_links': '<b>Дополнительные ссылки:</b>',
        'parser_hidden_links': 'Ссылки из поста:',
        'source_link': '<b>Источник:</b> <a href=\'{url}\'>Перейти к оригиналу</a>',

        # --- /start ---
        'start_access_denied': 'Доступ запрещен. Ваш Telegram ID: <code>{user_id}</code>. Добавьте его в ADMIN_IDS в файле .env.\n\nЕсли вы нашли этого бота случайно, вы можете ознакомиться с проектом на GitHub:\nhttps://github.com/ivanchik-byte/Telegram-Channel-Admin',
        'start_welcome': '<b>Управление каналом</b>\n\nПроверяйте посты, редактируйте текст и отправляйте готовые материалы в канал.\n\nМодерация — следующий пост на проверку.\nСтатус — очередь, пауза и настройки.\n\nМожно прислать свой текст или медиа с подписью. Список команд: /help.',

        # --- Moderation flow ---
        'mod_extracting': 'Готовлю следующий пост: переписываю текст через ИИ…',
        'mod_ai_failed': 'Не удалось подготовить текст. Проверьте подключение командой /test_ai.',
        'mod_already_processing': 'Пост уже обрабатывается. Пожалуйста, нажмите «Модерация» еще раз через пару секунд.',
        'mod_queue_empty': 'Постов на проверку пока нет. Нажмите «Собрать посты» или пришлите свой текст.',
        'mod_remaining': 'Постов на проверке: {count}',
        'edit_error_id': 'Ошибка ID',
        'edit_post_processed': 'Пост уже обработан',
        'edit_send_new_text': 'Пришлите новый текст для поста #{post_id}. Для отмены: /cancel.',
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
        'best_searching': 'Отбираю лучшие посты за последние {hours} ч. Результат пришлю после обработки.',

        # --- /interval ---
        'interval_usage': 'Использование: /interval <min>-<max> (например: /interval 20m-50m)\nИли /interval 0 для отключения.',
        'interval_disabled': 'Интервал отключён. Следующий пост поступит на проверку после обработки текущего.',
        'interval_set': '<b>Интервал успешно установлен:</b>\nот <b>{min_val}</b> до <b>{max_val}</b>.',
        'interval_invalid': 'Неверный формат. Пример: /interval 20m-50m или /interval 30-60',

        # --- /pause, /resume ---
        'pause_forever': '<b>Сбор постов приостановлен.</b>\nПауза действует до команды /resume.',
        'pause_timed': '<b>Бот поставлен на паузу на {duration}</b> (до {until} UTC).',
        'pause_invalid_time': 'Неверный формат времени. Пример: /pause 8h или /pause 30s',
        'resume_done': '<b>Бот возобновил работу.</b> Пауза снята, парсер активен.',

        # --- /status ---
        'status_title': '<b>Панель управления</b>\n',
        'status_mode': 'Режим: <b>{mode}</b>',
        'status_interval': 'Интервал: <code>{min_val} — {max_val}</code>',
        'status_pause_forever': 'Сбор постов: <b>на паузе</b>\nВозобновить: /resume',
        'status_pause_until': 'Пауза до: <code>{until} UTC</code>\nОсталось: {remaining}',
        'status_active': 'Сбор постов: <b>активен</b>',
        'status_next_post': 'Следующий пост через: <code>{delay}</code>',
        'status_moderating': 'На проверке: <b>{count}</b>',
        'status_queued': 'В очереди: <b>{count} / {limit}</b>',
        'status_accumulated': 'В подборке: <b>{count}</b>',
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
            (
            '<b>Справка по командам бота-модератора</b>\n'
            '\n'
            '<b>Интерактивные кнопки меню:</b>\n'
            '- Модерация — показать один старейший пост, ожидающий проверки.\n'
            '- Собрать посты — загрузить последние 5 сообщений из 3 случайных каналов.\n'
            '- Отобрать лучшее — выбрать до 6 постов из уже собранных материалов.\n'
            '- Статус — настройки, режим работы, текущая очередь и задержки.\n'
            '- Возобновить / Пауза 8ч / Очистить очередь.\n'
            '\n'
            '<b>Управление режимами:</b>\n'
            '- /mode auto — автоматический режим (1 пост на модерации, остальные в очереди).\n'
            '- /mode curation — режим кураторства (все посты собираются в корзину без рерайта).\n'
            '\n'
            '<b>Управление интервалами:</b>\n'
            '- /interval [мин]-[макс] — случайная задержка. Поддерживает суффиксы: s (сек), m (мин), h (ч), d (д).\n'
            'Пример: /interval 20m-50m или /interval 30s-1h\n'
            '- /interval [время] — фиксированная задержка. Пример: /interval 30s\n'
            '- /interval 0 — отключить задержку.\n'
            '\n'
            '<b>Пауза и возобновление:</b>\n'
            '- /pause — поставить бота на паузу без срока.\n'
            '- /pause [время] — поставить на паузу на указанное время. Пример: /pause 8h\n'
            '- /resume — возобновить работу бота (снять паузу).\n'
            '\n'
            '<b>Языки и системный промпт ИИ:</b>\n'
            '- /lang — изменить язык интерфейса или язык постов (ИИ).\n'
            '- /prompt — интерактивное меню управления системным промптом (просмотр, изменение, сброс).\n'
            '- /set_prompt [текст] — быстро установить свой системный промпт для рерайта постов.\n'
            '- /reset_prompt — сбросить промпт на стандартный по умолчанию.\n'
            '- /test_ai — проверить подключение к нейросети, валидность API ключа и модели.\n'
            '\n'
            '<b>Сбор постов и статистика:</b>\n'
            '- /status — посмотреть настройки, режим и статистику.\n'
            '- /mod — запросить старейший пост из очереди на немедленную проверку.\n'
            '- /edit [id] [текст] — отредактировать текст ожидающего поста.\n'
            '- /best [время] — выбрать до 6 лучших собранных постов за период (например: /best 24h).\n'
            '- /parse [кол-во или время],[каналы] — ручной сбор постов (например: /parse 24h,5 или /parse 10,2).\n'
            '- /queue [лимит] — изменить максимальный размер очереди (по умолчанию 5, например: /queue 20).\n'
            '\n'
            '<b>Очистка данных:</b>\n'
            '- /clear — очистить текущую очередь публикации и корзину.\n'
            '- /clear_db — полностью очистить базу данных постов.\n'
        )
        ),

        # --- AI custom edit ---
        'ai_edit_prompt': 'Напишите, что ИИ должен сделать с текстом поста <b>#{post_id}</b> (например: <i>\'сделай короче\'</i>, <i>\'добавь больше деталей\'</i>, <i>\'перепиши в шутливом тоне\'</i>).\n\nДля отмены отправьте /cancel.',
        'ai_edit_send_instruction': 'Пожалуйста, отправьте текстовую инструкцию.',
        'ai_edit_cancelled': 'Корректировка отменена.',
        'ai_edit_progress': '<b>Нейросеть правит пост по вашему запросу...</b>',
        'ai_edit_failed': 'Не удалось изменить пост с помощью ИИ. Попробуйте еще раз.',
        'ai_edit_success': 'Текст поста успешно обновлен нейросетью!',
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
        'manual_text_short': 'Добавьте больше текста: для рерайта нужно хотя бы 5 символов.',
        'manual_download_failed': 'Не удалось скачать медиафайл. Попробуйте еще раз.',
        'manual_db_failed': 'Не удалось создать пост в базе данных.',
        'manual_accepted': 'Пост #{post_id} принят. Готовлю текст через ИИ…',
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
        'worker_best_invalid': 'Не удалось разобрать ответ ИИ для {total} постов. Материалы сохранены. Повторите /best.',

        # --- Language Setup & Settings ---
        'start_select_ui_lang': '<b>Шаг 1 из 2: Выберите язык интерфейса бота</b>\n(Select bot interface language):',
        'start_select_post_lang': '<b>Шаг 2 из 2: Выберите язык рерайта постов нейросетью</b>\n(Select language for AI-generated posts):',
        'lang_ui_set': 'Язык интерфейса: {language_name}',
        'lang_post_set': 'Язык постов: {language_name}',
        'lang_setup_complete': '<b>Языки настроены</b>\n\nБот готов к работе. Выберите действие в меню ниже. Изменить языки: /lang.',
        'btn_lang_ru': 'Русский',
        'btn_lang_en': 'English',
        'ib_languages': 'Настройка языков',
        'menu_lang_title': '<b>Настройки языков бота:</b>\n\n• <b>Интерфейс:</b> <code>{ui_lang}</code>\n• <b>Посты (ИИ):</b> <code>{post_lang}</code>',
        'btn_change_ui_lang': 'Изменить язык интерфейса',
        'btn_change_post_lang': 'Изменить язык постов (ИИ)',
        'status_ui_lang': 'Интерфейс: <code>{ui_lang}</code>',
        'status_post_lang': 'Язык постов: <code>{post_lang}</code>',

        # --- Prompt Management ---
        'prompt_status_custom': '<b>Пользовательский</b> ({length} симв.)',
        'prompt_status_default': '<b>Стандартный ({language_name})</b>',
        'prompt_menu_title': '<b>Управление системным промптом ИИ:</b>\n\n• <b>Статус:</b> {status}\n\n{preview}\n\nВы можете изменить системный промпт для рерайта постов прямо сейчас или сбросить его на стандартный.',
        'prompt_preview_label': '<b>Текущий текст промпта:</b>\n<blockquote>{text}</blockquote>',
        'btn_set_prompt': 'Изменить промпт',
        'btn_reset_prompt': 'Сбросить на стандартный',
        'btn_show_prompt': 'Показать весь промпт',
        'ib_prompt': 'Промпт ИИ',
        'prompt_send_new': '<b>Отправьте новый системный промпт для рерайта постов следующим сообщением.</b>\n\nДля отмены отправьте /cancel.',
        'prompt_updated': '<b>Системный промпт успешно обновлен!</b>\nНовый размер: {length} символов.',
        'prompt_reset_done': 'Установлен стандартный промпт ({language_name}).',
        'prompt_canceled': 'Изменение промпта отменено.',
        'action_cancelled': 'Действие отменено.',
        'prompt_full_title': '<b>Полный системный промпт ({type}):</b>\n\n',

        # --- AI Errors and Diagnostics ---
        'ai_err_410': 'Модель устарела (End of Life) и больше не поддерживается провайдером API (HTTP 410 Gone).',
        'ai_err_401': 'Недействительный или истекший API ключ (HTTP 401 Unauthorized).',
        'ai_err_404': 'Модель или эндпоинт не найдены на сервере провайдера (HTTP 404 Not Found).',
        'ai_err_429': 'Превышен лимит запросов или закончился баланс токенов (HTTP 429 Rate Limit / Quota Exceeded).',
        'ai_err_402': 'Требуется оплата баланса API (HTTP 402 Payment Required).',
        'ai_err_5xx': 'Временный сбой на стороне провайдера нейросети (HTTP 5xx Server Error).',
        'ai_err_timeout': 'Превышено время ожидания ответа от нейросети (Timeout).',
        'ai_err_connection': 'Не удалось установить соединение с сервером нейросети (Connection Error).',
        'ai_test_testing': '<b>Проверка подключения к AI API...</b>\n\n• Модель: <code>{model}</code>\n• Эндпоинт: <code>{endpoint}</code>',
        'ai_test_success': '<b>Подключение к ИИ работает</b>\n\nМодель: <code>{model}</code>\nОтвет: <i>{response}</i>\nВремя ответа: <code>{latency} сек.</code>',

        # --- Time units ---
        'time_days': 'д.',
        'time_hours': 'ч.',
        'time_minutes': 'мин.',
        'time_seconds': 'сек.',
    },
    'en': {
        # --- Buttons (moderation card) ---
        'btn_publish': 'Publish',
        'btn_reject': 'Reject',
        'btn_edit': 'Edit text',
        'btn_change_media': 'Media',
        'btn_ai_edit': 'Edit with AI',

        # --- Moderation messages ---
        'msg_access_denied': 'Access denied',
        'msg_already_processed': 'Post already processed or not found.',
        'msg_no_text_to_publish': 'Error: no text to publish.',
        'msg_published': '<b>Published</b>',
        'msg_published_alert': 'Post published.',
        'msg_rejected': '<b>Rejected</b>',
        'msg_rejected_alert': 'Post rejected.',
        'msg_edit_wrong_format': 'Invalid command format. Use:\n/edit <post_ID> <New text>',
        'msg_edit_id_not_number': 'Invalid format or ID is not a number.',
        'msg_edit_post_not_found': 'Post not found or no longer in moderation (possibly already processed).',
        'msg_edit_success': 'Text saved. Updated review card sent.',

        # --- Reply keyboard buttons ---
        'kb_moderation': 'Moderation',
        'kb_status': 'Status',
        'kb_parse_now': 'Collect posts',
        'kb_find_best': 'Select best posts',
        'kb_pause_8h': 'Pause for 8 hours',
        'kb_resume': 'Resume',
        'kb_clear_all': 'Clear queue',
        'kb_clear_db': 'Clear DB',
        'kb_input_placeholder': 'Post text or command',

        # --- Inline keyboard buttons (status dashboard) ---
        'ib_moderation': 'Moderation',
        'ib_refresh_status': 'Refresh status',
        'ib_parse_now': 'Collect posts',
        'ib_find_best': 'Select best posts',
        'ib_pause_8h': 'Pause for 8 hours',
        'ib_resume': 'Resume',
        'ib_clear_all': 'Clear queue',
        'ib_clear_db': 'Clear DB',

        # --- action_by label ---
        'action_by': 'Moderator: {username}',
        'publish_error': 'Publish error: {error}',
        'extra_links': '<b>Additional links:</b>',
        'parser_hidden_links': 'Links from the post:',
        'source_link': '<b>Source:</b> <a href=\'{url}\'>Go to original</a>',

        # --- /start ---
        'start_access_denied': 'Access denied. Your Telegram ID: <code>{user_id}</code>. Add it to ADMIN_IDS in the .env file.\n\nIf you found this bot by accident, you can check out the project on GitHub:\nhttps://github.com/ivanchik-byte/Telegram-Channel-Admin',
        'start_welcome': '<b>Channel workspace</b>\n\nReview posts, edit drafts and publish finished content to your channel.\n\nModeration — the next post to review.\nStatus — queue, pause and settings.\n\nYou can also send your own text or media with a caption. Commands: /help.',

        # --- Moderation flow ---
        'mod_extracting': 'Preparing the next post: rewriting the text with AI…',
        'mod_ai_failed': 'Could not prepare the text. Check the connection with /test_ai.',
        'mod_already_processing': 'Post is already being processed. Please tap "Moderation" again in a few seconds.',
        'mod_queue_empty': 'No posts to review yet. Tap “Collect posts” or send your own text.',
        'mod_remaining': 'Posts awaiting review: {count}',
        'edit_error_id': 'ID error',
        'edit_post_processed': 'Post already processed',
        'edit_send_new_text': 'Send replacement text for post #{post_id}. Cancel: /cancel.',
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
        'best_searching': 'Selecting the best posts from the last {hours}h. Results will follow after processing.',

        # --- /interval ---
        'interval_usage': 'Usage: /interval <min>-<max> (e.g. /interval 20m-50m)\nOr /interval 0 to disable.',
        'interval_disabled': 'Interval disabled. The next post will arrive for review after the current one is processed.',
        'interval_set': '<b>Interval successfully set:</b>\nfrom <b>{min_val}</b> to <b>{max_val}</b>.',
        'interval_invalid': 'Invalid format. Example: /interval 20m-50m or /interval 30-60',

        # --- /pause, /resume ---
        'pause_forever': '<b>Post collection paused.</b>\nSend /resume to continue.',
        'pause_timed': '<b>Bot paused for {duration}</b> (until {until} UTC).',
        'pause_invalid_time': 'Invalid time format. Example: /pause 8h or /pause 30s',
        'resume_done': '<b>Bot resumed.</b> Pause lifted, parser is active.',

        # --- /status ---
        'status_title': '<b>Channel dashboard</b>\n',
        'status_mode': 'Mode: <b>{mode}</b>',
        'status_interval': 'Interval: <code>{min_val} — {max_val}</code>',
        'status_pause_forever': 'Collection: <b>paused</b>\nResume: /resume',
        'status_pause_until': 'Paused until: <code>{until} UTC</code>\nRemaining: {remaining}',
        'status_active': 'Collection: <b>active</b>',
        'status_next_post': 'Next post in: <code>{delay}</code>',
        'status_moderating': 'Awaiting review: <b>{count}</b>',
        'status_queued': 'Queued: <b>{count} / {limit}</b>',
        'status_accumulated': 'Collected: <b>{count}</b>',
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
            (
            '<b>Moderator bot command reference</b>\n'
            '\n'
            '<b>Interactive menu buttons:</b>\n'
            '- Moderation — show the oldest post awaiting review.\n'
            '- Collect posts — load the last 5 messages from 3 random channels.\n'
            '- Select best posts — pick up to 6 posts from collected material.\n'
            '- Status — settings, operating mode, current queue and delays.\n'
            '- Resume / Pause 8h / Clear queue.\n'
            '\n'
            '<b>Mode management:</b>\n'
            '- /mode auto — automatic mode (1 post in moderation, rest in queue).\n'
            '- /mode curation — curation mode (all posts collected in basket without rewrite).\n'
            '\n'
            '<b>Interval management:</b>\n'
            '- /interval [min]-[max] — random delay. Supports suffixes: s (sec), m (min), h (hr), d (day).\n'
            'Example: /interval 20m-50m or /interval 30s-1h\n'
            '- /interval [time] — fixed delay. Example: /interval 30s\n'
            '- /interval 0 — disable delay.\n'
            '\n'
            '<b>Pause and resume:</b>\n'
            '- /pause — pause bot indefinitely.\n'
            '- /pause [time] — pause for a set duration. Example: /pause 8h\n'
            '- /resume — resume bot (lift pause).\n'
            '\n'
            '<b>Languages & AI System Prompt:</b>\n'
            '- /lang — change interface language or AI post generation language.\n'
            '- /prompt — interactive menu for AI system prompt (view, edit, reset).\n'
            '- /set_prompt [text] — quickly set custom AI system rewrite prompt.\n'
            '- /reset_prompt — revert system prompt to default.\n'
            '- /test_ai — test AI connection, API key validity and active model.\n'
            '\n'
            '<b>Post Collection & Stats:</b>\n'
            '- /status — view settings, mode, and statistics.\n'
            '- /mod — request the oldest queued post for immediate review.\n'
            '- /edit [id] [text] — edit rewritten text of a pending post.\n'
            '- /best [time] — pick up to 6 collected posts for the period (e.g. /best 24h).\n'
            '- /parse [count or time],[channels] — manual parsing (e.g. /parse 24h,5 or /parse 10,2).\n'
            '- /queue [limit] — change max queue size (default 5, e.g. /queue 20).\n'
            '\n'
            '<b>Data Cleanup:</b>\n'
            '- /clear — clear current publish queue and basket.\n'
            '- /clear_db — completely clear the post database.\n'
        )
        ),

        # --- AI custom edit ---
        'ai_edit_prompt': 'Describe what AI should do with post <b>#{post_id}</b> text (e.g. <i>\'make it shorter\'</i>, <i>\'add more details\'</i>, <i>\'rewrite in a humorous tone\'</i>).\n\nTo cancel, send /cancel.',
        'ai_edit_send_instruction': 'Please send a text instruction.',
        'ai_edit_cancelled': 'Edit cancelled.',
        'ai_edit_progress': '<b>AI is editing the post per your request...</b>',
        'ai_edit_failed': 'Failed to edit post with AI. Try again.',
        'ai_edit_success': 'Post text successfully updated by AI!',
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
        'manual_text_short': 'Add more text: rewriting requires at least 5 characters.',
        'manual_download_failed': 'Failed to download media file. Please try again.',
        'manual_db_failed': 'Failed to create post in the database.',
        'manual_accepted': 'Post #{post_id} received. Preparing the text with AI…',
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
        'worker_best_invalid': 'Could not read the AI selection for {total} posts. Your posts are saved. Try /best again.',

        # --- Language Setup & Settings ---
        'start_select_ui_lang': '<b>Step 1 of 2: Select bot interface language</b>\n(Выберите язык интерфейса бота):',
        'start_select_post_lang': '<b>Step 2 of 2: Select language for AI-generated posts</b>\n(Выберите язык рерайта постов нейросетью):',
        'lang_ui_set': 'Interface language: {language_name}',
        'lang_post_set': 'Post language: {language_name}',
        'lang_setup_complete': '<b>Languages configured</b>\n\nReady to go. Choose an action below. Change languages: /lang.',
        'btn_lang_ru': 'Русский',
        'btn_lang_en': 'English',
        'ib_languages': 'Language Settings',
        'menu_lang_title': '<b>Bot Language Settings:</b>\n\n• <b>Interface:</b> <code>{ui_lang}</code>\n• <b>Posts (AI):</b> <code>{post_lang}</code>',
        'btn_change_ui_lang': 'Change interface language',
        'btn_change_post_lang': 'Change posts language (AI)',
        'status_ui_lang': 'Interface: <code>{ui_lang}</code>',
        'status_post_lang': 'Post language: <code>{post_lang}</code>',

        # --- Prompt Management ---
        'prompt_status_custom': '<b>Custom</b> ({length} chars)',
        'prompt_status_default': '<b>Default ({language_name})</b>',
        'prompt_menu_title': '<b>AI System Prompt Management:</b>\n\n• <b>Status:</b> {status}\n\n{preview}\n\nChange the AI post rewrite prompt on the fly or revert back to default.',
        'prompt_preview_label': '<b>Current Prompt Text:</b>\n<blockquote>{text}</blockquote>',
        'btn_set_prompt': 'Change Prompt',
        'btn_reset_prompt': 'Revert to Default',
        'btn_show_prompt': 'View Full Prompt',
        'ib_prompt': 'AI Prompt',
        'prompt_send_new': '<b>Send your new AI system prompt in the next message.</b>\n\nSend /cancel to abort.',
        'prompt_updated': '<b>AI system prompt successfully updated!</b>\nLength: {length} characters.',
        'prompt_reset_done': 'Default prompt restored ({language_name}).',
        'prompt_canceled': 'Prompt update cancelled.',
        'action_cancelled': 'Action cancelled.',
        'prompt_full_title': '<b>Full System Prompt ({type}):</b>\n\n',

        # --- AI Errors and Diagnostics ---
        'ai_err_410': 'The model is deprecated (End of Life) and no longer supported by the API provider (HTTP 410 Gone).',
        'ai_err_401': 'Invalid or expired API Key (HTTP 401 Unauthorized).',
        'ai_err_404': 'Model or endpoint not found on provider server (HTTP 404 Not Found).',
        'ai_err_429': 'Rate limit exceeded or token balance exhausted (HTTP 429 Rate Limit / Quota Exceeded).',
        'ai_err_402': 'Payment required for API balance (HTTP 402 Payment Required).',
        'ai_err_5xx': 'Temporary failure on the AI provider server (HTTP 5xx Server Error).',
        'ai_err_timeout': 'Timed out waiting for response from AI provider (Timeout).',
        'ai_err_connection': 'Failed to establish connection to AI provider server (Connection Error).',
        'ai_test_testing': '<b>Testing AI API connection...</b>\n\n• Model: <code>{model}</code>\n• Endpoint: <code>{endpoint}</code>',
        'ai_test_success': '<b>AI connection is working</b>\n\nModel: <code>{model}</code>\nResponse: <i>{response}</i>\nResponse time: <code>{latency} sec</code>',

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


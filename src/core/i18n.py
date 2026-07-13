import logging
from src.core.config import settings

_logger = logging.getLogger("TG_Admin")

TRANSLATIONS = {
    'ru': {
        'btn_publish': 'Опубликовать',
        'btn_reject': 'Отклонить',
        'btn_edit': 'Править',
        'btn_change_media': 'Заменить медиа',
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
    },
    'en': {
        'btn_publish': 'Publish',
        'btn_reject': 'Reject',
        'btn_edit': 'Edit',
        'btn_change_media': 'Replace media',
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
    }
}

class I18n:
    def __init__(self, default_lang: str = 'ru'):
        self.lang = default_lang

    def get(self, key: str, **kwargs) -> str:
        lang_dict = TRANSLATIONS.get(self.lang, TRANSLATIONS['ru'])
        text = lang_dict.get(key, key)
        if kwargs:
            try:
                text = text.format(**kwargs)
            except KeyError as ke:
                missing_key = ke.args[0] if ke.args else str(ke)
                _logger.warning(f"[i18n] Missing format key '{missing_key}' for i18n string '{key}' (lang={self.lang})")
        return text

# Global instance — reads from pydantic settings, consistent with the rest of the codebase
i18n = I18n(default_lang=settings.LANGUAGE)

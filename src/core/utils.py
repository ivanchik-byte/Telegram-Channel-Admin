from datetime import timedelta
import re
from html import unescape


def strip_html(value: str) -> str:
    """Strips HTML tags AND unescapes entities — result is clean plain text."""
    return unescape(re.sub(r'<[^>]+>', '', value))


def parse_time_suffix(time_str: str) -> timedelta | None:
    """
    Parses a string like '30s', '30m', '12h', '1d' into a timedelta.
    If no suffix is provided, assumes seconds for backward compatibility.
    Returns None if parsing fails.
    """
    time_str = time_str.strip().lower()
    if not time_str:
        return None

    try:
        if time_str.endswith('s'):
            return timedelta(seconds=int(time_str[:-1]))
        elif time_str.endswith('m'):
            return timedelta(minutes=int(time_str[:-1]))
        elif time_str.endswith('h'):
            return timedelta(hours=int(time_str[:-1]))
        elif time_str.endswith('d'):
            return timedelta(days=int(time_str[:-1]))
        else:
            # default to seconds
            return timedelta(seconds=int(time_str))
    except ValueError:
        return None


def format_seconds_readable(seconds: int) -> str:
    """Formats a number of seconds into a human-readable string using i18n time units."""
    from src.core.i18n import i18n

    if seconds == 0:
        return f"0 {i18n.get('time_seconds')}"
        
    days = seconds // 86400
    seconds %= 86400
    hours = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    secs = seconds % 60
    
    parts = []
    if days > 0:
        parts.append(f"{days} {i18n.get('time_days')}")
    if hours > 0:
        parts.append(f"{hours} {i18n.get('time_hours')}")
    if minutes > 0:
        parts.append(f"{minutes} {i18n.get('time_minutes')}")
    if secs > 0 or not parts:
        parts.append(f"{secs} {i18n.get('time_seconds')}")
        
    return " ".join(parts)


def format_telegram_html(text: str) -> str:
    """
    Safely formats text for Telegram's HTML parse mode.
    Converts Markdown bold/code/spoilers and balances/sanitizes HTML tags.
    """
    if not text:
        return ""
    from html import escape
    import re

    # Fix headline if it has a dangling </b> without opening <b>
    lines = text.split('\n')
    if lines and '</b>' in lines[0] and '<b' not in lines[0]:
        lines[0] = '<b>' + lines[0]
        text = '\n'.join(lines)

    # Standardize Markdown tags before escaping
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)
    text = re.sub(r'\|\|(.*?)\|\|', r'<tg-spoiler>\1</tg-spoiler>', text)

    allowed_tags = {'b', 'strong', 'i', 'em', 'u', 'ins', 's', 'strike', 'del', 'code', 'pre', 'blockquote', 'tg-spoiler', 'a'}
    tag_regex = re.compile(r'(</?([a-zA-Z0-9_-]+)(?:\s+[^>]*)?>)')

    parts = []
    stack = []
    last_idx = 0

    for match in tag_regex.finditer(text):
        start, end = match.span()
        plain_part = text[last_idx:start]
        parts.append(escape(plain_part))

        full_tag = match.group(1)
        tag_name = match.group(2).lower()
        is_closing = full_tag.startswith('</')

        if tag_name not in allowed_tags:
            parts.append(escape(full_tag))
        else:
            if is_closing:
                if stack and stack[-1] == tag_name:
                    stack.pop()
                    parts.append(f"</{tag_name}>")
                elif tag_name in stack:
                    while stack and stack[-1] != tag_name:
                        unclosed = stack.pop()
                        parts.append(f"</{unclosed}>")
                    if stack and stack[-1] == tag_name:
                        stack.pop()
                        parts.append(f"</{tag_name}>")
                else:
                    # Dangling closing tag with no matching opening tag: discard
                    pass
            else:
                if tag_name == 'a':
                    href_match = re.search(r'href=[\'"]([^\'"]+)[\'"]', full_tag)
                    if href_match:
                        clean_href = escape(href_match.group(1), quote=True)
                        parts.append(f'<a href="{clean_href}">')
                        stack.append('a')
                    else:
                        parts.append(escape(full_tag))
                else:
                    parts.append(f"<{tag_name}>")
                    stack.append(tag_name)

        last_idx = end

    parts.append(escape(text[last_idx:]))

    while stack:
        unclosed = stack.pop()
        parts.append(f"</{unclosed}>")

    return "".join(parts)


def clean_post_output(text: str) -> str:
    """
    Cleans up conversational wrappers and tokenizer artifacts from AI output.
    """
    if not text:
        return ""
    import re
    # 0. Clean DeepSeek / thinking <think>...</think> tags if present
    if "<think>" in text:
        if "</think>" in text:
            text = text.split("</think>")[-1].strip()
        else:
            text = text.split("<think>")[0].strip()
    # 1. Remove XML wrapper tags if model echoed them.
    # Only strip known wrapper tags so Telegram <b>/<i>/<code> survive
    text = re.sub(r"^<(?:post|article|output)>\s*|\s*</(?:post|article|output)>$", "", text.strip(), flags=re.IGNORECASE)
    # 2. Strip conversational preambles
    text = re.sub(r"^(Вот (готовый )?пост|Here is the (rewritten )?post):?\s*\n+", "", text, flags=re.IGNORECASE)
    # 3. Replace cross-lingual tokenizer artifact 'như'
    text = re.sub(r"\bnhư\b", "таких как", text, flags=re.IGNORECASE)
    return text.strip()


def delete_media_file(path: str | None) -> bool:
    """
    Delete a post media file from disk. Never raises.
    Returns True when a file was actually removed.
    """
    if not path:
        return False
    import os
    try:
        abs_path = os.path.abspath(path)
        # Only allow deletions inside the media storage directory
        media_root = os.path.abspath('data/media')
        if os.path.commonpath([abs_path, media_root]) != media_root:
            return False
        if os.path.isfile(abs_path):
            os.remove(abs_path)
            return True
    except OSError:
        pass
    return False


def split_message_text(text: str, limit: int = 4096) -> list[str]:
    """Splits text into chunks that each fit Telegram's message limit.

    Splits on paragraph boundaries when possible, hard-slices overlong lines.
    Safe to format each chunk with format_telegram_html() afterwards — it
    balances tags per chunk.
    """
    if len(text) <= limit:
        return [text] if text else []

    chunks = []
    current = ""
    for line in text.split("\n"):
        while len(line) > limit:
            # Hard-split a single overlong line
            head, line = line[:limit], line[limit:]
            if current:
                chunks.append(current)
                current = ""
            chunks.append(head)
        if len(current) + len(line) + 1 > limit:
            chunks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)
    return chunks

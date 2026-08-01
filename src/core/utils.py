from datetime import timedelta

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
    Escapes HTML entities first, then converts markdown **bold** to <b>bold</b>,
    and restores allowed safe tags (<b>, <i>, <code>).
    """
    if not text:
        return ""
    from html import escape
    import re
    escaped = escape(text)
    # Convert **bold** to <b>bold</b>
    bold_converted = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', escaped)
    # Convert ||spoiler|| to <tg-spoiler>spoiler</tg-spoiler>
    spoiler_converted = re.sub(r'\|\|(.*?)\|\|', r'<tg-spoiler>\1</tg-spoiler>', bold_converted)
    # Unescape allowed tags
    restored = spoiler_converted.replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")
    restored = restored.replace("&lt;i&gt;", "<i>").replace("&lt;/i&gt;", "</i>")
    restored = restored.replace("&lt;code&gt;", "<code>").replace("&lt;/code&gt;", "</code>")
    restored = restored.replace("&lt;tg-spoiler&gt;", "<tg-spoiler>").replace("&lt;/tg-spoiler&gt;", "</tg-spoiler>")
    return restored

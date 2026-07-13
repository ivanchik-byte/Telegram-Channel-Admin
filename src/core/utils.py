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
    """Formats a number of seconds into a human-readable string (e.g. '20 мин. 30 сек.')."""
    if seconds == 0:
        return "0 сек."
        
    days = seconds // 86400
    seconds %= 86400
    hours = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    secs = seconds % 60
    
    parts = []
    if days > 0:
        parts.append(f"{days} д.")
    if hours > 0:
        parts.append(f"{hours} ч.")
    if minutes > 0:
        parts.append(f"{minutes} мин.")
    if secs > 0 or not parts:
        parts.append(f"{secs} сек.")
        
    return " ".join(parts)

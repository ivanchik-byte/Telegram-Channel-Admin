from datetime import timedelta

def parse_time_suffix(time_str: str) -> timedelta | None:
    """
    Parses a string like '30m', '12h', '1d' into a timedelta.
    If no suffix is provided, assumes minutes for backward compatibility.
    Returns None if parsing fails.
    """
    time_str = time_str.strip().lower()
    if not time_str:
        return None

    try:
        if time_str.endswith('m'):
            return timedelta(minutes=int(time_str[:-1]))
        elif time_str.endswith('h'):
            return timedelta(hours=int(time_str[:-1]))
        elif time_str.endswith('d'):
            return timedelta(days=int(time_str[:-1]))
        else:
            # default to minutes
            return timedelta(minutes=int(time_str))
    except ValueError:
        return None

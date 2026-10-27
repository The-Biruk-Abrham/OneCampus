from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Any, List, Tuple
from collections import defaultdict

ADDIS_TZ = ZoneInfo("Africa/Addis_Ababa")

CATEGORY_EMOJIS = {
    "academic": "🎓",
    "career/workshop": "💼",
    "sports": "⚽",
    "entertainment": "🎭",
    "club social": "🎉",
    "religious": "🕊️",
    "other": "📌",
}


def safe_escape(text: Any) -> str:
    """
    Safely escapes special characters for Telegram Markdown V1 to prevent entity parsing errors.
    """
    if text is None:
        return ""
    s = str(text)
    for ch in ('\\', '*', '_', '`', '['):
        s = s.replace(ch, f"\\{ch}")
    return s


def get_category_emoji(category_name: str = "") -> str:
    if not category_name:
        return "📌"
    return CATEGORY_EMOJIS.get(str(category_name).lower().strip(), "📌")


def parse_datetime(dt_str: str) -> datetime:
    """Parses ISO 8601 string into an Addis Ababa timezone-aware datetime object."""
    if not dt_str:
        return None
    try:
        # Handle trailing Z
        if dt_str.endswith('Z'):
            dt_str = dt_str[:-1] + '+00:00'
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ADDIS_TZ)
        else:
            dt = dt.astimezone(ADDIS_TZ)
        return dt
    except Exception:
        return None


def format_time_range(start_dt: datetime, end_dt: datetime = None) -> str:
    if not start_dt:
        return "TBD"
    time_fmt = "%I:%M %p"
    start_time_str = start_dt.strftime(time_fmt).lstrip('0')
    if end_dt:
        end_time_str = end_dt.strftime(time_fmt).lstrip('0')
        return f"{start_time_str} – {end_time_str}"
    return start_time_str


def format_event_card(event: Dict[str, Any], index: int = None) -> str:
    """
    Format a single event summary block for listing views in Addis Ababa local time.
    """
    start_dt = parse_datetime(event.get('start_datetime'))
    end_dt = parse_datetime(event.get('end_datetime'))
    time_str = format_time_range(start_dt, end_dt)
    
    category_name = event.get('category_name') or 'General'
    emoji = get_category_emoji(category_name)
    title = safe_escape(event.get('title', 'Untitled Event'))
    club = safe_escape(event.get('club_name') or 'University Club')
    location = safe_escape(event.get('location') or 'Campus')
    category_escaped = safe_escape(category_name)

    prefix = f"{index}. " if index is not None else ""

    lines = [
        f"{prefix}*{title}*",
        f"  {emoji} `{category_escaped}` • 🏢 {club}",
        f"  ⏰ {time_str} • 📍 {location}",
    ]

    if event.get('recurring') and event.get('recurrence_pattern'):
        lines.append(f"  🔄 _{safe_escape(event['recurrence_pattern'])}_")

    return "\n".join(lines)


def format_single_event(event: Dict[str, Any]) -> str:
    """
    Format detailed full view of an event in Addis Ababa local time.
    """
    start_dt = parse_datetime(event.get('start_datetime'))
    end_dt = parse_datetime(event.get('end_datetime'))
    date_str = start_dt.strftime("%A, %B %d, %Y") if start_dt else "TBD"
    time_str = format_time_range(start_dt, end_dt)

    category_name = event.get('category_name') or 'General'
    emoji = get_category_emoji(category_name)
    title = safe_escape(event.get('title', 'Untitled Event'))
    club = safe_escape(event.get('club_name') or 'University Club')
    location = safe_escape(event.get('location') or 'Campus')
    category_escaped = safe_escape(category_name)

    is_custom_club = event.get('is_custom_club') or (not event.get('club') and event.get('custom_club'))
    is_custom_cat = event.get('is_custom_category') or (not event.get('category') and event.get('custom_category'))

    club_line = f"🏛️ *Organizer:* {club}"
    if is_custom_club:
        club_line = f"⚠️ *Organizer:* {club} _(CUSTOM / UNVERIFIED ENTRY)_"

    cat_line = f"{emoji} *Category:* {category_escaped}"
    if is_custom_cat:
        cat_line = f"⚠️ *Category:* {category_escaped} _(CUSTOM / UNLISTED)_"

    lines = [
        f"✨ *{title}* ✨",
        "─" * 28,
        club_line,
        cat_line,
        f"📅 *Date:* {date_str}",
        f"⏰ *Time:* {time_str}",
        f"📍 *Location:* {location}",
    ]

    if event.get('recurring') and event.get('recurrence_pattern'):
        lines.append(f"🔄 *Recurrence:* {safe_escape(event['recurrence_pattern'])}")

    raw_content = event.get('raw_content') or {}
    caption = raw_content.get('caption')
    if caption:
        lines.append("")
        lines.append("📝 *Original Announcement:*")
        lines.append(f"{safe_escape(caption.strip())}")

    return "\n".join(lines)


def format_today_events(
    events: List[Dict[str, Any]],
    page: int = 1,
    page_size: int = 3,
) -> Tuple[str, int, int]:
    """
    Formats today's events with pagination in Addis Ababa local time.
    Returns (formatted_text, total_pages, total_count).
    """
    today_str = datetime.now(ADDIS_TZ).strftime("%A, %B %d, %Y")
    total_count = len(events)

    if total_count == 0:
        return (
            f"☀️ *Today at AASTU ({today_str})*\n\n"
            "No events scheduled for today.\n"
            "Check out upcoming events with `/week` or browse by `/events`!",
            0,
            0,
        )

    total_pages = max(1, (total_count + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_events = events[start_idx:end_idx]

    header = f"☀️ *Today at AASTU ({today_str})*\n"
    header += f"_{total_count} event{'s' if total_count != 1 else ''} scheduled_\n"
    header += "─" * 28 + "\n\n"

    cards = []
    for i, event in enumerate(page_events, start=start_idx + 1):
        cards.append(format_event_card(event, index=i))

    body = "\n\n".join(cards)
    footer = f"\n\n_Page {page} of {total_pages}_" if total_pages > 1 else ""

    return (header + body + footer, total_pages, total_count)


def format_week_events(events: List[Dict[str, Any]]) -> str:
    """
    Formats events for the upcoming 7 days grouped by weekday in Addis Ababa local time.
    """
    if not events:
        return (
            "🗓️ *This Week at AASTU*\n\n"
            "No events scheduled for this week yet.\n"
            "Stay tuned for new club announcements!"
        )

    # Group events by date string in Addis Ababa local time
    grouped = defaultdict(list)
    for event in events:
        start_dt = parse_datetime(event.get('start_datetime'))
        if start_dt:
            day_key = start_dt.strftime("%A, %b %d")
            grouped[day_key].append(event)
        else:
            grouped["Date TBD"].append(event)

    total_count = len(events)
    header = f"🗓️ *This Week at AASTU ({total_count} Total)*\n"
    header += "─" * 28 + "\n"

    sections = []
    for day_label, day_events in grouped.items():
        day_header = f"📅 *{day_label}* ({len(day_events)})"
        cards = []
        for i, ev in enumerate(day_events, start=1):
            start_dt = parse_datetime(ev.get('start_datetime'))
            end_dt = parse_datetime(ev.get('end_datetime'))
            time_str = format_time_range(start_dt, end_dt)
            category_name = ev.get('category_name') or 'General'
            emoji = get_category_emoji(category_name)
            title = safe_escape(ev.get('title', 'Untitled Event'))
            club = safe_escape(ev.get('club_name') or 'Club')
            loc = safe_escape(ev.get('location') or 'Campus')

            cards.append(
                f"  • *{title}*\n"
                f"    {emoji} {safe_escape(category_name)} • ⏰ {time_str}\n"
                f"    🏢 {club} • 📍 {loc}"
            )
        sections.append(f"{day_header}\n" + "\n".join(cards))

    return header + "\n\n".join(sections)


def format_category_events(
    category_name: str,
    events: List[Dict[str, Any]],
    page: int = 1,
    page_size: int = 3,
) -> Tuple[str, int, int]:
    """
    Formats filtered category events.
    """
    emoji = get_category_emoji(category_name)
    total_count = len(events)

    if total_count == 0:
        return (
            f"{emoji} *{safe_escape(category_name)} Events*\n\n"
            f"No upcoming {safe_escape(category_name)} events currently scheduled.\n"
            "Try another category with `/events`!",
            0,
            0,
        )

    total_pages = max(1, (total_count + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_events = events[start_idx:end_idx]

    header = f"{emoji} *{safe_escape(category_name)} Events*\n"
    header += f"_{total_count} upcoming event{'s' if total_count != 1 else ''}_\n"
    header += "─" * 28 + "\n\n"

    cards = []
    for i, event in enumerate(page_events, start=start_idx + 1):
        card = format_event_card(event, index=i)
        cards.append(card)

    body = "\n\n".join(cards)
    footer = f"\n\n_Page {page} of {total_pages}_" if total_pages > 1 else ""

    return (header + body + footer, total_pages, total_count)


def format_channel_post(event: Dict[str, Any], max_len: int = 100000) -> str:
    """
    Dedicated formatting function for Telegram Broadcast Channel posting.

    1. Forwarded submissions (is_forwarded=True):
       Returns the original forwarded media caption/text completely untouched without truncating.

    2. Manual submissions (is_forwarded=False):
       Composes a clear, fully formatted channel post FROM all structured fields:
       Title, Club/Organizer, Category, Date/Time, Location/Venue, Recurrence (if any),
       and whatever full description text the user typed without truncating.
    """
    raw_content = event.get('raw_content') or {}
    is_forwarded = bool(raw_content.get('is_forwarded', False))
    caption = (raw_content.get('caption') or "").strip()

    # Path 1: Forwarded Submissions -> preserve original content untouched
    if is_forwarded:
        if caption:
            return caption
        return event.get('title', 'Upcoming Event')

    # Path 2: Manual Submissions -> compose complete formatted summary from structured fields
    start_dt = parse_datetime(event.get('start_datetime'))
    end_dt = parse_datetime(event.get('end_datetime'))
    date_str = start_dt.strftime("%A, %B %d, %Y") if start_dt else "TBD"
    time_str = format_time_range(start_dt, end_dt)

    category_name = event.get('category_name') or 'General'
    emoji = get_category_emoji(category_name)
    title = safe_escape(event.get('title', 'Untitled Event'))
    club = safe_escape(event.get('club_name') or 'University Club')
    location = safe_escape(event.get('location') or 'Campus')
    category_escaped = safe_escape(category_name)

    is_custom_club = event.get('is_custom_club') or (not event.get('club') and event.get('custom_club'))
    is_custom_cat = event.get('is_custom_category') or (not event.get('category') and event.get('custom_category'))

    club_line = f"🏛️ *Organizer:* {club}"
    if is_custom_club:
        club_line = f"🏛️ *Organizer:* {club} _(Custom)_"

    cat_line = f"{emoji} *Category:* {category_escaped}"
    if is_custom_cat:
        cat_line = f"{emoji} *Category:* {category_escaped} _(Custom)_"

    lines = [
        f"📢 *NEW CAMPUS EVENT*",
        "─" * 28,
        f"✨ *{title}* ✨",
        club_line,
        cat_line,
        f"📅 *Date:* {date_str}",
        f"⏰ *Time:* {time_str}",
        f"📍 *Location:* {location}",
    ]

    if event.get('recurring') and event.get('recurrence_pattern'):
        lines.append(f"🔄 *Recurrence:* {safe_escape(event['recurrence_pattern'])}")

    base_post = "\n".join(lines)

    if caption:
        caption_esc = safe_escape(caption)
        desc_block = f"\n\n📝 *Description:*\n{caption_esc}"
        return base_post + desc_block

    return base_post


def format_admin_pending_card(event: Dict[str, Any], max_len: int = 1000) -> str:
    """
    Formats the structured review card specifically for the Admin Group notification.
    Includes Header, Structured Fields (Title, Organizer, Category, Date/Time, Location),
    and original caption snippet if it fits within the media caption limit.
    """
    start_dt = parse_datetime(event.get('start_datetime'))
    end_dt = parse_datetime(event.get('end_datetime'))
    date_str = start_dt.strftime("%A, %B %d, %Y") if start_dt else "TBD"
    time_str = format_time_range(start_dt, end_dt)

    category_name = event.get('category_name') or 'General'
    emoji = get_category_emoji(category_name)
    title = safe_escape(event.get('title', 'Untitled Event'))
    club = safe_escape(event.get('club_name') or 'University Club')
    location = safe_escape(event.get('location') or 'Campus')
    category_escaped = safe_escape(category_name)

    is_custom_club = event.get('is_custom_club') or (not event.get('club') and event.get('custom_club'))
    is_custom_cat = event.get('is_custom_category') or (not event.get('category') and event.get('custom_category'))

    club_line = f"🏛️ *Organizer:* {club}"
    if is_custom_club:
        club_line = f"⚠️ *Organizer:* {club} _(CUSTOM / UNVERIFIED ENTRY)_"

    cat_line = f"{emoji} *Category:* {category_escaped}"
    if is_custom_cat:
        cat_line = f"⚠️ *Category:* {category_escaped} _(CUSTOM / UNLISTED)_"

    header_lines = [
        "🔔 *NEW EVENT PENDING APPROVAL*",
        "─" * 28,
        f"✨ *{title}* ✨",
        club_line,
        cat_line,
        f"📅 *Date:* {date_str}",
        f"⏰ *Time:* {time_str}",
        f"📍 *Location:* {location}",
    ]

    if event.get('recurring') and event.get('recurrence_pattern'):
        header_lines.append(f"🔄 *Recurrence:* {safe_escape(event['recurrence_pattern'])}")

    raw_content = event.get('raw_content') or {}
    caption = (raw_content.get('caption') or "").strip()

    structured_text = "\n".join(header_lines)

    if caption:
        available_len = max_len - len(structured_text) - 30
        if available_len > 40:
            caption_esc = safe_escape(caption)
            if len(caption_esc) > available_len:
                caption_esc = caption_esc[:available_len].rstrip() + "..."
            return f"{structured_text}\n\n📝 *Original Announcement:*\n_{caption_esc}_"

    return structured_text


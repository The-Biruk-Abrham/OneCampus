from typing import List, Dict, Any, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from .formatters import get_category_emoji


def build_pagination_keyboard(
    current_page: int,
    total_pages: int,
    callback_prefix: str,
    back_callback: Optional[str] = None,
    show_main_menu: bool = False,
) -> Optional[InlineKeyboardMarkup]:
    """
    Builds [◀️ Prev] [Page X/Y] [Next ▶️] pagination inline keyboard
    with optional Back and Main Menu navigation buttons.
    """
    keyboard = []

    if total_pages > 1:
        page_buttons = []
        # Prev Button
        if current_page > 1:
            page_buttons.append(
                InlineKeyboardButton("◀️ Prev", callback_data=f"{callback_prefix}:{current_page - 1}")
            )
        else:
            page_buttons.append(InlineKeyboardButton("⏹️", callback_data="noop"))

        # Indicator
        page_buttons.append(
            InlineKeyboardButton(f"{current_page} / {total_pages}", callback_data="noop")
        )

        # Next Button
        if current_page < total_pages:
            page_buttons.append(
                InlineKeyboardButton("Next ▶️", callback_data=f"{callback_prefix}:{current_page + 1}")
            )
        else:
            page_buttons.append(InlineKeyboardButton("⏹️", callback_data="noop"))

        keyboard.append(page_buttons)

    # Navigation buttons row (Back / Main Menu)
    nav_row = []
    if back_callback:
        label = "🔙 Categories" if back_callback == "btn:categories" else "🔙 Back"
        nav_row.append(InlineKeyboardButton(label, callback_data=back_callback))
    if show_main_menu:
        nav_row.append(InlineKeyboardButton("🏠 Main Menu", callback_data="btn:main_menu"))

    if nav_row:
        keyboard.append(nav_row)

    return InlineKeyboardMarkup(keyboard) if keyboard else None


def build_category_keyboard(categories: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """
    Builds an interactive 2-column grid of category buttons
    plus a '🔙 Back to Main Menu' button.
    """
    keyboard = []
    row = []

    for cat in categories:
        cat_id = cat.get('id')
        cat_name = cat.get('name', 'Category')
        emoji = get_category_emoji(cat_name)
        button_text = f"{emoji} {cat_name}"
        button = InlineKeyboardButton(button_text, callback_data=f"cat:select:{cat_id}")
        row.append(button)
        if len(row) == 2:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    # Navigation row to return to Main Menu
    keyboard.append([
        InlineKeyboardButton("🔙 Back to Main Menu", callback_data="btn:main_menu")
    ])

    return InlineKeyboardMarkup(keyboard)


def build_category_events_keyboard(
    category_identifier: Any,
    current_page: int,
    total_pages: int,
) -> Optional[InlineKeyboardMarkup]:
    """
    Builds keyboard for category events view with pagination + [🔙 Categories] [🏠 Main Menu].
    """
    return build_pagination_keyboard(
        current_page=current_page,
        total_pages=total_pages,
        callback_prefix=f"page:cat:{category_identifier}",
        back_callback="btn:categories",
        show_main_menu=True,
    )


def build_single_action_keyboard(
    back_callback: Optional[str] = None,
    show_main_menu: bool = True
) -> Optional[InlineKeyboardMarkup]:
    """
    Builds a simple navigation bar with Back and/or Main Menu buttons.
    """
    row = []
    if back_callback:
        label = "🔙 Categories" if back_callback == "btn:categories" else "🔙 Back"
        row.append(InlineKeyboardButton(label, callback_data=back_callback))
    if show_main_menu:
        row.append(InlineKeyboardButton("🏠 Main Menu", callback_data="btn:main_menu"))
    return InlineKeyboardMarkup([row]) if row else None


def build_start_keyboard() -> InlineKeyboardMarkup:
    """
    Quick action menu buttons for /start.
    """
    keyboard = [
        [
            InlineKeyboardButton("☀️ Today's Events", callback_data="btn:today"),
            InlineKeyboardButton("🗓️ This Week", callback_data="btn:week"),
        ],
        [
            InlineKeyboardButton("🏷️ Browse by Category", callback_data="btn:categories"),
        ],
        [
            InlineKeyboardButton("➕ Submit New Event", callback_data="btn:submit"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def build_submission_confirm_keyboard() -> InlineKeyboardMarkup:
    """
    Interactive confirmation keyboard before sending event to approval queue.
    Allows editing any single field or confirming/cancelling.
    """
    keyboard = [
        [
            InlineKeyboardButton("✅ Confirm & Submit", callback_data="submit:confirm"),
        ],
        [
            InlineKeyboardButton("✏️ Title", callback_data="submit:edit:title"),
            InlineKeyboardButton("🏛️ Club", callback_data="submit:edit:club"),
            InlineKeyboardButton("🏷️ Category", callback_data="submit:edit:category"),
        ],
        [
            InlineKeyboardButton("📅 Date & Time", callback_data="submit:edit:datetime"),
            InlineKeyboardButton("📍 Location", callback_data="submit:edit:location"),
        ],
        [
            InlineKeyboardButton("❌ Cancel Submission", callback_data="submit:cancel"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def build_club_picker_keyboard(clubs: List[Dict[str, Any]], callback_prefix: str = "submit:club") -> InlineKeyboardMarkup:
    """
    Keyboard for selecting host club during submission, including an '➕ Other' option.
    """
    keyboard = []
    for club in clubs:
        cid = club.get('id')
        cname = club.get('name', 'Club')
        keyboard.append([
            InlineKeyboardButton(f"🏛️ {cname}", callback_data=f"{callback_prefix}:{cid}")
        ])
    # Option for Custom / Unlisted Club
    keyboard.append([
        InlineKeyboardButton("➕ Other (Type Custom Club)", callback_data=f"{callback_prefix}:other")
    ])
    keyboard.append([
        InlineKeyboardButton("❌ Cancel Submission", callback_data="submit:cancel")
    ])
    return InlineKeyboardMarkup(keyboard)


def build_submission_category_keyboard(categories: List[Dict[str, Any]], callback_prefix: str = "submit:cat") -> InlineKeyboardMarkup:
    """
    Keyboard for choosing category during submission, including an '➕ Other' option.
    """
    keyboard = []
    row = []
    for cat in categories:
        cid = cat.get('id')
        cname = cat.get('name', 'Category')
        emoji = get_category_emoji(cname)
        row.append(InlineKeyboardButton(f"{emoji} {cname}", callback_data=f"{callback_prefix}:{cid}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    # Option for Custom Category
    keyboard.append([
        InlineKeyboardButton("➕ Other (Type Custom Category)", callback_data=f"{callback_prefix}:other")
    ])
    keyboard.append([
        InlineKeyboardButton("❌ Cancel Submission", callback_data="submit:cancel")
    ])
    return InlineKeyboardMarkup(keyboard)


def build_admin_approval_keyboard(event_id: int) -> InlineKeyboardMarkup:
    """
    Inline keyboard displayed in the Admin Group for pending submissions.
    """
    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"admin:approve:{event_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"admin:reject:{event_id}"),
        ],
        [
            InlineKeyboardButton("✏️ Edit Fields", callback_data=f"admin:edit:{event_id}"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def build_admin_edit_field_keyboard(event_id: int) -> InlineKeyboardMarkup:
    """
    Field picker for admin editing.
    """
    keyboard = [
        [
            InlineKeyboardButton("✏️ Edit Title", callback_data=f"admin:editfield:title:{event_id}"),
            InlineKeyboardButton("📅 Edit Date/Time", callback_data=f"admin:editfield:date:{event_id}"),
        ],
        [
            InlineKeyboardButton("📍 Edit Location", callback_data=f"admin:editfield:loc:{event_id}"),
            InlineKeyboardButton("🏷️ Edit Category", callback_data=f"admin:editfield:cat:{event_id}"),
        ],
        [
            InlineKeyboardButton("🏛️ Edit Club", callback_data=f"admin:editfield:club:{event_id}"),
            InlineKeyboardButton("🔙 Done / Back", callback_data=f"admin:editfield:done:{event_id}"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

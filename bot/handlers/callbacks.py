import logging
from telegram import Update
from telegram.ext import ContextTypes
from .start import start_command
from .today import today_command
from .week import week_command
from .events import show_category_picker, show_category_events
from .admin import handle_admin_approve, handle_admin_reject, handle_admin_edit_start

logger = logging.getLogger(__name__)


async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Central router for all callback queries (inline button clicks).
    Updates existing messages in place.
    """
    query = update.callback_query
    if not query:
        return

    data = query.data or ""
    await query.answer()

    if data == "noop":
        return

    # Main menu navigation
    if data == "btn:main_menu":
        await start_command(update, context)
        return

    # Start menu button shortcuts
    if data == "btn:today":
        await today_command(update, context, page=1)
        return
    elif data == "btn:week":
        await week_command(update, context)
        return
    elif data == "btn:categories":
        await show_category_picker(update, context)
        return

    # Admin actions
    if data.startswith("admin:approve:"):
        await handle_admin_approve(update, context)
        return
    elif data.startswith("admin:reject:"):
        await handle_admin_reject(update, context)
        return
    elif data.startswith("admin:edit:"):
        await handle_admin_edit_start(update, context)
        return

    # Pagination callbacks
    # Format: page:today:<page_number>
    if data.startswith("page:today:"):
        try:
            page = int(data.split(":")[2])
            await today_command(update, context, page=page)
        except (IndexError, ValueError) as e:
            logger.error("Invalid today pagination callback %s: %s", data, e)
        return

    # Format: page:cat:<cat_id>:<page_number>
    if data.startswith("page:cat:"):
        try:
            parts = data.split(":")
            cat_id = parts[2]
            page = int(parts[3])
            await show_category_events(update, category_identifier=cat_id, page=page)
        except (IndexError, ValueError) as e:
            logger.error("Invalid category pagination callback %s: %s", data, e)
        return

    # Category selection callback
    # Format: cat:select:<cat_id>
    if data.startswith("cat:select:"):
        try:
            cat_id = data.split(":")[2]
            await show_category_events(update, category_identifier=cat_id, page=1)
        except IndexError as e:
            logger.error("Invalid category selection callback %s: %s", data, e)
        return

    logger.warning("Unhandled callback query data: %s", data)

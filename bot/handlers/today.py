import logging
from telegram import Update
from telegram.ext import ContextTypes
from ..api_client import api_client
from ..formatters import format_today_events
from ..pagination import build_pagination_keyboard
from ..config import PAGE_SIZE
from .events import safe_edit_or_reply

logger = logging.getLogger(__name__)


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 1) -> None:
    """
    /today handler: fetches events for today from the REST API and renders them with pagination and main menu button.
    """
    try:
        events = await api_client.get_events(range_type='today')
        text, total_pages, total_count = format_today_events(events, page=page, page_size=PAGE_SIZE)
        keyboard = build_pagination_keyboard(
            current_page=page,
            total_pages=total_pages,
            callback_prefix="page:today",
            show_main_menu=True,
        )
        await safe_edit_or_reply(update, text=text, reply_markup=keyboard)
    except Exception as e:
        if "Message is not modified" in str(e):
            return
        logger.error("Error in /today command: %s", e)
        error_msg = "⚠️ *Unable to reach Events server.*\nPlease try again in a few moments."
        await safe_edit_or_reply(update, error_msg)

import logging
from telegram import Update
from telegram.ext import ContextTypes
from ..api_client import api_client
from ..formatters import format_week_events
from ..pagination import build_single_action_keyboard
from .events import safe_edit_or_reply

logger = logging.getLogger(__name__)


async def week_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /week handler: fetches events for the upcoming 7 days, renders them grouped by day,
    and includes a Main Menu button.
    """
    try:
        events = await api_client.get_events(range_type='week')
        text = format_week_events(events)
        keyboard = build_single_action_keyboard(show_main_menu=True)
        await safe_edit_or_reply(update, text=text, reply_markup=keyboard)
    except Exception as e:
        if "Message is not modified" in str(e):
            return
        logger.error("Error in /week command: %s", e)
        error_msg = "⚠️ *Unable to reach Events server.*\nPlease try again in a few moments."
        await safe_edit_or_reply(update, error_msg)

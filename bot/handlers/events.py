import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from ..api_client import api_client
from ..formatters import format_category_events
from ..pagination import build_category_keyboard, build_category_events_keyboard
from ..config import PAGE_SIZE

logger = logging.getLogger(__name__)


async def safe_edit_or_reply(
    update: Update,
    text: str,
    reply_markup=None,
    parse_mode=ParseMode.MARKDOWN,
) -> None:
    """
    Safely edits the existing callback message or replies with a new one.
    Silently ignores 'Message is not modified' errors and retries as plaintext if Markdown parsing fails.
    """
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
            )
        except Exception as e:
            if "Message is not modified" in str(e):
                return
            if parse_mode and "can't parse entities" in str(e).lower():
                plain = text.replace('*', '').replace('_', '').replace('`', '').replace('\\', '')
                await update.callback_query.edit_message_text(
                    text=plain,
                    reply_markup=reply_markup,
                )
            else:
                raise e
    else:
        try:
            await update.message.reply_text(
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
            )
        except Exception as e:
            if parse_mode and "can't parse entities" in str(e).lower():
                plain = text.replace('*', '').replace('_', '').replace('`', '').replace('\\', '')
                await update.message.reply_text(
                    text=plain,
                    reply_markup=reply_markup,
                )
            else:
                raise e


async def events_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /events [category_name] handler.
    If no category is provided, shows an interactive category picker.
    If a category is provided as argument (e.g. /events sports), queries directly.
    """
    args = context.args if context and context.args else []

    if not args:
        await show_category_picker(update, context)
        return

    category_query = " ".join(args).strip()
    await show_category_events(update, category_query, page=1)


async def show_category_picker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Renders inline buttons for each category fetched from the backend,
    including a Back to Main Menu button.
    """
    try:
        categories = await api_client.get_categories()
        if not categories:
            await safe_edit_or_reply(update, "No categories available at the moment.")
            return

        keyboard = build_category_keyboard(categories)
        prompt_text = (
            "🏷️ *Select an Event Category:*\n\n"
            "Choose a category below to see all upcoming events:"
        )
        await safe_edit_or_reply(update, text=prompt_text, reply_markup=keyboard)
    except Exception as e:
        if "Message is not modified" in str(e):
            return
        logger.error("Error loading categories: %s", e)
        error_msg = "⚠️ *Unable to load categories.*\nPlease check backend connection."
        await safe_edit_or_reply(update, error_msg)


async def show_category_events(
    update: Update,
    category_identifier: str | int,
    page: int = 1,
    category_name: str = None,
) -> None:
    """
    Fetches and renders events for a specific category with pagination
    and [🔙 Categories] + [🏠 Main Menu] navigation buttons.
    """
    try:
        events = await api_client.get_events(category=category_identifier)
        resolved_name = category_name or str(category_identifier).title()
        if events and not category_name:
            resolved_name = events[0].get('category_name', resolved_name)

        text, total_pages, total_count = format_category_events(
            category_name=resolved_name,
            events=events,
            page=page,
            page_size=PAGE_SIZE,
        )

        keyboard = build_category_events_keyboard(
            category_identifier=category_identifier,
            current_page=page,
            total_pages=total_pages,
        )
        await safe_edit_or_reply(update, text=text, reply_markup=keyboard)
    except Exception as e:
        if "Message is not modified" in str(e):
            return
        logger.error("Error fetching category events for %s: %s", category_identifier, e)
        error_msg = f"⚠️ *Error fetching events for category '{category_identifier}'.*"
        await safe_edit_or_reply(update, error_msg)

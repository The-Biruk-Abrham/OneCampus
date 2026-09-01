from telegram import Update
from telegram.ext import ContextTypes
from ..pagination import build_start_keyboard
from .events import safe_edit_or_reply


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /start and /help command handler.
    Welcomes the user and displays available commands and interactive buttons.
    """
    user_name = update.effective_user.first_name if update.effective_user else "Student"

    welcome_text = (
        f"👋 *Welcome to ASTU Events Hub, {user_name}!* 🎓\n\n"
        "Your single source of truth for all campus activities, club events, workshops, and sports at ASTU.\n\n"
        "📌 *Available Commands:*\n"
        "• `/today` — View events happening today\n"
        "• `/week` — View the 7-day schedule grouped by day\n"
        "• `/events` — Browse events by category with inline picker\n"
        "• `/submit` — Submit a new club event or forward an announcement\n"
        "• `/cancel` — Cancel any active action and return here\n"
        "• `/help` — Show this guide and command list\n\n"
        "Tap a button below to get started immediately:"
    )

    keyboard = build_start_keyboard()
    await safe_edit_or_reply(update, text=welcome_text, reply_markup=keyboard)

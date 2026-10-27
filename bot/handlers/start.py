from telegram import Update
from telegram.ext import ContextTypes
from ..config import is_owner
from ..pagination import build_start_keyboard
from .events import safe_edit_or_reply


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /start and /help command handler.
    Welcomes the user and displays available commands and interactive buttons.
    """
    user = update.effective_user
    user_name = user.first_name if user else "Student"
    user_id = user.id if user else None
    user_is_owner = is_owner(user_id)

    user_is_officer = False
    try:
        from .submit import get_user_verified_clubs
        verified_clubs = await get_user_verified_clubs(user_id)
        user_is_officer = bool(verified_clubs) or user_is_owner
    except Exception:
        user_is_officer = user_is_owner

    owner_lines = ""
    if user_is_owner:
        owner_lines = (
            "👑 *Owner Commands:*\n"
            "• `/add_club` — Register a new university club\n"
            "• `/add_club_admin` — Add a verified club representative\n"
            "• `/remove_club_admin` — Remove a club representative\n"
            "• `/officers` — View all verified club representatives\n\n"
        )

    officer_lines = ""
    if user_is_officer:
        officer_lines = "• `/submit` — Submit a new club event (verified club representatives only)\n"

    welcome_text = (
        f"👋 *Welcome to Addis Ababa Science and Technology University (AASTU) Events Hub, {user_name}!* 🎓\n\n"
        "Your single source of truth for all campus activities, club events, workshops, and sports at AASTU.\n\n"
        "📌 *Available Commands:*\n"
        "• `/today` — View events happening today\n"
        "• `/week` — View the 7-day schedule grouped by day\n"
        "• `/events` — Browse events by category with inline picker\n"
        f"{officer_lines}"
        "• `/cancel` — Cancel any active action and return here\n"
        "• `/help` — Show this guide and command list\n\n"
        f"{owner_lines}"
        "Tap a button below to get started immediately:"
    )

    keyboard = build_start_keyboard(is_owner=user_is_owner, is_officer=user_is_officer)
    await safe_edit_or_reply(update, text=welcome_text, reply_markup=keyboard)


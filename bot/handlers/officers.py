import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from ..api_client import api_client

logger = logging.getLogger(__name__)


async def add_officer_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Admin command: /add_officer <club_id> <telegram_id>
    """
    admin_id = update.effective_user.id
    args = context.args or []

    if len(args) < 2:
        await update.message.reply_text(
            "ℹ️ *Usage:* `/add_officer <club_id> <telegram_id>`\n"
            "_Example: `/add_officer 1 123456789`_",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    try:
        club_id = int(args[0])
        officer_id = int(args[1])

        club = await api_client.add_club_officer(
            club_id=club_id,
            officer_telegram_id=officer_id,
            admin_telegram_id=admin_id,
        )
        officers_list = ", ".join(str(o) for o in club.get('verified_officers', []))
        await update.message.reply_text(
            f"✅ *Verified Officer Added!*\n\n"
            f"🏛️ *Club:* {club.get('name')}\n"
            f"👥 *Verified Officers:* `{officers_list}`",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        logger.error("Error adding officer: %s", e)
        await update.message.reply_text(f"⚠️ Failed to add officer: {e}")


async def remove_officer_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Admin command: /remove_officer <club_id> <telegram_id>
    """
    admin_id = update.effective_user.id
    args = context.args or []

    if len(args) < 2:
        await update.message.reply_text(
            "ℹ️ *Usage:* `/remove_officer <club_id> <telegram_id>`\n"
            "_Example: `/remove_officer 1 123456789`_",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    try:
        club_id = int(args[0])
        officer_id = int(args[1])

        club = await api_client.remove_club_officer(
            club_id=club_id,
            officer_telegram_id=officer_id,
            admin_telegram_id=admin_id,
        )
        officers_list = ", ".join(str(o) for o in club.get('verified_officers', [])) or "None"
        await update.message.reply_text(
            f"✅ *Verified Officer Removed!*\n\n"
            f"🏛️ *Club:* {club.get('name')}\n"
            f"👥 *Verified Officers:* `{officers_list}`",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        logger.error("Error removing officer: %s", e)
        await update.message.reply_text(f"⚠️ Failed to remove officer: {e}")


async def list_officers_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Command: /officers [club_id]
    """
    args = context.args or []

    try:
        clubs = await api_client.get_clubs()
        if args and args[0].isdigit():
            target_id = int(args[0])
            clubs = [c for c in clubs if c.get('id') == target_id]

        if not clubs:
            await update.message.reply_text("No matching clubs found.")
            return

        lines = ["👥 *Verified Club Officers:*", "─" * 28]
        for club in clubs:
            officers = club.get('verified_officers', [])
            officers_str = ", ".join(f"`{o}`" for o in officers) if officers else "_None_"
            lines.append(f"• *{club.get('name')}* (ID: `{club.get('id')}`)\n  Officers: {officers_str}")

        await update.message.reply_text("\n\n".join(lines), parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error("Error listing officers: %s", e)
        await update.message.reply_text(f"⚠️ Failed to load officers: {e}")

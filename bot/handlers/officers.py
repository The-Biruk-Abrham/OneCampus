import logging
from typing import Optional, Tuple
from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from telegram.constants import ParseMode

from ..api_client import api_client
from ..config import is_owner
from ..formatters import safe_escape
from ..pagination import (
    build_owner_club_picker_keyboard,
    build_owner_officers_list_keyboard,
    build_club_genre_keyboard,
    build_start_keyboard,
)

import warnings
from telegram.warnings import PTBUserWarning
warnings.filterwarnings("ignore", message=r".*per_message=False.*", category=PTBUserWarning)

logger = logging.getLogger(__name__)

# Conversation States
(
    STATE_OWNER_ADD_CLUB_SELECT,
    STATE_OWNER_ADD_OFFICER_INPUT,
    STATE_OWNER_RM_CLUB_SELECT,
    STATE_OWNER_RM_OFFICER_INPUT,
    STATE_OWNER_CREATE_CLUB_NAME,
    STATE_OWNER_CREATE_CLUB_GENRE,
) = range(6)



UNIDENTIFIABLE_FORWARD_ERROR = (
    "⚠️ This forward doesn't include the sender's account info (it may be from a channel, "
    "or the sender has forward privacy on). Please ask them to send you a direct message "
    "you can forward instead, or type their numeric Telegram ID manually."
)


def extract_telegram_id_from_message(msg) -> Tuple[Optional[int], Optional[str], Optional[str]]:
    """
    Extracts Telegram user ID from either a forwarded message or a typed numeric string.
    Returns (telegram_id, user_display_name, error_reason).
    """
    if not msg:
        return None, None, "No message received."

    # Check if this message was forwarded in any format
    origin = getattr(msg, 'forward_origin', None)
    forward_from = getattr(msg, 'forward_from', None)
    forward_from_chat = getattr(msg, 'forward_from_chat', None)
    forward_sender_name = getattr(msg, 'forward_sender_name', None)
    forward_date = getattr(msg, 'forward_date', None)

    is_forward = bool(origin or forward_from or forward_from_chat or forward_sender_name or forward_date)

    if is_forward:
        # 1. Forward origin (PTB v20+)
        if origin:
            origin_type = getattr(origin, 'type', '')
            if origin_type == 'user' and getattr(origin, 'sender_user', None):
                u = origin.sender_user
                display = u.full_name or (f"@{u.username}" if getattr(u, 'username', None) else str(u.id))
                return u.id, display, None
            else:
                return None, None, UNIDENTIFIABLE_FORWARD_ERROR

        # 2. Legacy forward_from
        if forward_from:
            u = forward_from
            display = u.full_name or (f"@{u.username}" if getattr(u, 'username', None) else str(u.id))
            return u.id, display, None

        # Forwarded from channel, chat, hidden user, or unidentifiable sender
        return None, None, UNIDENTIFIABLE_FORWARD_ERROR

    # 3. Direct numeric ID input
    text = (msg.text or "").strip()
    if text.isdigit():
        return int(text), f"ID `{text}`", None

    return None, None, (
        "❌ Please either *forward a message* from the representative, or type their numeric Telegram ID (e.g. `123456789`)."
    )


# -------------------------------------------------------------------------
# ADD CLUB ADMIN FLOW
# -------------------------------------------------------------------------

async def start_owner_add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Entry point for owner to add a verified club representative.
    Triggered by [➕ Add Club Admin] button or /add_club_admin command.
    """
    user_id = update.effective_user.id if update.effective_user else None
    if not is_owner(user_id):
        msg = "⛔ *Access Denied:* Only the bot owner is authorized to manage club representatives."
        if update.callback_query:
            await update.callback_query.answer(msg, show_alert=True)
        elif update.message:
            await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END

    if update.callback_query:
        await update.callback_query.answer()

    context.user_data.clear()
    context.user_data['officer_manage'] = {'action': 'add'}

    try:
        clubs = await api_client.get_clubs()
        if not clubs:
            msg = "⚠️ No registered clubs found in database."
            if update.callback_query:
                await update.callback_query.edit_message_text(msg)
            elif update.message:
                await update.message.reply_text(msg)
            return ConversationHandler.END

        keyboard = build_owner_club_picker_keyboard(clubs, action="add")
        prompt = (
            "👑 *Owner Portal — Add Club Admin*\n\n"
            "🏛️ *Step 1:* Select the club you want to add a verified representative for:"
        )

        if update.callback_query:
            await update.callback_query.edit_message_text(prompt, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
        elif update.message:
            await update.message.reply_text(prompt, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)

        return STATE_OWNER_ADD_CLUB_SELECT
    except Exception as e:
        logger.error("Error loading clubs for owner add admin: %s", e, exc_info=True)
        err_msg = f"⚠️ Error loading clubs: {e}"
        if update.callback_query:
            await update.callback_query.edit_message_text(err_msg)
        elif update.message:
            await update.message.reply_text(err_msg)
        return ConversationHandler.END


async def handle_owner_add_club_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Processes club selection and prompts owner for the representative's ID or forward.
    """
    query = update.callback_query
    await query.answer()

    data = query.data
    if data == "owner:cancel":
        await query.edit_message_text("❌ Action cancelled.")
        context.user_data.clear()
        return ConversationHandler.END

    parts = data.split(":")
    club_id = int(parts[2])

    club_name = f"Club #{club_id}"
    try:
        clubs = await api_client.get_clubs()
        for c in clubs:
            if c.get('id') == club_id:
                club_name = c.get('name')
                break
    except Exception:
        pass

    context.user_data['officer_manage'] = {
        'action': 'add',
        'club_id': club_id,
        'club_name': club_name,
    }

    prompt = (
        f"🏛️ *Selected Club:* **{safe_escape(club_name)}**\n\n"
        "👤 *Step 2: Add Representative*\n"
        "Please provide the representative's Telegram account:\n\n"
        "1️⃣ *Forward a message* from that person to this chat _(Recommended & Easiest)_, or\n"
        "2️⃣ *Type their numeric Telegram ID* directly (e.g. `123456789`).\n\n"
        "_Send /cancel anytime to exit._"
    )

    await query.edit_message_text(prompt, parse_mode=ParseMode.MARKDOWN)
    return STATE_OWNER_ADD_OFFICER_INPUT


async def handle_owner_add_officer_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Extracts representative Telegram ID from forwarded message or numeric input,
    and calls backend API to register them as a verified officer.
    """
    manage_data = context.user_data.get('officer_manage', {})
    club_id = manage_data.get('club_id')
    club_name = manage_data.get('club_name', f"Club #{club_id}")
    owner_id = update.effective_user.id

    if not club_id:
        await update.message.reply_text("Session expired. Please start again with /add_club_admin.")
        context.user_data.clear()
        return ConversationHandler.END

    msg = update.message
    target_id, target_name, error_reason = extract_telegram_id_from_message(msg)

    if error_reason:
        await update.message.reply_text(error_reason, parse_mode=ParseMode.MARKDOWN)
        return STATE_OWNER_ADD_OFFICER_INPUT

    try:
        updated_club = await api_client.add_club_officer(
            club_id=club_id,
            officer_telegram_id=target_id,
            admin_telegram_id=owner_id,
        )

        officers = updated_club.get('verified_officers', [])
        officers_str = ", ".join(f"`{o}`" for o in officers) if officers else "_None_"

        success_text = (
            "✅ *Verified Club Representative Added!*\n\n"
            f"🏛️ *Club:* {safe_escape(updated_club.get('name', club_name))}\n"
            f"👤 *New Officer:* `{target_id}` ({safe_escape(target_name)})\n"
            f"👥 *All Verified Officers ({len(officers)}):* {officers_str}\n\n"
            "This user can now submit events for this club via `/submit` or by forwarding posts to the bot."
        )

        await update.message.reply_text(success_text, parse_mode=ParseMode.MARKDOWN)
        context.user_data.clear()
        return ConversationHandler.END
    except Exception as e:
        logger.error("Error adding officer via owner flow: %s", e, exc_info=True)
        await update.message.reply_text(
            f"⚠️ *Failed to add representative:*\n`{safe_escape(str(e))}`",
            parse_mode=ParseMode.MARKDOWN,
        )
        context.user_data.clear()
        return ConversationHandler.END


# -------------------------------------------------------------------------
# REMOVE CLUB ADMIN FLOW
# -------------------------------------------------------------------------

async def start_owner_remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Entry point for owner to remove a verified club representative.
    Triggered by [➖ Remove Club Admin] button or /remove_club_admin command.
    """
    user_id = update.effective_user.id if update.effective_user else None
    if not is_owner(user_id):
        msg = "⛔ *Access Denied:* Only the bot owner is authorized to manage club representatives."
        if update.callback_query:
            await update.callback_query.answer(msg, show_alert=True)
        elif update.message:
            await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END

    if update.callback_query:
        await update.callback_query.answer()

    context.user_data.clear()
    context.user_data['officer_manage'] = {'action': 'remove'}

    try:
        clubs = await api_client.get_clubs()
        if not clubs:
            msg = "⚠️ No registered clubs found in database."
            if update.callback_query:
                await update.callback_query.edit_message_text(msg)
            elif update.message:
                await update.message.reply_text(msg)
            return ConversationHandler.END

        keyboard = build_owner_club_picker_keyboard(clubs, action="rm")
        prompt = (
            "👑 *Owner Portal — Remove Club Admin*\n\n"
            "🏛️ *Step 1:* Select the club you want to remove a representative from:"
        )

        if update.callback_query:
            await update.callback_query.edit_message_text(prompt, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
        elif update.message:
            await update.message.reply_text(prompt, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)

        return STATE_OWNER_RM_CLUB_SELECT
    except Exception as e:
        logger.error("Error loading clubs for owner remove admin: %s", e, exc_info=True)
        err_msg = f"⚠️ Error loading clubs: {e}"
        if update.callback_query:
            await update.callback_query.edit_message_text(err_msg)
        elif update.message:
            await update.message.reply_text(err_msg)
        return ConversationHandler.END


async def handle_owner_rm_club_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Processes club selection and shows existing verified officers with one-tap removal buttons.
    """
    query = update.callback_query
    await query.answer()

    data = query.data
    if data == "owner:cancel":
        await query.edit_message_text("❌ Action cancelled.")
        context.user_data.clear()
        return ConversationHandler.END

    parts = data.split(":")
    club_id = int(parts[2])

    club_name = f"Club #{club_id}"
    officers = []
    try:
        clubs = await api_client.get_clubs()
        for c in clubs:
            if c.get('id') == club_id:
                club_name = c.get('name')
                officers = c.get('verified_officers') or []
                break
    except Exception:
        pass

    context.user_data['officer_manage'] = {
        'action': 'remove',
        'club_id': club_id,
        'club_name': club_name,
    }

    if not officers:
        await query.edit_message_text(
            f"ℹ️ *{safe_escape(club_name)}* currently has no registered verified representatives.",
            parse_mode=ParseMode.MARKDOWN,
        )
        context.user_data.clear()
        return ConversationHandler.END

    keyboard = build_owner_officers_list_keyboard(club_id, officers)
    prompt = (
        f"🏛️ *Selected Club:* **{safe_escape(club_name)}**\n\n"
        f"👥 *Current Representatives ({len(officers)}):*\n"
        "Tap a button below to remove an officer, or forward a message / type an ID:"
    )

    await query.edit_message_text(prompt, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
    return STATE_OWNER_RM_OFFICER_INPUT


async def handle_owner_rm_officer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handles inline button tap to remove a specific officer.
    """
    query = update.callback_query
    await query.answer()

    data = query.data
    if data == "owner:cancel":
        await query.edit_message_text("❌ Action cancelled.")
        context.user_data.clear()
        return ConversationHandler.END

    parts = data.split(":")
    club_id = int(parts[2])
    officer_id = int(parts[3])
    owner_id = update.effective_user.id

    try:
        updated_club = await api_client.remove_club_officer(
            club_id=club_id,
            officer_telegram_id=officer_id,
            admin_telegram_id=owner_id,
        )

        officers = updated_club.get('verified_officers', [])
        officers_str = ", ".join(f"`{o}`" for o in officers) if officers else "_None_"

        success_text = (
            "✅ *Verified Club Representative Removed!*\n\n"
            f"🏛️ *Club:* {safe_escape(updated_club.get('name'))}\n"
            f"👤 *Removed Officer ID:* `{officer_id}`\n"
            f"👥 *Remaining Officers ({len(officers)}):* {officers_str}"
        )

        await query.edit_message_text(success_text, parse_mode=ParseMode.MARKDOWN)
        context.user_data.clear()
        return ConversationHandler.END
    except Exception as e:
        logger.error("Error removing officer via button: %s", e, exc_info=True)
        await query.edit_message_text(f"⚠️ Failed to remove officer: {e}")
        context.user_data.clear()
        return ConversationHandler.END


async def handle_owner_rm_officer_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handles typed ID or forwarded message to remove an officer.
    """
    manage_data = context.user_data.get('officer_manage', {})
    club_id = manage_data.get('club_id')
    club_name = manage_data.get('club_name', f"Club #{club_id}")
    owner_id = update.effective_user.id

    if not club_id:
        await update.message.reply_text("Session expired. Please start again with /remove_club_admin.")
        context.user_data.clear()
        return ConversationHandler.END

    msg = update.message
    target_id, target_name, error_reason = extract_telegram_id_from_message(msg)

    if error_reason:
        await update.message.reply_text(error_reason, parse_mode=ParseMode.MARKDOWN)
        return STATE_OWNER_RM_OFFICER_INPUT

    try:
        updated_club = await api_client.remove_club_officer(
            club_id=club_id,
            officer_telegram_id=target_id,
            admin_telegram_id=owner_id,
        )

        officers = updated_club.get('verified_officers', [])
        officers_str = ", ".join(f"`{o}`" for o in officers) if officers else "_None_"

        success_text = (
            "✅ *Verified Club Representative Removed!*\n\n"
            f"🏛️ *Club:* {safe_escape(updated_club.get('name', club_name))}\n"
            f"👤 *Removed Officer:* `{target_id}`\n"
            f"👥 *Remaining Officers ({len(officers)}):* {officers_str}"
        )

        await update.message.reply_text(success_text, parse_mode=ParseMode.MARKDOWN)
        context.user_data.clear()
        return ConversationHandler.END
    except Exception as e:
        logger.error("Error removing officer via text input: %s", e, exc_info=True)
        await update.message.reply_text(
            f"⚠️ *Failed to remove representative:*\n`{safe_escape(str(e))}`",
            parse_mode=ParseMode.MARKDOWN,
        )
        context.user_data.clear()
        return ConversationHandler.END


async def cancel_owner_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the owner action cleanly."""
    context.user_data.clear()
    msg = "❌ Action cancelled. Returning to main menu."
    user_id = update.effective_user.id if update.effective_user else None
    keyboard = build_start_keyboard(is_owner=is_owner(user_id))
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(msg, reply_markup=keyboard)
    elif update.message:
        await update.message.reply_text(msg, reply_markup=keyboard)
    return ConversationHandler.END


# -------------------------------------------------------------------------
# DIRECT CLI COMMANDS & UTILITIES
# -------------------------------------------------------------------------

async def add_officer_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Command: /add_officer <club_id> <telegram_id> or interactive /add_club_admin
    """
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text(
            "⛔ *Access Denied:* Only the bot owner is authorized to manage club representatives.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    args = context.args or []
    if len(args) < 2:
        await start_owner_add_admin(update, context)
        return

    try:
        club_id = int(args[0])
        officer_id = int(args[1])

        club = await api_client.add_club_officer(
            club_id=club_id,
            officer_telegram_id=officer_id,
            admin_telegram_id=user_id,
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
    Command: /remove_officer <club_id> <telegram_id> or interactive /remove_club_admin
    """
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text(
            "⛔ *Access Denied:* Only the bot owner is authorized to manage club representatives.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    args = context.args or []
    if len(args) < 2:
        await start_owner_remove_admin(update, context)
        return

    try:
        club_id = int(args[0])
        officer_id = int(args[1])

        club = await api_client.remove_club_officer(
            club_id=club_id,
            officer_telegram_id=officer_id,
            admin_telegram_id=user_id,
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


# -------------------------------------------------------------------------
# REGISTER NEW CLUB FLOW (OWNER)
# -------------------------------------------------------------------------

async def start_owner_create_club(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Entry point for owner to register a new club in the system.
    Triggered by [🏛️ Register New Club] button or /add_club command.
    """
    user_id = update.effective_user.id if update.effective_user else None
    if not is_owner(user_id):
        msg = "⛔ *Access Denied:* Only the bot owner is authorized to register new clubs."
        if update.callback_query:
            await update.callback_query.answer(msg, show_alert=True)
        elif update.message:
            await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END

    if update.callback_query:
        await update.callback_query.answer()

    context.user_data.clear()
    context.user_data['create_club'] = {}

    prompt = (
        "👑 *Owner Portal — Register New Club*\n\n"
        "🏛️ *Step 1 of 2: Club Name*\n"
        "Please type the official name of the university club or organization:\n\n"
        "_Example: ASTU IEEE Student Branch_"
    )

    if update.callback_query:
        await update.callback_query.edit_message_text(prompt, parse_mode=ParseMode.MARKDOWN)
    elif update.message:
        await update.message.reply_text(prompt, parse_mode=ParseMode.MARKDOWN)

    return STATE_OWNER_CREATE_CLUB_NAME


async def handle_owner_create_club_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Saves club name and prompts owner for club genre / category type.
    """
    name = update.message.text.strip() if update.message and update.message.text else ""
    if not name:
        await update.message.reply_text("Please enter a valid club name:")
        return STATE_OWNER_CREATE_CLUB_NAME

    if len(name) > 200:
        await update.message.reply_text("❌ Club name is too long (max 200 characters). Please type a shorter name:")
        return STATE_OWNER_CREATE_CLUB_NAME

    if 'create_club' not in context.user_data:
        context.user_data['create_club'] = {}

    context.user_data['create_club']['name'] = name

    keyboard = build_club_genre_keyboard()
    prompt = (
        f"🏛️ *Club Name:* **{safe_escape(name)}**\n\n"
        "🏷️ *Step 2 of 2: Club Genre / Category Type*\n"
        "Select a genre below or type a custom genre (e.g. _Robotics, Environmental, Chess_):"
    )

    await update.message.reply_text(prompt, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
    return STATE_OWNER_CREATE_CLUB_GENRE


async def _finish_club_creation(update: Update, context: ContextTypes.DEFAULT_TYPE, genre: str, is_callback: bool = False) -> int:
    """Helper to finalize club creation via REST API."""
    create_data = context.user_data.get('create_club', {})
    name = create_data.get('name')
    owner_id = update.effective_user.id

    if not name:
        msg = "⚠️ Session expired. Please start again with /add_club."
        if is_callback:
            await update.callback_query.edit_message_text(msg)
        else:
            await update.message.reply_text(msg)
        context.user_data.clear()
        return ConversationHandler.END

    try:
        new_club = await api_client.create_club(
            name=name,
            category_type=genre,
            admin_telegram_id=owner_id,
        )

        success_text = (
            "🎉 *New Club Successfully Registered!*\n\n"
            f"🏛️ *Club Name:* **{safe_escape(new_club.get('name'))}**\n"
            f"🏷️ *Genre / Type:* `{safe_escape(new_club.get('category_type') or 'General')}`\n"
            f"🆔 *Club ID:* `{new_club.get('id')}`\n\n"
            "✨ This club is now listed in the system. You can assign verified representatives to it anytime using `➕ Add Club Admin`."
        )

        if is_callback:
            await update.callback_query.edit_message_text(success_text, parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(success_text, parse_mode=ParseMode.MARKDOWN)

        context.user_data.clear()
        return ConversationHandler.END
    except Exception as e:
        logger.error("Error creating club: %s", e, exc_info=True)
        err_text = f"⚠️ *Failed to register club:*\n`{safe_escape(str(e))}`"
        if is_callback:
            await update.callback_query.edit_message_text(err_text, parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(err_text, parse_mode=ParseMode.MARKDOWN)
        context.user_data.clear()
        return ConversationHandler.END


async def handle_owner_create_club_genre_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles preset genre button click during club registration."""
    query = update.callback_query
    await query.answer()

    data = query.data
    if data == "owner:cancel":
        await query.edit_message_text("❌ Action cancelled.")
        context.user_data.clear()
        return ConversationHandler.END

    genre = data.split(":")[2]
    return await _finish_club_creation(update, context, genre=genre, is_callback=True)


async def handle_owner_create_club_genre_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles free-text genre input during club registration."""
    genre = update.message.text.strip() if update.message and update.message.text else "General"
    return await _finish_club_creation(update, context, genre=genre, is_callback=False)


# -------------------------------------------------------------------------
# DIRECT CLI COMMANDS & UTILITIES
# -------------------------------------------------------------------------

async def add_club_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Command: /add_club [name]
    """
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text(
            "⛔ *Access Denied:* Only the bot owner is authorized to register new clubs.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    args = context.args or []
    if not args:
        await start_owner_create_club(update, context)
        return

    club_name = " ".join(args).strip()
    context.user_data['create_club'] = {'name': club_name}
    keyboard = build_club_genre_keyboard()
    await update.message.reply_text(
        f"🏛️ *Registering:* **{safe_escape(club_name)}**\n\n"
        "🏷️ Select a category/genre for this club or type a custom one:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
    )


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

        lines = ["👥 *Verified Club Representatives:*", "─" * 28]
        for club in clubs:
            officers = club.get('verified_officers', [])
            officers_str = ", ".join(f"`{o}`" for o in officers) if officers else "_None_"
            lines.append(f"• *{club.get('name')}* (ID: `{club.get('id')}`)\n  Officers: {officers_str}")

        await update.message.reply_text("\n\n".join(lines), parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error("Error listing officers: %s", e)
        await update.message.reply_text(f"⚠️ Failed to load officers: {e}")


def get_officer_management_conversation_handler() -> ConversationHandler:
    """
    Builds the ConversationHandler for owner club & representative management.
    """
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_owner_add_admin, pattern="^owner:add_admin$"),
            CallbackQueryHandler(start_owner_remove_admin, pattern="^owner:remove_admin$"),
            CallbackQueryHandler(start_owner_create_club, pattern="^owner:create_club$"),
            CommandHandler("add_club_admin", start_owner_add_admin),
            CommandHandler("remove_club_admin", start_owner_remove_admin),
            CommandHandler("add_club", start_owner_create_club),
        ],
        states={
            STATE_OWNER_ADD_CLUB_SELECT: [
                CallbackQueryHandler(handle_owner_add_club_selected, pattern="^owner:club_add:"),
            ],
            STATE_OWNER_ADD_OFFICER_INPUT: [
                MessageHandler(filters.ALL & ~filters.COMMAND, handle_owner_add_officer_input),
            ],
            STATE_OWNER_RM_CLUB_SELECT: [
                CallbackQueryHandler(handle_owner_rm_club_selected, pattern="^owner:club_rm:"),
            ],
            STATE_OWNER_RM_OFFICER_INPUT: [
                CallbackQueryHandler(handle_owner_rm_officer_callback, pattern="^owner:rm_officer:"),
                MessageHandler(filters.ALL & ~filters.COMMAND, handle_owner_rm_officer_input),
            ],
            STATE_OWNER_CREATE_CLUB_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_owner_create_club_name_input),
            ],
            STATE_OWNER_CREATE_CLUB_GENRE: [
                CallbackQueryHandler(handle_owner_create_club_genre_callback, pattern="^owner:genre:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_owner_create_club_genre_input),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_owner_action),
            CallbackQueryHandler(cancel_owner_action, pattern="^owner:cancel$"),
        ],
        conversation_timeout=600,
        allow_reentry=True,
        per_chat=True,
        per_user=True,
        per_message=False,
    )



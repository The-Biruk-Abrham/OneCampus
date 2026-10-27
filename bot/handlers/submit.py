import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Any, Optional
from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    TypeHandler,
    filters,
)
from telegram.constants import ParseMode

from ..api_client import api_client
from ..config import TELEGRAM_ADMIN_GROUP_ID, TELEGRAM_PUBLIC_CHANNEL_ID, is_owner
from ..formatters import format_single_event, safe_escape
from ..pagination import (
    build_submission_confirm_keyboard,
    build_club_picker_keyboard,
    build_submission_category_keyboard,
    build_admin_approval_keyboard,
    build_start_keyboard,
)

logger = logging.getLogger(__name__)

ADDIS_TZ = ZoneInfo("Africa/Addis_Ababa")

# Conversation States
(
    STATE_CONTENT,
    STATE_TITLE,
    STATE_CLUB,
    STATE_CUSTOM_CLUB,
    STATE_CATEGORY,
    STATE_CUSTOM_CATEGORY,
    STATE_DATETIME,
    STATE_LOCATION,
    STATE_CONFIRM,
    STATE_EDIT_FIELD_INPUT,
) = range(10)


def extract_raw_content(update: Update) -> Dict[str, Any]:
    """
    Extracts raw media file_id(s), media type, and unmodified caption/text from a message.
    Handles photos, videos, animations, documents, audio, voice, polls, and forwarded channel posts.
    Preserves original captions untouched.
    """
    msg = update.message or (update.callback_query.message if update.callback_query else None)
    user = update.effective_user

    if not msg:
        return {
            "media_type": "text",
            "file_ids": [],
            "caption": "",
            "is_forwarded": False,
            "submitter_telegram_id": user.id if user else None,
            "submitter_username": user.username if user else None,
            "forward_info": {},
        }

    media_type = "text"
    file_ids = []
    caption = ""

    if msg.photo:
        media_type = "photo"
        file_ids = [msg.photo[-1].file_id]  # highest resolution photo
        caption = msg.caption or ""
    elif msg.video:
        media_type = "video"
        file_ids = [msg.video.file_id]
        caption = msg.caption or ""
    elif msg.animation:
        media_type = "animation"
        file_ids = [msg.animation.file_id]
        caption = msg.caption or ""
    elif msg.document:
        media_type = "document"
        file_ids = [msg.document.file_id]
        caption = msg.caption or ""
    elif msg.audio:
        media_type = "audio"
        file_ids = [msg.audio.file_id]
        caption = msg.caption or msg.audio.title or ""
    elif msg.voice:
        media_type = "voice"
        file_ids = [msg.voice.file_id]
        caption = msg.caption or ""
    elif msg.poll:
        media_type = "poll"
        caption = f"Poll: {msg.poll.question}"
        file_ids = []
    elif msg.text:
        media_type = "text"
        caption = msg.text
        file_ids = []
    elif msg.caption:
        media_type = "media"
        caption = msg.caption
        file_ids = []

    # Capture forward origin metadata if message was forwarded from a channel/chat
    forward_info = {}
    is_forwarded = False
    if getattr(msg, 'forward_origin', None):
        is_forwarded = True
        origin = msg.forward_origin
        forward_info['origin_type'] = str(getattr(origin, 'type', ''))
        if hasattr(origin, 'chat') and origin.chat:
            forward_info['chat_title'] = str(getattr(origin.chat, 'title', ''))
            forward_info['chat_username'] = str(getattr(origin.chat, 'username', ''))
        elif hasattr(origin, 'sender_user') and origin.sender_user:
            forward_info['sender_name'] = str(getattr(origin.sender_user, 'full_name', ''))
    elif getattr(msg, 'forward_from_chat', None):
        is_forwarded = True
        forward_info['chat_title'] = str(msg.forward_from_chat.title) if msg.forward_from_chat.title else None
        forward_info['chat_username'] = str(msg.forward_from_chat.username) if msg.forward_from_chat.username else None
    elif getattr(msg, 'forward_date', None) or getattr(msg, 'forward_from', None):
        is_forwarded = True

    return {
        "media_type": media_type,
        "file_ids": file_ids,
        "caption": caption.strip() if caption else "",
        "is_forwarded": is_forwarded,
        "submitter_telegram_id": int(user.id) if user and hasattr(user, 'id') else None,
        "submitter_username": str(user.username) if user and user.username else None,
        "forward_info": forward_info,
    }


def parse_event_datetime(dt_text: str) -> datetime:
    """
    Parses DD/MM/YYYY HH:MM (or DD/MM/YY HH:MM) string into an Addis Ababa timezone-aware datetime.
    """
    cleaned = dt_text.strip()
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%y %H:%M"):
        try:
            naive_dt = datetime.strptime(cleaned, fmt)
            return naive_dt.replace(tzinfo=ADDIS_TZ)
        except ValueError:
            continue
    raise ValueError(f"Invalid datetime format: '{dt_text}'. Expected DD/MM/YYYY HH:MM")


def _get_submission(context: ContextTypes.DEFAULT_TYPE, user_id: Any = None) -> dict:
    """
    Safely retrieves or initializes the user's submission dictionary.
    Guarantees context.user_data['submission'] exists and prevents KeyError.
    """
    if 'submission' not in context.user_data or not isinstance(context.user_data['submission'], dict):
        logger.warning(
            "Accessed context.user_data['submission'] when not present for user_id=%s. Auto-initializing empty submission dict.",
            user_id or "unknown"
        )
        context.user_data['submission'] = {}
    return context.user_data['submission']


import warnings
from telegram.warnings import PTBUserWarning
warnings.filterwarnings("ignore", message=r".*per_message=False.*", category=PTBUserWarning)


async def is_user_admin_or_owner(user_id: Any) -> bool:
    """Check if the user is the bot owner or an active admin."""
    if not user_id:
        return False
    if is_owner(user_id):
        return True
    try:
        return await api_client.check_admin_status(int(user_id))
    except Exception:
        return False


def render_preview_text(sub: Dict[str, Any], is_direct_publish: bool = False) -> str:
    """
    Renders full structured submission preview text.
    """
    title_escaped = safe_escape(sub.get('title', 'Untitled'))
    club_escaped = safe_escape(sub.get('club_name', 'Not Selected'))
    if sub.get('is_custom_club'):
        club_escaped += " _(Custom / Unverified)_"

    cat_escaped = safe_escape(sub.get('category_name', 'Not Selected'))
    if sub.get('is_custom_category'):
        cat_escaped += " _(Custom / Unlisted)_"

    dt_display_escaped = safe_escape(sub.get('start_datetime_display', 'Not Set'))
    location_escaped = safe_escape(sub.get('location', 'Not Set'))

    raw_content = sub.get('raw_content', {})
    media_type = raw_content.get('media_type', 'None').title()

    lines = [
        "🔍 *SUBMISSION PREVIEW*",
        "─" * 28,
        f"📌 *Title:* {title_escaped}",
        f"🏛️ *Host Club:* {club_escaped}",
        f"🏷️ *Category:* {cat_escaped}",
        f"📅 *Date & Time:* {dt_display_escaped}",
        f"📍 *Venue:* {location_escaped}",
        f"📷 *Media Attached:* {media_type}",
    ]

    caption = raw_content.get('caption')
    if caption:
        cap_clean = caption[:140] + "..." if len(caption) > 140 else caption
        lines.append(f"📝 *Original Text:* _{safe_escape(cap_clean)}_")

    if is_direct_publish or sub.get('is_direct_publish'):
        lines.append("\n⚡ *This will be published immediately to the channel (you are an admin/owner).*")
    else:
        lines.append("\n_Check the details above. Tap any button below to edit a field, or Confirm to submit:_")

    return "\n".join(lines)


async def get_user_verified_clubs(user_id: Any) -> list[Dict[str, Any]]:
    """
    Returns the list of clubs where this Telegram user_id is in verified_officers.
    If the user is the bot owner, returns all registered clubs.
    """
    if not user_id:
        return []
    clubs = await api_client.get_clubs()
    if is_owner(user_id):
        return clubs
    return [
        c for c in clubs
        if str(user_id) in [str(o) for o in (c.get('verified_officers') or [])]
    ]


async def start_submission(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Entry point for /submit or initial submission trigger.
    Explicitly checks officer status and initializes context.user_data['submission'].
    """
    user = update.effective_user
    user_id = user.id if user else None
    context.user_data.clear()

    try:
        verified_clubs = await get_user_verified_clubs(user_id)
        user_is_admin = await is_user_admin_or_owner(user_id)
    except Exception as e:
        logger.error("Error checking verified officer status for user %s: %s", user_id, e)
        verified_clubs = []
        user_is_admin = False

    if not verified_clubs and not user_is_admin:
        rejection_text = (
            "⚠️ *Access Restricted*\n\n"
            "Only registered club representatives can submit events to Addis Ababa Science and Technology University (AASTU) Events Hub.\n\n"
            "If you are a club officer, please contact the admin team to register your Telegram account as a verified representative."
        )
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(rejection_text, parse_mode=ParseMode.MARKDOWN)
        elif update.message:
            await update.message.reply_text(rejection_text, parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END

    sub = _get_submission(context, user_id)
    sub['verified_clubs'] = verified_clubs
    sub['is_direct_publish'] = user_is_admin

    intro_text = (
        "📝 *Event Submission Wizard*\n\n"
        "Forward an announcement post (with photo, video, or text) from your club channel, "
        "or send a photo/text directly to begin.\n\n"
        "Or simply send a message with the event description now:"
    )

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(intro_text, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(intro_text, parse_mode=ParseMode.MARKDOWN)

    return STATE_CONTENT


async def handle_content_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Processes forwarded post or direct content received from user.
    Guarantees officer authorization check and context.user_data['submission'] initialization.
    Safeguards against hijacking other active conversation flows (e.g. Officer Management or Admin Edit).
    """
    # 1. State Scope Check: verify if the user is currently in another active conversation flow
    if 'officer_manage' in context.user_data and isinstance(context.user_data['officer_manage'], dict):
        manage_data = context.user_data['officer_manage']
        action = manage_data.get('action')
        if action == 'add':
            from .officers import handle_owner_add_officer_input
            if 'club_id' in manage_data:
                await handle_owner_add_officer_input(update, context)
            else:
                if update.message:
                    await update.message.reply_text("⚠️ Please select a club from the buttons above first, or send /cancel to exit.")
            return ConversationHandler.END
        elif action == 'remove':
            from .officers import handle_owner_rm_officer_input
            if 'club_id' in manage_data:
                await handle_owner_rm_officer_input(update, context)
            else:
                if update.message:
                    await update.message.reply_text("⚠️ Please select a club from the buttons above first, or send /cancel to exit.")
            return ConversationHandler.END

    if 'create_club' in context.user_data and isinstance(context.user_data['create_club'], dict):
        from .officers import handle_owner_create_club_name_input
        if 'name' not in context.user_data['create_club']:
            await handle_owner_create_club_name_input(update, context)
            return ConversationHandler.END

    if 'admin_edit' in context.user_data and isinstance(context.user_data['admin_edit'], dict):
        from .admin import handle_admin_edit_field_input
        await handle_admin_edit_field_input(update, context)
        return ConversationHandler.END

    user = update.effective_user
    user_id = user.id if user else None

    # Gate check if this was a direct forward or media message without prior /submit
    sub_data = context.user_data.get('submission')
    if not isinstance(sub_data, dict) or 'verified_clubs' not in sub_data:
        try:
            verified_clubs = await get_user_verified_clubs(user_id)
        except Exception as e:
            logger.error("Error checking officer status in handle_content_received: %s", e)
            verified_clubs = []

        if not verified_clubs:
            rejection_text = (
                "⚠️ *Access Restricted*\n\n"
                "Only registered club representatives can submit events to ASTU Events Hub.\n\n"
                "If you are a club officer, please contact the admin team to register your Telegram account as a verified representative."
            )
            if update.message:
                await update.message.reply_text(rejection_text, parse_mode=ParseMode.MARKDOWN)
            elif update.callback_query:
                await update.callback_query.message.reply_text(rejection_text, parse_mode=ParseMode.MARKDOWN)
            return ConversationHandler.END

        sub = _get_submission(context, user_id)
        sub['verified_clubs'] = verified_clubs
    else:
        sub = _get_submission(context, user_id)

    try:
        raw_content = extract_raw_content(update)
        sub['raw_content'] = raw_content

        prompt = (
            "✅ *Media & Announcement Captured!*\n\n"
            "📝 *Step 1 of 5: Event Title*\n"
            "Please enter a short Title for this event (e.g. _Robotics Workshop 2026_):"
        )
        if update.message:
            await update.message.reply_text(prompt, parse_mode=ParseMode.MARKDOWN)
        elif update.callback_query:
            await update.callback_query.message.reply_text(prompt, parse_mode=ParseMode.MARKDOWN)

        return STATE_TITLE
    except Exception as e:
        logger.error("Error in handle_content_received: %s", e, exc_info=True)
        if update.message:
            await update.message.reply_text(
                "✅ Media received.\n\n📝 *Step 1 of 5: Event Title*\nPlease enter a short Title for this event:",
                parse_mode=ParseMode.MARKDOWN,
            )
        return STATE_TITLE


async def handle_title_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Saves event title and proceeds to Club selection.
    Auto-fills club if officer represents 1 club; shows verified club picker if >1.
    """
    title = update.message.text.strip() if update.message and update.message.text else ""
    if not title:
        await update.message.reply_text("Please enter a valid title:")
        return STATE_TITLE

    user_id = update.effective_user.id if update.effective_user else "unknown"
    sub = _get_submission(context, user_id)
    sub['title'] = title

    # If user was editing just the title from the preview screen
    if sub.pop('editing_from_preview', None):
        preview_text = render_preview_text(sub)
        keyboard = build_submission_confirm_keyboard()
        await update.message.reply_text(preview_text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
        return STATE_CONFIRM

    try:
        verified_clubs = sub.get('verified_clubs')
        if not verified_clubs:
            verified_clubs = await get_user_verified_clubs(user_id)
            sub['verified_clubs'] = verified_clubs

        if len(verified_clubs) == 1:
            club = verified_clubs[0]
            sub['club'] = club['id']
            sub['club_name'] = club['name']
            sub['is_custom_club'] = False

            # Auto-selected club! Move straight to Category
            categories = await api_client.get_categories()
            keyboard = build_submission_category_keyboard(categories)
            club_name_esc = safe_escape(club['name'])
            prompt = (
                f"🏛️ *Host Club:* {club_name_esc} _(Auto-selected as you are a verified officer)_\n\n"
                "🏷️ *Step 3 of 5: Event Category*\n"
                "Select an event category or choose ➕ Other:"
            )
            await update.message.reply_text(prompt, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
            return STATE_CATEGORY
        else:
            # Show club picker with only their verified clubs (or custom option for owner)
            include_other = is_owner(user_id)
            keyboard = build_club_picker_keyboard(verified_clubs, include_other=include_other)
            await update.message.reply_text(
                "🏛️ *Step 2 of 5: Host Club / Organization*\n"
                "Select which of your verified clubs this event is for:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
            return STATE_CLUB
    except Exception as e:
        logger.error("Error loading clubs during submission: %s", e, exc_info=True)
        await update.message.reply_text(
            f"⚠️ Unable to load clubs ({e}). Please try /submit again."
        )
        return ConversationHandler.END


async def handle_club_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Processes club selection callback (preset club or Other).
    """
    query = update.callback_query
    await query.answer()

    data = query.data
    if data == "submit:cancel":
        await query.edit_message_text("❌ Submission cancelled.")
        context.user_data.clear()
        return ConversationHandler.END

    user_id = update.effective_user.id if update.effective_user else "unknown"
    sub = _get_submission(context, user_id)

    # Check if user selected '➕ Other'
    if data == "submit:club:other":
        prompt = (
            "🏛️ *Step 2 of 5: Custom Host Club / Organization*\n\n"
            "Please type the name of your club or organization (max 50 characters):"
        )
        await query.edit_message_text(prompt, parse_mode=ParseMode.MARKDOWN)
        return STATE_CUSTOM_CLUB

    club_id = int(data.split(":")[2])
    sub['club'] = club_id
    sub['custom_club'] = ''
    sub['is_custom_club'] = False

    # Fetch club name for preview display
    try:
        clubs = await api_client.get_clubs()
        for c in clubs:
            if c.get('id') == club_id:
                sub['club_name'] = c.get('name')
                break
    except Exception:
        sub['club_name'] = f"Club #{club_id}"

    # If editing from preview, return to preview
    if sub.pop('editing_from_preview', None):
        preview_text = render_preview_text(sub)
        keyboard = build_submission_confirm_keyboard()
        await query.edit_message_text(preview_text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
        return STATE_CONFIRM

    try:
        categories = await api_client.get_categories()
        keyboard = build_submission_category_keyboard(categories)
        await query.edit_message_text(
            "🏷️ *Step 3 of 5: Event Category*\n"
            "Select an event category or choose ➕ Other:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )
        return STATE_CATEGORY
    except Exception as e:
        logger.error("Error loading categories during submission: %s", e)
        await query.edit_message_text("⚠️ Error loading categories.")
        return ConversationHandler.END


async def handle_custom_club_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Processes free-text custom club entry (max 50 chars).
    """
    text = update.message.text.strip() if update.message and update.message.text else ""
    if not text:
        await update.message.reply_text("Please type a valid club or organization name:")
        return STATE_CUSTOM_CLUB

    if len(text) > 50:
        await update.message.reply_text(
            f"❌ *Name is too long* ({len(text)}/50 characters).\n"
            "Please keep custom club names under 50 characters:\n\n"
            "Type your club name again:",
            parse_mode=ParseMode.MARKDOWN,
        )
        return STATE_CUSTOM_CLUB

    user_id = update.effective_user.id if update.effective_user else "unknown"
    sub = _get_submission(context, user_id)
    sub['club'] = None
    sub['custom_club'] = text
    sub['club_name'] = text
    sub['is_custom_club'] = True

    # If editing from preview, return to preview
    if sub.pop('editing_from_preview', None):
        preview_text = render_preview_text(sub)
        keyboard = build_submission_confirm_keyboard()
        await update.message.reply_text(preview_text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
        return STATE_CONFIRM

    try:
        categories = await api_client.get_categories()
        keyboard = build_submission_category_keyboard(categories)
        await update.message.reply_text(
            f"✅ Custom Club set: *{safe_escape(text)}*\n\n"
            "🏷️ *Step 3 of 5: Event Category*\n"
            "Select an event category or choose ➕ Other:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )
        return STATE_CATEGORY
    except Exception as e:
        logger.error("Error loading categories: %s", e)
        await update.message.reply_text("⚠️ Error loading categories.")
        return ConversationHandler.END


async def handle_category_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Processes category selection callback (preset category or Other).
    """
    query = update.callback_query
    await query.answer()

    data = query.data
    if data == "submit:cancel":
        await query.edit_message_text("❌ Submission cancelled.")
        context.user_data.clear()
        return ConversationHandler.END

    user_id = update.effective_user.id if update.effective_user else "unknown"
    sub = _get_submission(context, user_id)

    # Check if user selected '➕ Other'
    if data == "submit:cat:other":
        prompt = (
            "🏷️ *Step 3 of 5: Custom Event Category*\n\n"
            "Please type your custom category name (max 50 characters):"
        )
        await query.edit_message_text(prompt, parse_mode=ParseMode.MARKDOWN)
        return STATE_CUSTOM_CATEGORY

    cat_id = int(data.split(":")[2])
    sub['category'] = cat_id
    sub['custom_category'] = ''
    sub['is_custom_category'] = False

    try:
        cats = await api_client.get_categories()
        for c in cats:
            if c.get('id') == cat_id:
                sub['category_name'] = c.get('name')
                break
    except Exception:
        sub['category_name'] = f"Category #{cat_id}"

    # If editing from preview, return to preview
    if sub.pop('editing_from_preview', None):
        preview_text = render_preview_text(sub)
        keyboard = build_submission_confirm_keyboard()
        await query.edit_message_text(preview_text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
        return STATE_CONFIRM

    prompt = (
        "📅 *Step 4 of 5: Event Date & Time*\n\n"
        "Enter start date and time in `DD/MM/YYYY HH:MM` (24-hour clock):\n"
        "_Example: 15/09/2026 14:30_"
    )
    await query.edit_message_text(prompt, parse_mode=ParseMode.MARKDOWN)
    return STATE_DATETIME


async def handle_custom_category_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Processes free-text custom category entry (max 50 chars).
    """
    text = update.message.text.strip() if update.message and update.message.text else ""
    if not text:
        await update.message.reply_text("Please type a valid category name:")
        return STATE_CUSTOM_CATEGORY

    if len(text) > 50:
        await update.message.reply_text(
            f"❌ *Category name too long* ({len(text)}/50 characters).\n"
            "Please keep custom category names under 50 characters:\n\n"
            "Type your category name again:",
            parse_mode=ParseMode.MARKDOWN,
        )
        return STATE_CUSTOM_CATEGORY

    user_id = update.effective_user.id if update.effective_user else "unknown"
    sub = _get_submission(context, user_id)
    sub['category'] = None
    sub['custom_category'] = text
    sub['category_name'] = text
    sub['is_custom_category'] = True

    # If editing from preview, return to preview
    if sub.pop('editing_from_preview', None):
        preview_text = render_preview_text(sub)
        keyboard = build_submission_confirm_keyboard()
        await update.message.reply_text(preview_text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
        return STATE_CONFIRM

    prompt = (
        f"✅ Custom Category set: *{safe_escape(text)}*\n\n"
        "📅 *Step 4 of 5: Event Date & Time*\n\n"
        "Enter start date and time in `DD/MM/YYYY HH:MM` (24-hour clock):\n"
        "_Example: 15/09/2026 14:30_"
    )
    await update.message.reply_text(prompt, parse_mode=ParseMode.MARKDOWN)
    return STATE_DATETIME


async def handle_datetime_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Validates date/time string in DD/MM/YYYY HH:MM format.
    """
    text = update.message.text.strip() if update.message and update.message.text else ""
    user_id = update.effective_user.id if update.effective_user else "unknown"
    sub = _get_submission(context, user_id)

    try:
        dt = parse_event_datetime(text)
        sub['start_datetime_iso'] = dt.isoformat()
        sub['start_datetime_display'] = dt.strftime("%A, %B %d, %Y at %I:%M %p")
    except ValueError:
        await update.message.reply_text(
            "❌ *Invalid format.* Please enter date and time exactly as `DD/MM/YYYY HH:MM` (24-hour clock):\n"
            "_Example: 15/09/2026 14:30_",
            parse_mode=ParseMode.MARKDOWN,
        )
        return STATE_DATETIME

    # If editing from preview, return to preview
    if sub.pop('editing_from_preview', None):
        preview_text = render_preview_text(sub)
        keyboard = build_submission_confirm_keyboard()
        await update.message.reply_text(preview_text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
        return STATE_CONFIRM

    await update.message.reply_text(
        "📍 *Step 5 of 5: Event Venue / Location*\n"
        "Enter event venue or location description:\n"
        "_Example: Auditorium Hall B / Stadium / ICT 508_",
        parse_mode=ParseMode.MARKDOWN,
    )
    return STATE_LOCATION


async def handle_location_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Saves location and presents full submission preview for confirmation.
    """
    location = update.message.text.strip() if update.message and update.message.text else ""
    if not location:
        await update.message.reply_text("Please enter a valid venue / location:")
        return STATE_LOCATION

    user_id = update.effective_user.id if update.effective_user else "unknown"
    sub = _get_submission(context, user_id)
    sub['location'] = location

    # Show preview screen
    preview_text = render_preview_text(sub)
    keyboard = build_submission_confirm_keyboard()

    try:
        await update.message.reply_text(
            preview_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )
    except Exception as e:
        logger.warning("Markdown preview failed (%s). Retrying with plain text.", e)
        plain_preview = preview_text.replace('*', '').replace('_', '').replace('`', '').replace('\\', '')
        await update.message.reply_text(
            plain_preview,
            reply_markup=keyboard,
        )
    return STATE_CONFIRM


async def handle_preview_actions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handles inline button actions on the Preview screen:
    - Confirm submission
    - Cancel
    - Edit single field (Title, Club, Category, Date/Time, Location)
    """
    query = update.callback_query
    await query.answer()

    data = query.data
    user_id = update.effective_user.id if update.effective_user else "unknown"
    sub = _get_submission(context, user_id)

    if data == "submit:confirm":
        if sub.get('is_submitting'):
            return ConversationHandler.END
        sub['is_submitting'] = True
        return await handle_submission_confirmation(update, context)

    if data == "submit:cancel":
        await query.edit_message_text("❌ Event submission cancelled.")
        context.user_data.clear()
        return ConversationHandler.END

    if data == "submit:edit:title":
        sub['editing_from_preview'] = True
        await query.edit_message_text(
            "✏️ *Edit Title*\nPlease enter the updated event title:",
            parse_mode=ParseMode.MARKDOWN,
        )
        return STATE_TITLE

    if data == "submit:edit:club":
        sub['editing_from_preview'] = True
        try:
            verified_clubs = sub.get('verified_clubs') or await get_user_verified_clubs(user_id)
            if len(verified_clubs) == 1:
                # Single club officer: already set
                sub['club'] = verified_clubs[0]['id']
                sub['club_name'] = verified_clubs[0]['name']
                sub['is_custom_club'] = False
                preview_text = render_preview_text(sub)
                keyboard = build_submission_confirm_keyboard()
                await query.edit_message_text(preview_text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
                return STATE_CONFIRM

            include_other = is_owner(user_id)
            keyboard = build_club_picker_keyboard(verified_clubs, include_other=include_other)
            await query.edit_message_text(
                "🏛️ *Edit Host Club*\nSelect which of your verified clubs this event is for:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
            return STATE_CLUB
        except Exception as e:
            logger.error("Error loading clubs for edit: %s", e)
            await query.edit_message_text("⚠️ Error loading clubs.")
            return STATE_CONFIRM

    if data == "submit:edit:category":
        sub['editing_from_preview'] = True
        try:
            categories = await api_client.get_categories()
            keyboard = build_submission_category_keyboard(categories)
            await query.edit_message_text(
                "🏷️ *Edit Category*\nSelect category from the list or choose ➕ Other:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
            return STATE_CATEGORY
        except Exception as e:
            logger.error("Error loading categories: %s", e)
            await query.edit_message_text("⚠️ Error loading categories.")
            return STATE_CONFIRM

    if data == "submit:edit:datetime":
        sub['editing_from_preview'] = True
        await query.edit_message_text(
            "📅 *Edit Date & Time*\nEnter updated date and time in `DD/MM/YYYY HH:MM` format:\n_Example: 15/09/2026 14:30_",
            parse_mode=ParseMode.MARKDOWN,
        )
        return STATE_DATETIME

    if data == "submit:edit:location":
        sub['editing_from_preview'] = True
        await query.edit_message_text(
            "📍 *Edit Location*\nEnter updated venue or location description:",
            parse_mode=ParseMode.MARKDOWN,
        )
        return STATE_LOCATION

    return STATE_CONFIRM


_notified_submission_event_ids: set = set()


async def handle_submission_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    POSTs event to REST API.
    - If status is 'approved' (Admin/Owner direct publish): broadcasts immediately to public channel and sends one-line info log to Admin Group.
    - If status is 'pending' (Club representative): posts approval card to Admin Group.
    """
    query = update.callback_query
    user_id = update.effective_user.id if update.effective_user else "unknown"
    sub = _get_submission(context, user_id)

    if not sub.get('title') or not sub.get('start_datetime_iso'):
        await query.edit_message_text("⚠️ Submission session incomplete or expired. Use /submit to start again.")
        context.user_data.clear()
        return ConversationHandler.END

    payload = {
        "title": sub.get('title'),
        "club": sub.get('club'),
        "custom_club": sub.get('custom_club', ''),
        "category": sub.get('category'),
        "custom_category": sub.get('custom_category', ''),
        "start_datetime": sub.get('start_datetime_iso'),
        "location": sub.get('location', ''),
        "raw_content": sub.get('raw_content', {}),
    }

    # Clear state immediately to prevent re-entrancy / double submission
    context.user_data.clear()

    try:
        submitter_id_int = int(user_id) if str(user_id).isdigit() else None
        created_event = await api_client.create_event(payload, submitter_telegram_id=submitter_id_int)
        event_id = created_event['id']

        if created_event.get('status') == 'approved':
            # Direct Publish flow for Owner / Admins
            from .admin import broadcast_event_to_channel
            post_msg_id = await broadcast_event_to_channel(
                bot=context.bot,
                event=created_event,
                channel_id=TELEGRAM_PUBLIC_CHANNEL_ID,
            )

            # Store channel_message_id if posted
            if post_msg_id and submitter_id_int:
                try:
                    await api_client.update_event_status(
                        event_id=event_id,
                        status_value='approved',
                        admin_telegram_id=submitter_id_int,
                        channel_message_id=post_msg_id,
                    )
                except Exception as err:
                    logger.error("Failed to store channel_message_id for direct publish event %d: %s", event_id, err)

            # Send one-line info log to Admin Group (no approval buttons)
            if TELEGRAM_ADMIN_GROUP_ID:
                effective_name = update.effective_user.full_name or update.effective_user.username or "Admin"
                if is_owner(user_id):
                    effective_name = f"{effective_name} (Owner)"
                admin_log_msg = f"📢 Event *{safe_escape(created_event.get('title'))}* posted directly by {safe_escape(effective_name)}."
                try:
                    await context.bot.send_message(
                        chat_id=TELEGRAM_ADMIN_GROUP_ID,
                        text=admin_log_msg,
                        parse_mode=ParseMode.MARKDOWN,
                    )
                except Exception as err:
                    logger.error("Failed to post direct publish log to Admin Group: %s", err)

            success_text = (
                "⚡ *Event Published Directly!*\n\n"
                f"Your event *{safe_escape(created_event.get('title'))}* has been published immediately to the public channel."
            )
            await query.edit_message_text(success_text, parse_mode=ParseMode.MARKDOWN)

        else:
            # Normal approval queue flow for Club Representatives
            success_text = (
                "🎉 *Event Submitted Successfully!*\n\n"
                f"Your event *{safe_escape(created_event.get('title'))}* has been submitted to the admin approval queue.\n"
                "You will be notified once reviewed by the moderation team."
            )
            await query.edit_message_text(success_text, parse_mode=ParseMode.MARKDOWN)

            # Notify Admin Group exactly ONCE per event_id
            if TELEGRAM_ADMIN_GROUP_ID:
                global _notified_submission_event_ids
                if event_id not in _notified_submission_event_ids:
                    _notified_submission_event_ids.add(event_id)
                    try:
                        try:
                            full_event = await api_client.get_event_detail(event_id)
                        except Exception:
                            full_event = created_event

                        from .admin import send_admin_pending_notification
                        await send_admin_pending_notification(
                            bot=context.bot,
                            event=full_event,
                            admin_group_id=TELEGRAM_ADMIN_GROUP_ID,
                        )
                    except Exception as e:
                        logger.error(
                            "Failed to notify admin group %s: %s",
                            TELEGRAM_ADMIN_GROUP_ID,
                            e,
                            exc_info=True,
                        )
                else:
                    logger.info("Admin notification for event %d already sent, skipping duplicate.", event_id)

    except Exception as e:
        logger.error("Error submitting event: %s", e)
        await query.edit_message_text(
            "⚠️ *Failed to submit event to server.*\nPlease try again later.",
            parse_mode=ParseMode.MARKDOWN,
        )

    return ConversationHandler.END


async def handle_submission_timeout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handles submission conversation timeout (20 minutes of inactivity).
    Cleans up user_data and returns user to the main menu.
    """
    user_id = update.effective_user.id if update.effective_user else None
    context.user_data.clear()
    msg = (
        "⏱️ *Submission Session Timed Out*\n\n"
        "Your event submission session expired due to inactivity.\n"
        "You can tap *📝 Submit Post* or type `/submit` anytime to start again."
    )
    user_is_owner = is_owner(user_id)
    user_is_officer = False
    try:
        verified_clubs = await get_user_verified_clubs(user_id)
        user_is_officer = bool(verified_clubs) or user_is_owner
    except Exception:
        user_is_officer = user_is_owner

    keyboard = build_start_keyboard(is_owner=user_is_owner, is_officer=user_is_officer)
    if update.effective_message:
        try:
            await update.effective_message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
        except Exception:
            pass
    return ConversationHandler.END


async def cancel_submission(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the conversation cleanly and clears partial state."""
    user_id = update.effective_user.id if update.effective_user else None
    context.user_data.clear()
    msg = "❌ Event submission cancelled. Returning to main menu."
    user_is_owner = is_owner(user_id)
    user_is_officer = False
    try:
        verified_clubs = await get_user_verified_clubs(user_id)
        user_is_officer = bool(verified_clubs) or user_is_owner
    except Exception:
        user_is_officer = user_is_owner

    keyboard = build_start_keyboard(is_owner=user_is_owner, is_officer=user_is_officer)
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(msg, reply_markup=keyboard)
    elif update.message:
        await update.message.reply_text(msg, reply_markup=keyboard)
    return ConversationHandler.END


def get_submission_conversation_handler() -> ConversationHandler:
    """
    Builds the ConversationHandler for event submission.
    Requires explicit entry via /submit command or [📝 Submit Post] inline button.
    Forwards and direct media are only processed after entering the submission session.
    Includes /cancel fallback, timeout (20 min), and single-field preview editing.
    """
    return ConversationHandler(
        entry_points=[
            CommandHandler("submit", start_submission),
            CallbackQueryHandler(start_submission, pattern="^btn:submit$"),
        ],
        states={
            STATE_CONTENT: [
                MessageHandler(
                    filters.ALL & ~filters.COMMAND,
                    handle_content_received,
                )
            ],
            STATE_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_title_received)
            ],
            STATE_CLUB: [
                CallbackQueryHandler(handle_club_selected, pattern="^submit:club:")
            ],
            STATE_CUSTOM_CLUB: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_club_received)
            ],
            STATE_CATEGORY: [
                CallbackQueryHandler(handle_category_selected, pattern="^submit:cat:")
            ],
            STATE_CUSTOM_CATEGORY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_category_received)
            ],
            STATE_DATETIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_datetime_received)
            ],
            STATE_LOCATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_location_received)
            ],
            STATE_CONFIRM: [
                CallbackQueryHandler(handle_preview_actions, pattern="^submit:")
            ],
            ConversationHandler.TIMEOUT: [
                TypeHandler(Update, handle_submission_timeout),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_submission),
            CallbackQueryHandler(cancel_submission, pattern="^submit:cancel$"),
        ],
        conversation_timeout=1200,  # 20 minutes timeout
        allow_reentry=True,
        per_chat=True,
        per_user=True,
        per_message=False,
    )

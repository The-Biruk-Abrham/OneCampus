import logging
from typing import Optional, Dict, Any
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
from ..config import TELEGRAM_PUBLIC_CHANNEL_ID, TELEGRAM_ADMIN_GROUP_ID
from ..formatters import format_channel_post, format_single_event, safe_escape
from ..pagination import (
    build_admin_approval_keyboard,
    build_admin_edit_field_keyboard,
    build_submission_category_keyboard,
)

logger = logging.getLogger(__name__)

# Admin Edit States
STATE_EDIT_FIELD_SELECT, STATE_EDIT_FIELD_INPUT = range(2)


async def pending_events_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /pending command for admins to list all events waiting in the approval queue.
    """
    admin_id = update.effective_user.id

    try:
        pending_events = await api_client.get_events(status='pending', telegram_admin_id=admin_id)
        if not pending_events:
            await update.message.reply_text("✅ No events currently pending approval.")
            return

        await update.message.reply_text(
            f"📋 *Pending Approvals ({len(pending_events)} events):*",
            parse_mode=ParseMode.MARKDOWN,
        )

        for event in pending_events:
            text = format_single_event(event)
            keyboard = build_admin_approval_keyboard(event['id'])
            await update.message.reply_text(
                text=text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
    except Exception as e:
        logger.error("Error in /pending command: %s", e)
        await update.message.reply_text("⚠️ Error retrieving pending events. Ensure you have admin access.")


async def check_config_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Diagnostic command: /check_config
    Reports current chat ID, configured TELEGRAM_ADMIN_GROUP_ID, and tests sending a message to it.
    """
    current_chat_id = update.effective_chat.id
    current_chat_title = getattr(update.effective_chat, 'title', None) or "Private Chat"

    report = [
        "🛠️ *Configuration Diagnostics*",
        "─" * 28,
        f"📍 *Current Chat ID:* `{current_chat_id}` ({current_chat_title})",
        f"👥 *Configured Admin Group:* `{TELEGRAM_ADMIN_GROUP_ID}`",
        f"📢 *Configured Public Channel:* `{TELEGRAM_PUBLIC_CHANNEL_ID}`",
        "",
    ]

    if TELEGRAM_ADMIN_GROUP_ID:
        try:
            await context.bot.send_message(
                chat_id=TELEGRAM_ADMIN_GROUP_ID,
                text="🧪 *Ping from Events Hub Bot:* Connection test to admin group successful!",
                parse_mode=ParseMode.MARKDOWN,
            )
            report.append("✅ *Admin Group:* Successfully sent test ping to group!")
        except Exception as e:
            report.append(f"❌ *Admin Group Ping Failed:* `{e}`\n_(Check if bot is added as an Administrator to the group)_")
    else:
        report.append("⚠️ *Admin Group:* Not set in `.env`")

    if TELEGRAM_PUBLIC_CHANNEL_ID:
        try:
            test_ch_msg = await context.bot.send_message(
                chat_id=TELEGRAM_PUBLIC_CHANNEL_ID,
                text="🧪 *Ping from Events Hub Bot:* Connection test to public channel successful!",
                parse_mode=ParseMode.MARKDOWN,
            )
            report.append(f"✅ *Public Channel:* Successfully posted test message (ID: #{test_ch_msg.message_id})!")
        except Exception as e:
            report.append(f"❌ *Public Channel Post Failed:* `{e}`\n_(Make sure the bot has been added as an **Administrator** with 'Post Messages' permission in the channel)_")
    else:
        report.append("⚠️ *Public Channel:* Not set in `.env`")

    await update.message.reply_text("\n".join(report), parse_mode=ParseMode.MARKDOWN)


async def broadcast_event_to_channel(
    bot,
    event: Dict[str, Any],
    channel_id: str | int,
) -> Optional[int]:
    """
    Broadcasts the approved event to the public channel (with media if present)
    and returns the channel message_id.
    Displays ONLY the original forwarded media and caption, completely untouched.
    """
    raw_content = event.get('raw_content') or {}
    caption_text = format_channel_post(event)
    media_type = raw_content.get('media_type', 'text')
    file_ids = raw_content.get('file_ids', [])

    async def _try_send():
        if media_type == 'photo' and file_ids:
            msg = await bot.send_photo(
                chat_id=channel_id,
                photo=file_ids[0],
                caption=caption_text,
            )
            return msg.message_id
        elif media_type == 'video' and file_ids:
            msg = await bot.send_video(
                chat_id=channel_id,
                video=file_ids[0],
                caption=caption_text,
            )
            return msg.message_id
        elif media_type == 'document' and file_ids:
            msg = await bot.send_document(
                chat_id=channel_id,
                document=file_ids[0],
                caption=caption_text,
            )
            return msg.message_id
        elif media_type == 'animation' and file_ids:
            msg = await bot.send_animation(
                chat_id=channel_id,
                animation=file_ids[0],
                caption=caption_text,
            )
            return msg.message_id
        else:
            msg = await bot.send_message(
                chat_id=channel_id,
                text=caption_text,
            )
            return msg.message_id

    try:
        return await _try_send()
    except Exception as e:
        logger.error(
            "Error broadcasting to channel %s: %s. Please check if the bot is added as an Administrator to the channel.",
            channel_id,
            e,
            exc_info=True,
        )
        return None


async def send_admin_pending_notification(
    bot,
    event: Dict[str, Any],
    admin_group_id: str | int,
) -> Optional[int]:
    """
    Sends the pending event notification to the Admin Group.
    Includes the photo/video/media and displays structured review details as the caption
    with interactive Approve/Reject/Edit inline buttons.
    """
    from ..formatters import format_admin_pending_card
    raw_content = event.get('raw_content') or {}
    media_type = raw_content.get('media_type', 'text')
    file_ids = raw_content.get('file_ids', [])
    event_id = event.get('id')
    admin_kb = build_admin_approval_keyboard(event_id)

    formatted_caption = format_admin_pending_card(event)

    async def _try_send(use_markdown: bool = True):
        pm = ParseMode.MARKDOWN if use_markdown else None
        caption_text = formatted_caption if use_markdown else formatted_caption.replace('*', '').replace('_', '').replace('`', '')

        if media_type == 'photo' and file_ids:
            msg = await bot.send_photo(
                chat_id=admin_group_id,
                photo=file_ids[0],
                caption=caption_text,
                parse_mode=pm,
                reply_markup=admin_kb,
            )
            return msg.message_id
        elif media_type == 'video' and file_ids:
            msg = await bot.send_video(
                chat_id=admin_group_id,
                video=file_ids[0],
                caption=caption_text,
                parse_mode=pm,
                reply_markup=admin_kb,
            )
            return msg.message_id
        elif media_type == 'document' and file_ids:
            msg = await bot.send_document(
                chat_id=admin_group_id,
                document=file_ids[0],
                caption=caption_text,
                parse_mode=pm,
                reply_markup=admin_kb,
            )
            return msg.message_id
        elif media_type == 'animation' and file_ids:
            msg = await bot.send_animation(
                chat_id=admin_group_id,
                animation=file_ids[0],
                caption=caption_text,
                parse_mode=pm,
                reply_markup=admin_kb,
            )
            return msg.message_id
        else:
            msg = await bot.send_message(
                chat_id=admin_group_id,
                text=caption_text,
                parse_mode=pm,
                reply_markup=admin_kb,
            )
            return msg.message_id

    try:
        try:
            return await _try_send(use_markdown=True)
        except Exception as md_err:
            logger.warning("Markdown admin notification failed (%s). Retrying as plaintext: %s", admin_group_id, md_err)
            return await _try_send(use_markdown=False)
    except Exception as e:
        logger.error(
            "Error sending pending notification to admin group %s: %s",
            admin_group_id,
            e,
            exc_info=True,
        )
        return None


async def update_channel_message_in_place(
    bot,
    event: Dict[str, Any],
    channel_id: str | int,
    message_id: int,
) -> bool:
    """
    Edits an existing Telegram channel broadcast post in place after event updates.
    """
    formatted_caption = format_channel_post(event)
    raw_content = event.get('raw_content') or {}
    media_type = raw_content.get('media_type', 'text')

    try:
        if media_type in ('photo', 'video', 'document', 'animation'):
            await bot.edit_message_caption(
                chat_id=channel_id,
                message_id=message_id,
                caption=formatted_caption,
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            await bot.edit_message_text(
                chat_id=channel_id,
                message_id=message_id,
                text=formatted_caption,
                parse_mode=ParseMode.MARKDOWN,
            )
        return True
    except Exception as e:
        logger.error("Error editing channel message %d in place: %s", message_id, e)
        return False


async def safe_edit_query_message(
    query,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: Any = ParseMode.MARKDOWN,
) -> None:
    """
    Safely edits a callback query's message whether it is a media message (photo/video with caption)
    or a standard text message, with entity parsing error fallback.
    """
    msg = getattr(query, 'message', None)
    is_media = bool(msg and (getattr(msg, 'photo', None) or getattr(msg, 'video', None) or getattr(msg, 'animation', None) or getattr(msg, 'document', None) or getattr(msg, 'caption', None)))

    async def _do_edit(pm):
        if is_media:
            try:
                await query.edit_message_caption(caption=text, parse_mode=pm, reply_markup=reply_markup)
            except Exception as e:
                err = str(e).lower()
                if "no text in the message" in err or "there is no caption" in err or "message is not modified" in err:
                    if "message is not modified" in err:
                        return
                    await query.edit_message_text(text=text, parse_mode=pm, reply_markup=reply_markup)
                else:
                    raise
        else:
            try:
                await query.edit_message_text(text=text, parse_mode=pm, reply_markup=reply_markup)
            except Exception as e:
                err = str(e).lower()
                if "no text in the message" in err:
                    await query.edit_message_caption(caption=text, parse_mode=pm, reply_markup=reply_markup)
                elif "message is not modified" in err:
                    return
                else:
                    raise

    try:
        await _do_edit(parse_mode)
    except Exception as e:
        err = str(e).lower()
        if "message is not modified" in err:
            return
        if "can't parse entities" in err or "parsing" in err or "entity" in err:
            plain = text.replace('*', '').replace('_', '').replace('`', '').replace('\\', '')
            await _do_edit(None)
        else:
            raise


async def handle_admin_approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles [✅ Approve] button click by an admin.
    """
    query = update.callback_query
    await query.answer()
    admin_user = update.effective_user
    admin_id = admin_user.id
    admin_name = admin_user.first_name or admin_user.username or str(admin_id)

    event_id = int(query.data.split(":")[2])

    try:
        event = await api_client.get_event_detail(event_id)

        # 1. Broadcast to Public Channel if configured
        channel_msg_id = None
        if TELEGRAM_PUBLIC_CHANNEL_ID:
            channel_msg_id = await broadcast_event_to_channel(
                bot=context.bot,
                event=event,
                channel_id=TELEGRAM_PUBLIC_CHANNEL_ID,
            )

        # 2. Update status in backend API
        updated_event = await api_client.update_event_status(
            event_id=event_id,
            status_value="approved",
            admin_telegram_id=admin_id,
            channel_message_id=channel_msg_id,
        )

        # 3. Update Admin Group card in place (handles both photo/video captions and text)
        channel_info = f" (Channel Post #{channel_msg_id})" if channel_msg_id else ""
        adm_esc = safe_escape(admin_name)
        title_esc = safe_escape(event.get('title'))
        club_esc = safe_escape(event.get('club_name'))
        loc_esc = safe_escape(event.get('location'))

        approval_summary = (
            f"✅ *APPROVED by {adm_esc}*{channel_info}\n\n"
            f"📌 *Event:* {title_esc}\n"
            f"🏛️ *Club:* {club_esc}\n"
            f"📅 *Time:* {event.get('start_datetime')}\n"
            f"📍 *Venue:* {loc_esc}"
        )
        try:
            await safe_edit_query_message(query, approval_summary)
        except Exception as edit_err:
            logger.warning("Error editing admin card in place: %s", edit_err)

        # 4. Notify submitter
        raw_content = event.get('raw_content') or {}
        submitter_id = raw_content.get('submitter_telegram_id')
        if submitter_id:
            try:
                await context.bot.send_message(
                    chat_id=submitter_id,
                    text=(
                        f"🎉 *Great News! Your Event is Approved!* 📢\n\n"
                        f"Your event *{event.get('title')}* has been approved and published to the university channel."
                    ),
                    parse_mode=ParseMode.MARKDOWN,
                )
            except Exception as e:
                logger.info("Could not send DM to submitter %s: %s", submitter_id, e)

    except Exception as e:
        logger.error("Error approving event %d: %s", event_id, e)
        err_str = str(e)
        if "403" in err_str:
            err_text = (
                f"⛔ *Permission Denied:* Your Telegram ID (`{admin_id}`) is not registered as an authorized Admin in the database.\n"
                f"Use `python manage.py add_admin {admin_id}` to authorize this user."
            )
        else:
            err_text = f"⚠️ *Error approving event:*\n`{safe_escape(err_str)}`"

        if query and query.message:
            try:
                await query.message.reply_text(err_text, parse_mode=ParseMode.MARKDOWN)
            except Exception:
                await query.message.reply_text(err_text.replace('*', '').replace('`', ''))


async def handle_admin_reject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles [❌ Reject] button click by an admin.
    """
    query = update.callback_query
    await query.answer()
    admin_user = update.effective_user
    admin_id = admin_user.id
    admin_name = admin_user.first_name or admin_user.username or str(admin_id)

    event_id = int(query.data.split(":")[2])

    try:
        event = await api_client.get_event_detail(event_id)

        # 1. Update status in backend API
        await api_client.update_event_status(
            event_id=event_id,
            status_value="rejected",
            admin_telegram_id=admin_id,
        )

        # 2. Update Admin Group card in place (handles both photo/video captions and text)
        adm_esc = safe_escape(admin_name)
        title_esc = safe_escape(event.get('title'))
        club_esc = safe_escape(event.get('club_name'))
        rejection_summary = (
            f"❌ *REJECTED by {adm_esc}*\n\n"
            f"📌 *Event:* {title_esc}\n"
            f"🏛️ *Club:* {club_esc}"
        )
        try:
            await safe_edit_query_message(query, rejection_summary)
        except Exception as edit_err:
            logger.warning("Error editing admin rejection card in place: %s", edit_err)

        # 3. Notify submitter
        raw_content = event.get('raw_content') or {}
        submitter_id = raw_content.get('submitter_telegram_id')
        if submitter_id:
            try:
                await context.bot.send_message(
                    chat_id=submitter_id,
                    text=(
                        f"⚠️ *Event Submission Update*\n\n"
                        f"Your submission for *{event.get('title')}* was not approved by the moderation team."
                    ),
                    parse_mode=ParseMode.MARKDOWN,
                )
            except Exception as e:
                logger.info("Could not notify submitter %s: %s", submitter_id, e)

    except Exception as e:
        logger.error("Error rejecting event %d: %s", event_id, e)
        err_str = str(e)
        if "403" in err_str:
            err_text = (
                f"⛔ *Permission Denied:* Your Telegram ID (`{admin_id}`) is not registered as an authorized Admin in the database.\n"
                f"Use `python manage.py add_admin {admin_id}` to authorize this user."
            )
        else:
            err_text = f"⚠️ *Error rejecting event:*\n`{safe_escape(err_str)}`"

        if query and query.message:
            try:
                await query.message.reply_text(err_text, parse_mode=ParseMode.MARKDOWN)
            except Exception:
                await query.message.reply_text(err_text.replace('*', '').replace('`', ''))


async def handle_admin_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Opens field selection menu for admin editing.
    """
    query = update.callback_query
    await query.answer()
    event_id = int(query.data.split(":")[2])

    keyboard = build_admin_edit_field_keyboard(event_id)
    await query.edit_message_reply_markup(reply_markup=keyboard)


async def handle_admin_edit_field_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Prompt admin to input the new value for the chosen field.
    """
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":")
    field_type = parts[2]
    event_id = int(parts[3])

    if field_type == "done":
        await safe_edit_query_message(query, "✅ Editing completed.")
        context.user_data.clear()
        return ConversationHandler.END

    if 'admin_edit' not in context.user_data or not isinstance(context.user_data['admin_edit'], dict):
        context.user_data['admin_edit'] = {}

    context.user_data['admin_edit']['event_id'] = event_id
    context.user_data['admin_edit']['field'] = field_type

    prompts = {
        "title": "Enter new *Event Title*:",
        "date": "Enter new *Date & Time* (`DD/MM/YYYY HH:MM`):",
        "loc": "Enter new *Location / Venue*:",
        "cat": "Enter new *Category* (Category ID or type custom category name, max 50 chars):",
        "club": "Enter new *Host Club* (Club ID or type custom club name, max 50 chars):",
    }

    prompt = prompts.get(field_type, "Enter new value:")
    await query.message.reply_text(prompt, parse_mode=ParseMode.MARKDOWN)
    return STATE_EDIT_FIELD_INPUT


async def handle_admin_edit_field_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Saves edited field to backend and auto-edits channel post if already published.
    """
    new_val = update.message.text.strip() if update.message and update.message.text else ""
    edit_data = context.user_data.get('admin_edit', {})
    event_id = edit_data.get('event_id') or context.user_data.get('edit_event_id')
    field_type = edit_data.get('field') or context.user_data.get('edit_field')
    admin_id = update.effective_user.id

    if not event_id or not field_type:
        await update.message.reply_text("Session expired. Please select the event again.")
        context.user_data.clear()
        return ConversationHandler.END

    fields_payload = {}
    if field_type == "title":
        fields_payload["title"] = new_val
    elif field_type == "loc":
        fields_payload["location"] = new_val
    elif field_type == "date":
        from .submit import parse_event_datetime
        try:
            dt = parse_event_datetime(new_val)
            fields_payload["start_datetime"] = dt.isoformat()
        except ValueError:
            await update.message.reply_text(
                "❌ *Invalid format.* Please enter date and time as `DD/MM/YYYY HH:MM` (e.g. 15/09/2026 14:30):",
                parse_mode=ParseMode.MARKDOWN,
            )
            return STATE_EDIT_FIELD_INPUT
    elif field_type == "cat":
        if new_val.isdigit():
            fields_payload["category"] = int(new_val)
            fields_payload["custom_category"] = ""
        else:
            if len(new_val) > 50:
                await update.message.reply_text("❌ Please keep custom category names to 50 characters or fewer:")
                return STATE_EDIT_FIELD_INPUT
            fields_payload["category"] = None
            fields_payload["custom_category"] = new_val
    elif field_type == "club":
        if new_val.isdigit():
            fields_payload["club"] = int(new_val)
            fields_payload["custom_club"] = ""
        else:
            if len(new_val) > 50:
                await update.message.reply_text("❌ Please keep custom club names to 50 characters or fewer:")
                return STATE_EDIT_FIELD_INPUT
            fields_payload["club"] = None
            fields_payload["custom_club"] = new_val

    try:
        updated_event = await api_client.update_event_structured_fields(
            event_id=event_id,
            fields=fields_payload,
            admin_telegram_id=admin_id,
        )

        # In-place auto-edit channel message if already published!
        channel_msg_id = updated_event.get('channel_message_id')
        if channel_msg_id and TELEGRAM_PUBLIC_CHANNEL_ID:
            await update_channel_message_in_place(
                bot=context.bot,
                event=updated_event,
                channel_id=TELEGRAM_PUBLIC_CHANNEL_ID,
                message_id=channel_msg_id,
            )

        keyboard = build_admin_edit_field_keyboard(event_id)
        await update.message.reply_text(
            f"✅ *Field updated successfully!*"
            f"{' (Channel post updated in-place)' if channel_msg_id else ''}\n\n"
            "Choose another field to edit or tap Done:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )
        return STATE_EDIT_FIELD_SELECT
    except Exception as e:
        logger.error("Error updating event fields: %s", e)
        await update.message.reply_text(f"⚠️ Error updating field: {e}")
        context.user_data.clear()
        return ConversationHandler.END


async def cancel_admin_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels admin edit conversation."""
    context.user_data.clear()
    msg = "❌ Editing cancelled."
    if update.callback_query:
        await update.callback_query.answer()
        await safe_edit_query_message(update.callback_query, msg)
    elif update.message:
        await update.message.reply_text(msg)
    return ConversationHandler.END


def get_admin_edit_conversation_handler() -> ConversationHandler:
    """
    Builds the ConversationHandler for admin editing.
    """
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handle_admin_edit_field_choice, pattern="^admin:editfield:")
        ],
        states={
            STATE_EDIT_FIELD_SELECT: [
                CallbackQueryHandler(handle_admin_edit_field_choice, pattern="^admin:editfield:")
            ],
            STATE_EDIT_FIELD_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_edit_field_input)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_admin_edit),
            CallbackQueryHandler(cancel_admin_edit, pattern="^admin:cancel$"),
        ],
        conversation_timeout=1200,
        allow_reentry=True,
        per_chat=True,
        per_user=True,
        per_message=False,
    )

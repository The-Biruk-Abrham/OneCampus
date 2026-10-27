import logging
import sys
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from .config import TELEGRAM_BOT_TOKEN, API_BASE_URL, is_owner
from .pagination import build_start_keyboard
from .handlers.start import start_command
from .handlers.today import today_command
from .handlers.week import week_command
from .handlers.events import events_command
from .handlers.callbacks import callback_router
from .handlers.submit import get_submission_conversation_handler, get_user_verified_clubs
from .handlers.admin import pending_events_command, check_config_command, get_admin_edit_conversation_handler
from .handlers.officers import (
    add_officer_command,
    remove_officer_command,
    list_officers_command,
    add_club_command,
    get_officer_management_conversation_handler,
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
import telegram.error
from telegram.request import HTTPXRequest


import warnings
from telegram.warnings import PTBUserWarning
warnings.filterwarnings("ignore", message=r".*per_message=False.*", category=PTBUserWarning)


async def idle_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles forwarded messages or unsolicited media sent when no conversation session is active.
    Informs the user to tap 'Submit Post' or use the main menu.
    """
    if not update.effective_message:
        return

    user = update.effective_user
    user_id = user.id if user else None
    user_is_owner = is_owner(user_id)
    user_is_officer = False
    try:
        verified_clubs = await get_user_verified_clubs(user_id)
        user_is_officer = bool(verified_clubs) or user_is_owner
    except Exception:
        user_is_officer = user_is_owner

    if user_is_officer:
        msg = (
            "ℹ️ *You forwarded a message!*\n\n"
            "To submit an event, type `/submit` or click *📝 Submit Post* below."
        )
    else:
        msg = (
            "ℹ️ *Welcome to Addis Ababa Science and Technology University (AASTU) Events Hub!*\n\n"
            "Use `/events` or the menu below to browse upcoming campus events and activities."
        )

    keyboard = build_start_keyboard(is_owner=user_is_owner, is_officer=user_is_officer)
    await update.effective_message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a friendly message if possible."""
    if isinstance(context.error, (telegram.error.NetworkError, telegram.error.TimedOut)):
        logger.warning("Temporary Telegram network fluctuation: %s. Reconnecting...", context.error)
        return

    logger.error("Exception while handling an update:", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ *Something went wrong — try /cancel and start again.*",
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            try:
                await update.effective_message.reply_text(
                    "⚠️ Something went wrong — try /cancel and start again."
                )
            except Exception:
                pass


def build_bot_application(token: str = None) -> Application:
    """
    Constructs and configures the python-telegram-bot Application instance
    with resilient HTTP timeouts and connection pooling to handle network fluctuations.
    """
    bot_token = TELEGRAM_BOT_TOKEN if token is None else token
    if not bot_token:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN is not configured! Please add TELEGRAM_BOT_TOKEN to your .env file."
        )

    # Configure resilient HTTP connection timeouts & connection pooling
    request_config = HTTPXRequest(
        connect_timeout=30.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=30.0,
        connection_pool_size=16,
        http_version="1.1",
    )

    application = (
        ApplicationBuilder()
        .token(bot_token)
        .request(request_config)
        .build()
    )

    # Submission, Admin Edit, and Officer Management Conversation Handlers (High Priority)
    application.add_handler(get_officer_management_conversation_handler())
    application.add_handler(get_admin_edit_conversation_handler())
    application.add_handler(get_submission_conversation_handler())

    # Public Viewing Command Handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", start_command))
    application.add_handler(CommandHandler("today", today_command))
    application.add_handler(CommandHandler("week", week_command))
    application.add_handler(CommandHandler("events", events_command))
    application.add_handler(CommandHandler("cancel", start_command))

    # Admin / Owner Management Command Handlers
    application.add_handler(CommandHandler("pending", pending_events_command))
    application.add_handler(CommandHandler("check_config", check_config_command))
    application.add_handler(CommandHandler("add_club", add_club_command))
    application.add_handler(CommandHandler("add_officer", add_officer_command))
    application.add_handler(CommandHandler("remove_officer", remove_officer_command))
    application.add_handler(CommandHandler("add_club_admin", add_officer_command))
    application.add_handler(CommandHandler("remove_club_admin", remove_officer_command))
    application.add_handler(CommandHandler("officers", list_officers_command))

    # Callback Query Handler (Pagination, Navigation, and Admin Actions)
    application.add_handler(CallbackQueryHandler(callback_router))

    # Fallback message handler for idle forwards or unsolicited media in private chats
    application.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & (
                filters.FORWARDED
                | filters.PHOTO
                | filters.VIDEO
                | filters.ANIMATION
                | filters.Document.ALL
                | filters.AUDIO
                | filters.VOICE
            ),
            idle_message_handler,
        )
    )

    # Global Error Handler
    application.add_error_handler(error_handler)

    return application


def main():
    """Main runner entrypoint."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error(
            "CRITICAL: TELEGRAM_BOT_TOKEN is not set in .env! "
            "Please set TELEGRAM_BOT_TOKEN in .env to run the bot with live Telegram polling."
        )
        sys.exit(1)

    print("\n" + "=" * 60)
    print("🚀 University Events Hub Telegram Bot is STARTING...")
    print(f"🌐 Backend REST API: {API_BASE_URL}")
    print("🤖 Bot Handle: @AASTUeventsbot")
    print("💬 Status: LISTENING for Telegram messages & forwards")
    print("⏹️ Press Ctrl + C anytime to stop")
    print("=" * 60 + "\n")

    application = build_bot_application()
    logger.info("Bot application initialized. Starting polling with auto-reconnect...")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        bootstrap_retries=-1,  # Automatically retry on network timeouts during startup
        timeout=30,            # Polling timeout in seconds
    )


if __name__ == '__main__':
    main()

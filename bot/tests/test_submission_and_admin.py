import unittest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime
from telegram import Update, Message, User, PhotoSize, Video, CallbackQuery

from bot.handlers.submit import (
    extract_raw_content,
    parse_event_datetime,
    start_submission,
    handle_content_received,
    handle_title_received,
    handle_submission_timeout,
    get_user_verified_clubs,
    STATE_CONTENT,
    STATE_TITLE,
    STATE_CLUB,
    STATE_CATEGORY,
    STATE_CONFIRM,
)
from bot.handlers.start import start_command
from bot.main import idle_message_handler
from bot.handlers.admin import (
    broadcast_event_to_channel,
    update_channel_message_in_place,
)
from bot.handlers.officers import (
    extract_telegram_id_from_message,
    start_owner_add_admin,
    start_owner_remove_admin,
)
from bot.api_client import EventsApiClient
from telegram.ext import ConversationHandler


def _make_mock_message(**kwargs):
    msg = MagicMock(spec=Message)
    msg.photo = kwargs.get('photo', None)
    msg.video = kwargs.get('video', None)
    msg.animation = kwargs.get('animation', None)
    msg.document = kwargs.get('document', None)
    msg.audio = kwargs.get('audio', None)
    msg.voice = kwargs.get('voice', None)
    msg.poll = kwargs.get('poll', None)
    msg.text = kwargs.get('text', None)
    msg.caption = kwargs.get('caption', None)
    msg.forward_origin = kwargs.get('forward_origin', None)
    msg.forward_from = kwargs.get('forward_from', None)
    msg.forward_from_chat = kwargs.get('forward_from_chat', None)
    msg.reply_text = AsyncMock()
    return msg


class TestSubmissionHelpers(unittest.IsolatedAsyncioTestCase):
    def test_parse_event_datetime_valid(self):
        dt = parse_event_datetime("15/09/2026 14:30")
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.month, 9)
        self.assertEqual(dt.day, 15)
        self.assertEqual(dt.hour, 14)
        self.assertEqual(dt.minute, 30)

    def test_parse_event_datetime_invalid(self):
        with self.assertRaises(ValueError):
            parse_event_datetime("2026-09-15 14:30")
        with self.assertRaises(ValueError):
            parse_event_datetime("invalid-date")

    def test_extract_raw_content_photo(self):
        update = MagicMock(spec=Update)
        photo1 = MagicMock(spec=PhotoSize, file_id="small_id")
        photo2 = MagicMock(spec=PhotoSize, file_id="large_id")
        msg = _make_mock_message(photo=[photo1, photo2], caption="🚀 Epic Hackathon Announcement!")

        user = MagicMock(spec=User)
        user.id = 123456789
        user.username = "test_organizer"

        update.message = msg
        update.effective_user = user

        raw = extract_raw_content(update)
        self.assertEqual(raw["media_type"], "photo")
        self.assertEqual(raw["file_ids"], ["large_id"])
        self.assertEqual(raw["caption"], "🚀 Epic Hackathon Announcement!")
        self.assertEqual(raw["submitter_telegram_id"], 123456789)
        self.assertEqual(raw["submitter_username"], "test_organizer")
        self.assertFalse(raw["is_forwarded"])

    def test_extract_raw_content_text(self):
        update = MagicMock(spec=Update)
        msg = _make_mock_message(text="Join our general assembly this Friday at 5 PM.")
        user = MagicMock(spec=User)
        user.id = 987654321
        user.username = "club_prez"

        update.message = msg
        update.effective_user = user

        raw = extract_raw_content(update)
        self.assertEqual(raw["media_type"], "text")
        self.assertEqual(raw["file_ids"], [])
        self.assertEqual(raw["caption"], "Join our general assembly this Friday at 5 PM.")
        self.assertFalse(raw["is_forwarded"])

    def test_extract_raw_content_forwarded_from_channel(self):
        update = MagicMock(spec=Update)
        msg = _make_mock_message(
            document=MagicMock(file_id="doc_file_123"),
            caption="📄 Hackathon Rulebook PDF",
            forward_from_chat=MagicMock(title="ASTU Official Channel", username="astu_channel"),
        )
        user = MagicMock(spec=User)
        user.id = 555444
        user.username = "channel_forwarder"

        update.message = msg
        update.effective_user = user

        raw = extract_raw_content(update)
        self.assertEqual(raw["media_type"], "document")
        self.assertEqual(raw["file_ids"], ["doc_file_123"])
        self.assertTrue(raw["is_forwarded"])
        self.assertEqual(raw["forward_info"]["chat_title"], "ASTU Official Channel")


class TestSubmissionGatingAndRouting(unittest.IsolatedAsyncioTestCase):
    @patch("bot.handlers.submit.api_client.get_clubs", new_callable=AsyncMock)
    async def test_unauthorized_user_blocked_from_start_submission(self, mock_get_clubs):
        mock_get_clubs.return_value = [
            {"id": 1, "name": "Robotics Club", "verified_officers": [999999]}
        ]

        update = MagicMock(spec=Update)
        user = MagicMock(spec=User)
        user.id = 111222  # not an officer
        update.effective_user = user
        update.callback_query = None
        update.message = _make_mock_message()

        context = MagicMock()
        context.user_data = {}

        next_state = await start_submission(update, context)
        self.assertEqual(next_state, ConversationHandler.END)
        update.message.reply_text.assert_called_once()
        args, kwargs = update.message.reply_text.call_args
        self.assertIn("Access Restricted", args[0])

    @patch("bot.handlers.submit.api_client.get_clubs", new_callable=AsyncMock)
    async def test_authorized_user_enters_start_submission(self, mock_get_clubs):
        mock_get_clubs.return_value = [
            {"id": 1, "name": "Robotics Club", "verified_officers": [111222]}
        ]

        update = MagicMock(spec=Update)
        user = MagicMock(spec=User)
        user.id = 111222  # verified officer!
        update.effective_user = user
        update.callback_query = None
        update.message = _make_mock_message()

        context = MagicMock()
        context.user_data = {}

        next_state = await start_submission(update, context)
        self.assertEqual(next_state, STATE_CONTENT)
        self.assertIn("submission", context.user_data)
        self.assertEqual(len(context.user_data["submission"]["verified_clubs"]), 1)

    @patch("bot.handlers.submit.api_client.get_clubs", new_callable=AsyncMock)
    @patch("bot.handlers.submit.api_client.get_categories", new_callable=AsyncMock)
    async def test_single_club_officer_autofills_club(self, mock_get_cats, mock_get_clubs):
        mock_get_clubs.return_value = [
            {"id": 10, "name": "ASTU Coding Club", "verified_officers": [111222]}
        ]
        mock_get_cats.return_value = [
            {"id": 1, "name": "Academic"}
        ]

        update = MagicMock(spec=Update)
        user = MagicMock(spec=User)
        user.id = 111222
        update.effective_user = user
        update.message = _make_mock_message(text="Hackathon 2026")

        context = MagicMock()
        context.user_data = {
            "submission": {
                "verified_clubs": [{"id": 10, "name": "ASTU Coding Club", "verified_officers": [111222]}]
            }
        }

        next_state = await handle_title_received(update, context)
        # Should skip STATE_CLUB and advance directly to STATE_CATEGORY
        self.assertEqual(next_state, STATE_CATEGORY)
        sub = context.user_data["submission"]
        self.assertEqual(sub["club"], 10)
        self.assertEqual(sub["club_name"], "ASTU Coding Club")
        self.assertFalse(sub["is_custom_club"])

    @patch("bot.handlers.submit.api_client.get_clubs", new_callable=AsyncMock)
    async def test_multiple_clubs_officer_shows_picker(self, mock_get_clubs):
        verified_clubs = [
            {"id": 10, "name": "ASTU Coding Club", "verified_officers": [111222]},
            {"id": 20, "name": "ASTU AI Society", "verified_officers": [111222]},
        ]
        mock_get_clubs.return_value = verified_clubs

        update = MagicMock(spec=Update)
        user = MagicMock(spec=User)
        user.id = 111222
        update.effective_user = user
        update.message = _make_mock_message(text="AI Hackathon")

        context = MagicMock()
        context.user_data = {
            "submission": {
                "verified_clubs": verified_clubs
            }
        }

        next_state = await handle_title_received(update, context)
        # Should move to STATE_CLUB for the user to choose
        self.assertEqual(next_state, STATE_CLUB)
        update.message.reply_text.assert_called_once()
        _, kwargs = update.message.reply_text.call_args
        self.assertIn("Select which of your verified clubs", kwargs["text"] if "text" in kwargs else update.message.reply_text.call_args[0][0])

    @patch("bot.handlers.submit.api_client.get_clubs", new_callable=AsyncMock)
    async def test_start_command_non_rep_does_not_see_submit_button(self, mock_get_clubs):
        mock_get_clubs.return_value = [
            {"id": 1, "name": "Robotics Club", "verified_officers": [999999]}
        ]
        update = MagicMock(spec=Update)
        user = MagicMock(spec=User)
        user.id = 111222  # Not an officer
        user.first_name = "Student"
        update.effective_user = user
        update.callback_query = None
        update.message = _make_mock_message()

        context = MagicMock()
        await start_command(update, context)

        update.message.reply_text.assert_called_once()
        _, kwargs = update.message.reply_text.call_args
        kb = kwargs.get("reply_markup")
        all_callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        self.assertNotIn("btn:submit", all_callbacks)

    @patch("bot.handlers.submit.api_client.get_clubs", new_callable=AsyncMock)
    async def test_start_command_representative_sees_submit_button(self, mock_get_clubs):
        mock_get_clubs.return_value = [
            {"id": 1, "name": "Robotics Club", "verified_officers": [111222]}
        ]
        update = MagicMock(spec=Update)
        user = MagicMock(spec=User)
        user.id = 111222  # Verified officer
        user.first_name = "President"
        update.effective_user = user
        update.callback_query = None
        update.message = _make_mock_message()

        context = MagicMock()
        await start_command(update, context)

        update.message.reply_text.assert_called_once()
        _, kwargs = update.message.reply_text.call_args
        kb = kwargs.get("reply_markup")
        all_callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        self.assertIn("btn:submit", all_callbacks)

    @patch("bot.handlers.submit.api_client.get_clubs", new_callable=AsyncMock)
    async def test_idle_forward_rep_gets_prompt_and_no_submission_starts(self, mock_get_clubs):
        mock_get_clubs.return_value = [
            {"id": 1, "name": "Robotics Club", "verified_officers": [111222]}
        ]
        update = MagicMock(spec=Update)
        user = MagicMock(spec=User)
        user.id = 111222
        update.effective_user = user
        update.message = _make_mock_message(text="Forwarded message while idle", forward_date=12345)
        update.effective_message = update.message

        context = MagicMock()
        context.user_data = {}

        await idle_message_handler(update, context)

        self.assertNotIn("submission", context.user_data)
        update.effective_message.reply_text.assert_called_once()
        reply_text = update.effective_message.reply_text.call_args[0][0]
        self.assertIn("You forwarded a message!", reply_text)
        self.assertIn("Submit Post", reply_text)

    @patch("bot.handlers.submit.api_client.get_clubs", new_callable=AsyncMock)
    async def test_submission_timeout_handler_cleans_up_and_notifies(self, mock_get_clubs):
        mock_get_clubs.return_value = []
        update = MagicMock(spec=Update)
        user = MagicMock(spec=User)
        user.id = 111222
        update.effective_user = user
        update.message = _make_mock_message()
        update.effective_message = update.message

        context = MagicMock()
        context.user_data = {"submission": {"title": "Half filled"}}

        res = await handle_submission_timeout(update, context)
        self.assertEqual(res, ConversationHandler.END)
        self.assertEqual(context.user_data, {})
        update.effective_message.reply_text.assert_called_once()
        reply_text = update.effective_message.reply_text.call_args[0][0]
        self.assertIn("Submission Session Timed Out", reply_text)


class TestOwnerClubAdminFlow(unittest.IsolatedAsyncioTestCase):
    def test_extract_telegram_id_from_forward(self):
        msg = MagicMock(spec=Message)
        origin = MagicMock()
        origin.type = "user"
        origin.sender_user = MagicMock(id=555666777, full_name="Abebe Bikila", username="abebek")
        msg.forward_origin = origin
        msg.forward_from = None
        msg.text = None

        uid, name, err = extract_telegram_id_from_message(msg)
        self.assertEqual(uid, 555666777)
        self.assertEqual(name, "Abebe Bikila")
        self.assertIsNone(err)

    def test_extract_telegram_id_from_numeric_text(self):
        msg = MagicMock(spec=Message)
        msg.forward_origin = None
        msg.forward_from = None
        msg.text = "987654321"

        uid, name, err = extract_telegram_id_from_message(msg)
        self.assertEqual(uid, 987654321)
        self.assertIsNone(err)

    def test_extract_telegram_id_invalid_input(self):
        msg = MagicMock(spec=Message)
        msg.forward_origin = None
        msg.forward_from = None
        msg.text = "not-a-number"

        uid, name, err = extract_telegram_id_from_message(msg)
        self.assertIsNone(uid)
        self.assertIsNotNone(err)

    def test_extract_telegram_id_from_channel_forward(self):
        msg = MagicMock(spec=Message)
        origin = MagicMock()
        origin.type = "channel"
        msg.forward_origin = origin
        msg.forward_from = None
        msg.text = None

        uid, name, err = extract_telegram_id_from_message(msg)
        self.assertIsNone(uid)
        self.assertIn("This forward doesn't include the sender's account info", err)

    def test_extract_telegram_id_from_hidden_user_forward(self):
        msg = MagicMock(spec=Message)
        origin = MagicMock()
        origin.type = "hidden_user"
        msg.forward_origin = origin
        msg.forward_from = None
        msg.text = None

        uid, name, err = extract_telegram_id_from_message(msg)
        self.assertIsNone(uid)
        self.assertIn("This forward doesn't include the sender's account info", err)

    @patch("bot.handlers.officers.is_owner", return_value=False)
    async def test_non_owner_blocked_from_owner_add_admin(self, mock_is_owner):
        update = MagicMock(spec=Update)
        user = MagicMock(spec=User)
        user.id = 12345
        update.effective_user = user
        update.callback_query = None
        update.message = _make_mock_message()

        context = MagicMock()
        res = await start_owner_add_admin(update, context)
        self.assertEqual(res, ConversationHandler.END)
        update.message.reply_text.assert_called_once()
        args, _ = update.message.reply_text.call_args
        self.assertIn("Access Denied", args[0])

    @patch("bot.handlers.officers.api_client.add_club_officer", new_callable=AsyncMock)
    async def test_handle_content_received_routes_to_add_officer_when_in_step_2(self, mock_add_officer):
        mock_add_officer.return_value = {
            "id": 1,
            "name": "Robotics Club",
            "verified_officers": [555666777],
        }
        update = MagicMock(spec=Update)
        owner_user = MagicMock(spec=User)
        owner_user.id = 999000
        update.effective_user = owner_user

        msg = _make_mock_message()
        origin = MagicMock()
        origin.type = "user"
        origin.sender_user = MagicMock(id=555666777, full_name="Abebe Bikila", username="abebek")
        msg.forward_origin = origin
        msg.text = None
        update.message = msg
        update.callback_query = None

        context = MagicMock()
        context.user_data = {
            "officer_manage": {
                "action": "add",
                "club_id": 1,
                "club_name": "Robotics Club",
            }
        }

        # User is in Step 2: Add Representative. Calling handle_content_received with a forward
        # must route to Add Representative, extract representative ID, and NOT start submission flow.
        next_state = await handle_content_received(update, context)
        self.assertEqual(next_state, ConversationHandler.END)
        mock_add_officer.assert_called_once_with(
            club_id=1,
            officer_telegram_id=555666777,
            admin_telegram_id=999000,
        )
        update.message.reply_text.assert_called_once()
        reply_text = update.message.reply_text.call_args[0][0]
        self.assertIn("Verified Club Representative Added!", reply_text)
        self.assertNotIn("Step 1 of 5: Event Title", reply_text)

    async def test_handle_content_received_channel_forward_during_add_officer_shows_error(self):
        update = MagicMock(spec=Update)
        owner_user = MagicMock(spec=User)
        owner_user.id = 999000
        update.effective_user = owner_user

        msg = _make_mock_message()
        origin = MagicMock()
        origin.type = "channel"
        msg.forward_origin = origin
        msg.text = None
        update.message = msg
        update.callback_query = None

        context = MagicMock()
        context.user_data = {
            "officer_manage": {
                "action": "add",
                "club_id": 1,
                "club_name": "Robotics Club",
            }
        }

        next_state = await handle_content_received(update, context)
        self.assertEqual(next_state, ConversationHandler.END)
        update.message.reply_text.assert_called_once()
        reply_text = update.message.reply_text.call_args[0][0]
        self.assertIn("This forward doesn't include the sender's account info", reply_text)
        self.assertNotIn("Step 1 of 5: Event Title", reply_text)
        # Context should still hold officer_manage so user can try again
        self.assertIn("officer_manage", context.user_data)


class TestAdminChannelBroadcast(unittest.IsolatedAsyncioTestCase):
    async def test_broadcast_photo_forwarded_event_to_channel(self):
        mock_bot = MagicMock()
        mock_sent_msg = MagicMock()
        mock_sent_msg.message_id = 4055
        mock_bot.send_photo = AsyncMock(return_value=mock_sent_msg)

        event = {
            "title": "Robotics Showcase",
            "club_name": "ASTU Robotics",
            "category_name": "Engineering",
            "start_datetime": "2026-09-05T14:00:00Z",
            "location": "Main Stadium",
            "raw_content": {
                "media_type": "photo",
                "file_ids": ["photo_file_123"],
                "is_forwarded": True,
                "caption": "Check out our autonomous drone!",
            }
        }

        msg_id = await broadcast_event_to_channel(mock_bot, event, channel_id="@astu_events")
        self.assertEqual(msg_id, 4055)
        mock_bot.send_photo.assert_called_once()
        _, kwargs = mock_bot.send_photo.call_args
        self.assertEqual(kwargs["chat_id"], "@astu_events")
        self.assertEqual(kwargs["photo"], "photo_file_123")
        self.assertEqual(kwargs["caption"], "Check out our autonomous drone!")

    async def test_broadcast_manual_submission_full_format(self):
        mock_bot = MagicMock()
        mock_sent_msg = MagicMock()
        mock_sent_msg.message_id = 4056
        mock_bot.send_photo = AsyncMock(return_value=mock_sent_msg)

        event = {
            "title": "Robotics Showcase",
            "club_name": "ASTU Robotics",
            "category_name": "Career/Workshop",
            "start_datetime": "2026-09-05T14:00:00Z",
            "location": "Main Stadium",
            "raw_content": {
                "media_type": "photo",
                "file_ids": ["photo_file_123"],
                "is_forwarded": False,
                "caption": "Full details typed by organizer manually.",
            }
        }

        msg_id = await broadcast_event_to_channel(mock_bot, event, channel_id="@astu_events")
        self.assertEqual(msg_id, 4056)
        mock_bot.send_photo.assert_called_once()
        _, kwargs = mock_bot.send_photo.call_args
        caption = kwargs["caption"]
        self.assertIn("NEW CAMPUS EVENT", caption)
        self.assertIn("Robotics Showcase", caption)
        self.assertIn("ASTU Robotics", caption)
        self.assertIn("Career/Workshop", caption)
        self.assertIn("Main Stadium", caption)
        self.assertIn("Full details typed by organizer manually.", caption)

    async def test_update_channel_message_in_place_forwarded(self):
        mock_bot = MagicMock()
        mock_bot.edit_message_caption = AsyncMock()

        event = {
            "title": "Updated Robotics Showcase",
            "club_name": "ASTU Robotics",
            "category_name": "Engineering",
            "start_datetime": "2026-09-05T15:00:00Z",
            "location": "Hall 508",
            "raw_content": {
                "media_type": "photo",
                "file_ids": ["photo_file_123"],
                "is_forwarded": True,
                "caption": "Updated schedule!",
            }
        }

        success = await update_channel_message_in_place(
            mock_bot,
            event,
            channel_id="@astu_events",
            message_id=4055,
        )
        self.assertTrue(success)
        mock_bot.edit_message_caption.assert_called_once()
        _, kwargs = mock_bot.edit_message_caption.call_args
        self.assertEqual(kwargs["chat_id"], "@astu_events")
        self.assertEqual(kwargs["message_id"], 4055)
        self.assertEqual(kwargs["caption"], "Updated schedule!")


class TestApiClientExtensions(unittest.IsolatedAsyncioTestCase):
    async def test_create_event(self):
        client = EventsApiClient(base_url="http://testserver/api")
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": 42, "title": "New Event", "status": "pending"}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            payload = {"title": "New Event", "club": 1, "start_datetime": "2026-09-10T10:00:00Z"}
            res = await client.create_event(payload)
            self.assertEqual(res["id"], 42)
            self.assertEqual(res["status"], "pending")
            mock_post.assert_called_once()

    async def test_update_event_status(self):
        client = EventsApiClient(base_url="http://testserver/api")
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": 42, "status": "approved", "channel_message_id": 999}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.patch", new_callable=AsyncMock) as mock_patch:
            mock_patch.return_value = mock_response
            res = await client.update_event_status(
                event_id=42,
                status_value="approved",
                admin_telegram_id=100000001,
                channel_message_id=999
            )
            self.assertEqual(res["status"], "approved")
            self.assertEqual(res["channel_message_id"], 999)
            mock_patch.assert_called_once()
            _, kwargs = mock_patch.call_args
            self.assertEqual(kwargs["headers"]["X-Telegram-User-Id"], "100000001")
            self.assertEqual(kwargs["json"], {"status": "approved", "channel_message_id": 999})

    async def test_add_and_remove_club_officer(self):
        client = EventsApiClient(base_url="http://testserver/api")
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": 1, "verified_officers": [111, 222]}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            res = await client.add_club_officer(club_id=1, officer_telegram_id=222, admin_telegram_id=100000001)
            self.assertIn(222, res["verified_officers"])
            mock_post.assert_called_once()

        with patch("httpx.AsyncClient.delete", new_callable=AsyncMock) as mock_del:
            mock_del.return_value = mock_response
            res = await client.remove_club_officer(club_id=1, officer_telegram_id=222, admin_telegram_id=100000001)
            mock_del.assert_called_once()

    async def test_create_club(self):
        client = EventsApiClient(base_url="http://testserver/api")
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": 10, "name": "ASTU Game Devs", "category_type": "Gaming"}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            res = await client.create_club(
                name="ASTU Game Devs",
                category_type="Gaming",
                admin_telegram_id=100000001,
            )
            self.assertEqual(res["id"], 10)
            self.assertEqual(res["name"], "ASTU Game Devs")
            mock_post.assert_called_once()
            _, kwargs = mock_post.call_args
            self.assertEqual(kwargs["json"], {"name": "ASTU Game Devs", "category_type": "Gaming", "contact_info": ""})



class TestFixesAndImprovements(unittest.IsolatedAsyncioTestCase):
    def test_format_channel_post_shows_only_original_caption_when_forwarded(self):
        from bot.formatters import format_channel_post
        original_caption = "🎉 ASTU Hackathon 2026! Bring your laptops to ICT 508 on Saturday at 2pm."
        event = {
            "title": "Hackathon",
            "club_name": "Coding Club",
            "category_name": "Academic",
            "start_datetime": "2026-09-05T14:00:00Z",
            "location": "ICT 508",
            "raw_content": {
                "media_type": "photo",
                "is_forwarded": True,
                "caption": original_caption,
            },
        }
        channel_post = format_channel_post(event)
        self.assertEqual(channel_post, original_caption)
        # Ensure NO structured fields are appended or inserted into the forwarded channel post
        self.assertNotIn("NEW CAMPUS EVENT", channel_post)
        self.assertNotIn("Organizer:", channel_post)
        self.assertNotIn("Category:", channel_post)
        self.assertNotIn("Location:", channel_post)

    def test_format_channel_post_manual_builds_full_structured_summary(self):
        from bot.formatters import format_channel_post
        event = {
            "title": "Robotics Demo Day",
            "club_name": "Robotics Society",
            "category_name": "Career/Workshop",
            "start_datetime": "2026-09-02T15:20:00Z",
            "location": "Hall A",
            "raw_content": {
                "media_type": "text",
                "is_forwarded": False,
                "caption": "Line 1: Exciting demos\nLine 2: Free snacks included!",
            },
        }
        channel_post = format_channel_post(event)
        self.assertIn("NEW CAMPUS EVENT", channel_post)
        self.assertIn("Robotics Demo Day", channel_post)
        self.assertIn("Robotics Society", channel_post)
        self.assertIn("Career/Workshop", channel_post)
        self.assertIn("Hall A", channel_post)
        self.assertIn("Line 1: Exciting demos", channel_post)
        self.assertIn("Line 2: Free snacks included!", channel_post)

    def test_format_admin_pending_card_includes_structured_fields(self):
        from bot.formatters import format_admin_pending_card
        event = {
            "title": "AI Workshop",
            "club": None,
            "custom_club": "AI Club",
            "club_name": "AI Club",
            "is_custom_club": True,
            "category": None,
            "custom_category": "Workshops",
            "category_name": "Workshops",
            "is_custom_category": True,
            "start_datetime": "2026-09-03T14:00:00Z",
            "location": "Lab 4",
            "raw_content": {"media_type": "photo", "caption": "Come join us!"},
        }
        card = format_admin_pending_card(event)
        self.assertIn("NEW EVENT PENDING APPROVAL", card)
        self.assertIn("AI Workshop", card)
        self.assertIn("Organizer:", card)
        self.assertIn("CUSTOM / UNVERIFIED ENTRY", card)
        self.assertIn("Category:", card)
        self.assertIn("CUSTOM / UNLISTED", card)
        self.assertIn("Location:", card)
        self.assertIn("Come join us!", card)

    async def test_send_admin_pending_notification_with_photo(self):
        from bot.handlers.admin import send_admin_pending_notification
        mock_bot = AsyncMock()
        mock_msg = MagicMock()
        mock_msg.message_id = 777
        mock_bot.send_photo.return_value = mock_msg

        event = {
            "id": 101,
            "title": "Basketball Match",
            "club_name": "Sports Club",
            "category_name": "Sports",
            "start_datetime": "2026-09-04T16:00:00Z",
            "location": "Court 1",
            "raw_content": {
                "media_type": "photo",
                "file_ids": ["photo_file_123"],
                "caption": "Championship match!",
            },
        }

        msg_id = await send_admin_pending_notification(mock_bot, event, admin_group_id=-100123456)
        self.assertEqual(msg_id, 777)
        mock_bot.send_photo.assert_called_once()
        _, kwargs = mock_bot.send_photo.call_args
        self.assertEqual(kwargs["chat_id"], -100123456)
        self.assertEqual(kwargs["photo"], "photo_file_123")
        self.assertIn("Basketball Match", kwargs["caption"])
        self.assertIsNotNone(kwargs["reply_markup"])


    async def test_caption_length_900_chars_broadcast_single_message(self):
        mock_bot = AsyncMock()
        mock_msg = MagicMock()
        mock_msg.message_id = 901
        mock_bot.send_photo.return_value = mock_msg

        caption_900 = "A" * 900
        event = {
            "title": "Short Caption Event",
            "club_name": "Coding Club",
            "category_name": "Tech",
            "start_datetime": "2026-09-04T16:00:00Z",
            "location": "ICT 508",
            "raw_content": {
                "media_type": "photo",
                "file_ids": ["photo_file_123"],
                "is_forwarded": True,
                "caption": caption_900,
            },
        }

        msg_id = await broadcast_event_to_channel(mock_bot, event, channel_id="@test_channel")
        self.assertEqual(msg_id, 901)
        mock_bot.send_photo.assert_called_once()
        # Should not send secondary follow up message
        mock_bot.send_message.assert_not_called()
        _, kwargs = mock_bot.send_photo.call_args
        self.assertEqual(kwargs["caption"], caption_900)

    async def test_caption_length_1024_chars_broadcast_single_message(self):
        mock_bot = AsyncMock()
        mock_msg = MagicMock()
        mock_msg.message_id = 1024
        mock_bot.send_photo.return_value = mock_msg

        caption_1024 = "B" * 1024
        event = {
            "title": "Exact 1024 Caption Event",
            "club_name": "Coding Club",
            "category_name": "Tech",
            "start_datetime": "2026-09-04T16:00:00Z",
            "location": "ICT 508",
            "raw_content": {
                "media_type": "photo",
                "file_ids": ["photo_file_123"],
                "is_forwarded": True,
                "caption": caption_1024,
            },
        }

        msg_id = await broadcast_event_to_channel(mock_bot, event, channel_id="@test_channel")
        self.assertEqual(msg_id, 1024)
        mock_bot.send_photo.assert_called_once()
        mock_bot.send_message.assert_not_called()

    async def test_caption_length_1025_chars_broadcast_with_reply_message(self):
        mock_bot = AsyncMock()
        mock_photo_msg = MagicMock()
        mock_photo_msg.message_id = 2001
        mock_bot.send_photo.return_value = mock_photo_msg

        mock_reply_msg = MagicMock()
        mock_reply_msg.message_id = 2002
        mock_bot.send_message.return_value = mock_reply_msg

        caption_1025 = "C" * 1025
        event = {
            "title": "Long 1025 Caption Event",
            "club_name": "Coding Club",
            "category_name": "Tech",
            "start_datetime": "2026-09-04T16:00:00Z",
            "location": "ICT 508",
            "raw_content": {
                "media_type": "photo",
                "file_ids": ["photo_file_123"],
                "is_forwarded": True,
                "caption": caption_1025,
            },
        }

        msg_id = await broadcast_event_to_channel(mock_bot, event, channel_id="@test_channel")
        self.assertEqual(msg_id, 2001)
        mock_bot.send_photo.assert_called_once()
        # Full text must be preserved in the follow-up message reply
        mock_bot.send_message.assert_called_once()
        _, msg_kwargs = mock_bot.send_message.call_args
        self.assertEqual(msg_kwargs["text"], caption_1025)
        self.assertEqual(msg_kwargs["reply_to_message_id"], 2001)
        self.assertEqual(event["raw_content"]["channel_extra_message_id"], 2002)

    async def test_text_length_4100_chars_broadcast_split(self):
        mock_bot = AsyncMock()
        mock_msg1 = MagicMock()
        mock_msg1.message_id = 3001
        mock_msg2 = MagicMock()
        mock_msg2.message_id = 3002
        mock_bot.send_message.side_effect = [mock_msg1, mock_msg2]

        text_4100 = "D" * 4100
        event = {
            "title": "Huge Text Event",
            "club_name": "Debate Club",
            "category_name": "Academic",
            "start_datetime": "2026-09-04T16:00:00Z",
            "location": "Auditorium",
            "raw_content": {
                "media_type": "text",
                "is_forwarded": True,
                "caption": text_4100,
            },
        }

        msg_id = await broadcast_event_to_channel(mock_bot, event, channel_id="@test_channel")
        self.assertEqual(msg_id, 3001)
        self.assertEqual(mock_bot.send_message.call_count, 2)
        call1_args, call1_kwargs = mock_bot.send_message.call_args_list[0]
        call2_args, call2_kwargs = mock_bot.send_message.call_args_list[1]
        self.assertEqual(len(call1_kwargs["text"]), 4096)
        self.assertEqual(len(call2_kwargs["text"]), 4)
        self.assertEqual(call2_kwargs["reply_to_message_id"], 3001)

    async def test_idle_message_handler_from_officer_shows_friendly_hint(self):
        update = MagicMock(spec=Update)
        msg = MagicMock(spec=Message)
        msg.reply_text = AsyncMock()
        update.effective_message = msg

        user = MagicMock(spec=User)
        user.id = 555666
        update.effective_user = user
        context = MagicMock()

        # Officer is recognized
        with patch("bot.main.get_user_verified_clubs", new_callable=AsyncMock) as mock_clubs:
            mock_clubs.return_value = [{"id": 1, "name": "AASTU Coding Club"}]
            await idle_message_handler(update, context)

            msg.reply_text.assert_called_once()
            call_text = msg.reply_text.call_args[0][0]
            self.assertIn("You forwarded a message!", call_text)
            self.assertIn("/submit", call_text)
            self.assertIn("Submit Post", call_text)

    async def test_idle_message_handler_from_regular_user_shows_polite_menu(self):
        update = MagicMock(spec=Update)
        msg = MagicMock(spec=Message)
        msg.reply_text = AsyncMock()
        update.effective_message = msg

        user = MagicMock(spec=User)
        user.id = 999888
        update.effective_user = user
        context = MagicMock()

        # Regular user (not officer, not owner)
        with patch("bot.main.get_user_verified_clubs", new_callable=AsyncMock) as mock_clubs:
            mock_clubs.return_value = []
            await idle_message_handler(update, context)

            msg.reply_text.assert_called_once()
            call_text = msg.reply_text.call_args[0][0]
            self.assertIn("Welcome to Addis Ababa Science and Technology University (AASTU) Events Hub", call_text)
            self.assertIn("/events", call_text)

    def test_extract_telegram_id_from_private_forward_shows_clear_message(self):
        msg = MagicMock()
        msg.text = None
        msg.forward_from = None
        msg.forward_origin = MagicMock()
        msg.forward_origin.type = "hidden_user"
        msg.forward_from_chat = None
        msg.forward_sender_name = "Anonymous User"
        msg.forward_date = datetime.now()

        tid, name, err = extract_telegram_id_from_message(msg)
        self.assertIsNone(tid)
        self.assertIsNotNone(err)
        self.assertIn("forward privacy", err)
        self.assertIn("type their numeric Telegram ID manually", err)

    async def test_handle_submission_confirmation_admin_direct_publish(self):
        from bot.handlers.submit import handle_submission_confirmation

        update = MagicMock(spec=Update)
        query = MagicMock(spec=CallbackQuery)
        query.edit_message_text = AsyncMock()
        query.answer = AsyncMock()
        update.callback_query = query

        user = MagicMock(spec=User)
        user.id = 100000001
        user.full_name = "Admin User"
        update.effective_user = user

        context = MagicMock()
        context.user_data = {
            "submission": {
                "title": "Direct Published Event",
                "start_datetime_iso": "2026-09-15T14:30:00+03:00",
                "club": 1,
                "club_name": "AASTU Coding Club",
                "location": "Hall A",
                "raw_content": {"media_type": "text", "caption": "Official direct event"},
            }
        }
        context.bot = AsyncMock()

        created_event = {
            "id": 88,
            "title": "Direct Published Event",
            "status": "approved",
            "club": 1,
            "raw_content": {"media_type": "text", "caption": "Official direct event"},
        }

        with patch("bot.handlers.submit.api_client.create_event", new_callable=AsyncMock) as mock_create, \
             patch("bot.handlers.submit.api_client.update_event_status", new_callable=AsyncMock) as mock_update_status, \
             patch("bot.handlers.admin.broadcast_event_to_channel", new_callable=AsyncMock) as mock_broadcast, \
             patch("bot.handlers.submit.TELEGRAM_ADMIN_GROUP_ID", -100123456), \
             patch("bot.handlers.submit.TELEGRAM_PUBLIC_CHANNEL_ID", "@aastu_events"):

            mock_create.return_value = created_event
            mock_broadcast.return_value = 5001

            res = await handle_submission_confirmation(update, context)
            self.assertEqual(res, ConversationHandler.END)

            # Assert broadcast was invoked immediately
            mock_broadcast.assert_called_once()
            # Assert confirmation text indicates direct publish
            query.edit_message_text.assert_called_once()
            edit_text = query.edit_message_text.call_args[0][0]
            self.assertIn("Event Published Directly!", edit_text)

            # Assert one-line info log sent to Admin Group without approval buttons
            context.bot.send_message.assert_called_once()
            _, msg_kwargs = context.bot.send_message.call_args
            self.assertEqual(msg_kwargs["chat_id"], -100123456)
            self.assertIn("posted directly by", msg_kwargs["text"])


if __name__ == '__main__':
    unittest.main()


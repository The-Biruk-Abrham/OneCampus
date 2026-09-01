import unittest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime
from telegram import Update, Message, User, PhotoSize, Video

from bot.handlers.submit import (
    extract_raw_content,
    parse_event_datetime,
)
from bot.handlers.admin import (
    broadcast_event_to_channel,
    update_channel_message_in_place,
)
from bot.api_client import EventsApiClient


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
    msg.forward_from_chat = kwargs.get('forward_from_chat', None)
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

    def test_extract_raw_content_video(self):
        update = MagicMock(spec=Update)
        msg = _make_mock_message(video=MagicMock(file_id="vid_file_999"), caption="🎥 Live robot demo recording")
        user = MagicMock(spec=User)
        user.id = 12345
        user.username = "video_poster"

        update.message = msg
        update.effective_user = user

        raw = extract_raw_content(update)
        self.assertEqual(raw["media_type"], "video")
        self.assertEqual(raw["file_ids"], ["vid_file_999"])
        self.assertEqual(raw["caption"], "🎥 Live robot demo recording")

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
        self.assertEqual(raw["forward_info"]["chat_title"], "ASTU Official Channel")

    def test_extract_raw_content_poll(self):
        update = MagicMock(spec=Update)
        msg = _make_mock_message(poll=MagicMock(question="Which workshop topic do you prefer?"))
        user = MagicMock(spec=User)
        user.id = 777888
        user.username = "poll_maker"

        update.message = msg
        update.effective_user = user

        raw = extract_raw_content(update)
        self.assertEqual(raw["media_type"], "poll")
        self.assertIn("Which workshop topic do you prefer?", raw["caption"])

    async def test_handle_content_received_with_empty_user_data(self):
        from bot.handlers.submit import handle_content_received, STATE_TITLE

        update = MagicMock(spec=Update)
        msg = _make_mock_message(text="Forwarded post")
        msg.reply_text = AsyncMock()

        user = MagicMock(spec=User)
        user.id = 111222
        user.username = "organizer"

        update.message = msg
        update.effective_user = user

        context = MagicMock()
        context.user_data = {}  # completely uninitialized

        next_state = await handle_content_received(update, context)
        self.assertEqual(next_state, STATE_TITLE)
        self.assertIn('submission', context.user_data)
        self.assertEqual(context.user_data['submission']['raw_content']['media_type'], 'text')



class TestAdminChannelBroadcast(unittest.IsolatedAsyncioTestCase):
    async def test_broadcast_photo_event_to_channel(self):
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

    async def test_update_channel_message_in_place(self):
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


class TestFixesAndImprovements(unittest.IsolatedAsyncioTestCase):
    def test_format_channel_post_shows_only_original_caption(self):
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
        # Ensure NO structured fields are appended or inserted into the channel post
        self.assertNotIn("NEW EVENT", channel_post)
        self.assertNotIn("Hosted by", channel_post)
        self.assertNotIn("Category:", channel_post)
        self.assertNotIn("Venue:", channel_post)
        self.assertNotIn("Original Announcement:", channel_post)

    def test_format_channel_post_fallback_to_title(self):
        from bot.formatters import format_channel_post
        event = {
            "title": "Robotics Demo",
            "club_name": "Robotics Society",
            "category_name": "Academic",
            "start_datetime": "2026-09-02T15:20:00Z",
            "location": "Hall A",
            "raw_content": {
                "media_type": "text",
                "caption": "",
            },
        }
        channel_post = format_channel_post(event)
        self.assertEqual(channel_post, "Robotics Demo")

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

    def test_format_single_event_flags_custom_club_and_category(self):
        from bot.formatters import format_single_event
        event = {
            "title": "Indie Game Night",
            "club": None,
            "custom_club": "ASTU Game Devs",
            "club_name": "ASTU Game Devs",
            "is_custom_club": True,
            "category": None,
            "custom_category": "Gaming",
            "category_name": "Gaming",
            "is_custom_category": True,
            "start_datetime": "2026-09-04T18:00:00Z",
            "location": "Lounge 3",
            "raw_content": {},
        }
        formatted = format_single_event(event)
        self.assertIn("CUSTOM / UNVERIFIED ENTRY", formatted)
        self.assertIn("CUSTOM / UNLISTED", formatted)
        self.assertIn("ASTU Game Devs", formatted)
        self.assertIn("Gaming", formatted)

    def test_custom_club_length_validation(self):
        from bot.handlers.submit import render_preview_text
        sub = {
            "title": "Chess Tournament",
            "club": None,
            "custom_club": "ASTU Grandmaster Chess Enthusiasts Society",
            "club_name": "ASTU Grandmaster Chess Enthusiasts Society",
            "is_custom_club": True,
            "category": 1,
            "category_name": "Sports",
            "is_custom_category": False,
            "start_datetime_display": "Saturday, Sep 05, 2026 at 02:00 PM",
            "location": "Library Hall",
            "raw_content": {"media_type": "text", "caption": "Join us!"},
        }
        preview = render_preview_text(sub)
        self.assertIn("SUBMISSION PREVIEW", preview)
        self.assertIn("Chess Tournament", preview)
        self.assertIn("Custom / Unverified", preview)


if __name__ == '__main__':
    unittest.main()

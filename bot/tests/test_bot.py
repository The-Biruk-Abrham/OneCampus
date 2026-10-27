import unittest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from bot.formatters import (
    get_category_emoji,
    parse_datetime,
    format_time_range,
    format_event_card,
    format_single_event,
    format_today_events,
    format_week_events,
    format_category_events,
    format_channel_post,
)
from bot.pagination import (
    build_pagination_keyboard,
    build_category_keyboard,
    build_category_events_keyboard,
    build_single_action_keyboard,
    build_start_keyboard,
)
from bot.api_client import EventsApiClient
from bot.main import build_bot_application


class TestFormatters(unittest.TestCase):
    def setUp(self):
        self.sample_event = {
            "id": 1,
            "title": "Robotics & AI Expo 2026",
            "club_name": "ASTU Robotics Society",
            "category_name": "Career/Workshop",
            "start_datetime": "2026-09-05T14:00:00Z",
            "end_datetime": "2026-09-05T17:00:00Z",
            "location": "Auditorium Hall",
            "recurring": False,
            "recurrence_pattern": None,
            "raw_content": {
                "media_type": "photo",
                "caption": "🤖 Don't miss our live drone flight showcase!",
                "file_ids": ["sample_file_id_123"]
            }
        }

    def test_get_category_emoji(self):
        self.assertEqual(get_category_emoji("Academic"), "🎓")
        self.assertEqual(get_category_emoji("Sports"), "⚽")
        self.assertEqual(get_category_emoji("Career/Workshop"), "💼")
        self.assertEqual(get_category_emoji("UnknownCategory"), "📌")

    def test_parse_datetime_and_format_time_range(self):
        dt1 = parse_datetime("2026-09-05T14:00:00Z")
        dt2 = parse_datetime("2026-09-05T17:30:00Z")
        self.assertIsNotNone(dt1)
        # 14:00 UTC is 17:00 Addis Ababa time (UTC+3)
        self.assertEqual(dt1.hour, 17)
        formatted = format_time_range(dt1, dt2)
        self.assertEqual(formatted, "5:00 PM – 8:30 PM")

    def test_format_event_card(self):
        card = format_event_card(self.sample_event, index=1)
        self.assertIn("1. *Robotics & AI Expo 2026*", card)
        self.assertIn("ASTU Robotics Society", card)
        self.assertIn("Auditorium Hall", card)

    def test_format_single_event(self):
        detailed = format_single_event(self.sample_event)
        self.assertIn("Robotics & AI Expo 2026", detailed)
        self.assertIn("ASTU Robotics Society", detailed)
        self.assertIn("Don't miss our live drone flight showcase!", detailed)

    def test_format_today_events_with_items(self):
        events = [self.sample_event]
        text, total_pages, total_count = format_today_events(events, page=1, page_size=2)
        self.assertEqual(total_count, 1)
        self.assertEqual(total_pages, 1)
        self.assertIn("Today at AASTU", text)
        self.assertIn("Robotics & AI Expo 2026", text)

    def test_format_today_events_empty(self):
        text, total_pages, total_count = format_today_events([], page=1)
        self.assertEqual(total_count, 0)
        self.assertEqual(total_pages, 0)
        self.assertIn("No events scheduled for today", text)

    def test_format_week_events_grouped(self):
        event2 = dict(self.sample_event)
        event2["title"] = "Football League Match"
        event2["category_name"] = "Sports"
        event2["start_datetime"] = "2026-09-06T16:00:00Z"
        event2["end_datetime"] = "2026-09-06T18:00:00Z"

        events = [self.sample_event, event2]
        text = format_week_events(events)
        self.assertIn("This Week at AASTU", text)
        self.assertIn("Saturday, Sep 05", text)
        self.assertIn("Sunday, Sep 06", text)
        self.assertIn("Robotics & AI Expo 2026", text)
        self.assertIn("Football League Match", text)

    def test_format_week_events_empty(self):
        text = format_week_events([])
        self.assertIn("No events scheduled for this week yet", text)

    def test_format_category_events(self):
        events = [self.sample_event]
        text, total_pages, total_count = format_category_events("Career/Workshop", events, page=1)
        self.assertEqual(total_count, 1)
        self.assertIn("Career/Workshop Events", text)
        self.assertIn("Robotics & AI Expo 2026", text)

    def test_format_channel_post_forwarded(self):
        fwd_event = dict(self.sample_event)
        fwd_event["raw_content"] = {
            "media_type": "photo",
            "is_forwarded": True,
            "caption": "🤖 Don't miss our live drone flight showcase!",
            "file_ids": ["sample_file_id_123"],
        }
        post = format_channel_post(fwd_event)
        self.assertEqual(post, "🤖 Don't miss our live drone flight showcase!")

    def test_format_channel_post_manual(self):
        manual_event = dict(self.sample_event)
        manual_event["raw_content"] = {
            "media_type": "text",
            "is_forwarded": False,
            "caption": "Please bring your student ID and laptop.",
        }
        post = format_channel_post(manual_event)
        self.assertIn("NEW CAMPUS EVENT", post)
        self.assertIn("Robotics & AI Expo 2026", post)
        self.assertIn("ASTU Robotics Society", post)
        self.assertIn("Career/Workshop", post)
        self.assertIn("Auditorium Hall", post)
        self.assertIn("Please bring your student ID and laptop.", post)


class TestPagination(unittest.TestCase):
    def test_build_pagination_keyboard_single_page_without_nav(self):
        kb = build_pagination_keyboard(current_page=1, total_pages=1, callback_prefix="page:today")
        self.assertIsNone(kb)

    def test_build_pagination_keyboard_multi_page(self):
        kb = build_pagination_keyboard(current_page=1, total_pages=3, callback_prefix="page:today", show_main_menu=True)
        self.assertIsNotNone(kb)
        self.assertEqual(len(kb.inline_keyboard), 2)  # Page buttons row + Nav row
        page_buttons = kb.inline_keyboard[0]
        self.assertEqual(len(page_buttons), 3)
        self.assertEqual(page_buttons[0].callback_data, "noop")  # prev disabled on page 1
        self.assertEqual(page_buttons[1].text, "1 / 3")
        self.assertEqual(page_buttons[2].callback_data, "page:today:2")  # next enabled
        nav_buttons = kb.inline_keyboard[1]
        self.assertEqual(nav_buttons[0].callback_data, "btn:main_menu")

    def test_build_category_keyboard(self):
        categories = [
            {"id": 1, "name": "Academic"},
            {"id": 2, "name": "Sports"},
            {"id": 3, "name": "Entertainment"},
        ]
        kb = build_category_keyboard(categories)
        self.assertIsNotNone(kb)
        # 2 rows for categories + 1 row for Back to Main Menu
        self.assertEqual(len(kb.inline_keyboard), 3)
        self.assertIn("🎓 Academic", kb.inline_keyboard[0][0].text)
        self.assertEqual(kb.inline_keyboard[0][0].callback_data, "cat:select:1")
        # Bottom row
        self.assertEqual(kb.inline_keyboard[2][0].text, "🔙 Back to Main Menu")
        self.assertEqual(kb.inline_keyboard[2][0].callback_data, "btn:main_menu")

    def test_build_category_events_keyboard(self):
        kb = build_category_events_keyboard(category_identifier="sports", current_page=1, total_pages=2)
        self.assertIsNotNone(kb)
        self.assertEqual(len(kb.inline_keyboard), 2)
        nav_row = kb.inline_keyboard[1]
        self.assertEqual(len(nav_row), 2)
        self.assertEqual(nav_row[0].text, "🔙 Categories")
        self.assertEqual(nav_row[0].callback_data, "btn:categories")
        self.assertEqual(nav_row[1].text, "🏠 Main Menu")
        self.assertEqual(nav_row[1].callback_data, "btn:main_menu")

    def test_build_single_action_keyboard(self):
        kb = build_single_action_keyboard(back_callback="btn:categories", show_main_menu=True)
        self.assertIsNotNone(kb)
        self.assertEqual(len(kb.inline_keyboard[0]), 2)
        self.assertEqual(kb.inline_keyboard[0][0].callback_data, "btn:categories")
        self.assertEqual(kb.inline_keyboard[0][1].callback_data, "btn:main_menu")

    def test_build_start_keyboard_standard_user(self):
        kb = build_start_keyboard(is_owner=False, is_officer=False)
        self.assertIsNotNone(kb)
        self.assertEqual(len(kb.inline_keyboard), 2)  # Today/Week, Categories (No Submit Button for non-reps)
        self.assertEqual(kb.inline_keyboard[0][0].callback_data, "btn:today")
        self.assertEqual(kb.inline_keyboard[1][0].callback_data, "btn:categories")

    def test_build_start_keyboard_officer(self):
        kb = build_start_keyboard(is_owner=False, is_officer=True)
        self.assertIsNotNone(kb)
        self.assertEqual(len(kb.inline_keyboard), 3)  # Today/Week, Categories, Submit Post
        self.assertEqual(kb.inline_keyboard[0][0].callback_data, "btn:today")
        self.assertEqual(kb.inline_keyboard[2][0].callback_data, "btn:submit")
        self.assertIn("Submit Post", kb.inline_keyboard[2][0].text)

    def test_build_start_keyboard_owner(self):
        kb = build_start_keyboard(is_owner=True)
        self.assertIsNotNone(kb)
        self.assertEqual(len(kb.inline_keyboard), 5)  # Today/Week, Categories, Submit, Owner Admin Row, Register Club Row
        self.assertEqual(kb.inline_keyboard[3][0].callback_data, "owner:add_admin")
        self.assertEqual(kb.inline_keyboard[3][1].callback_data, "owner:remove_admin")
        self.assertEqual(kb.inline_keyboard[4][0].callback_data, "owner:create_club")



class TestBotApiClient(unittest.IsolatedAsyncioTestCase):
    async def test_get_events_calls_endpoint(self):
        client = EventsApiClient(base_url="http://testserver/api")
        mock_response = MagicMock()
        mock_response.json.return_value = [{"id": 1, "title": "Mock Event"}]
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await client.get_events(range_type="today", category="1")
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["title"], "Mock Event")
            mock_get.assert_called_once()
            call_args, call_kwargs = mock_get.call_args
            self.assertEqual(call_kwargs["params"], {"range": "today", "category": "1"})

    async def test_get_categories_calls_endpoint(self):
        client = EventsApiClient(base_url="http://testserver/api")
        mock_response = MagicMock()
        mock_response.json.return_value = [{"id": 1, "name": "Sports"}]
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await client.get_categories()
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["name"], "Sports")


class TestBotApplicationBuilder(unittest.TestCase):
    def test_build_bot_application_missing_token_raises(self):
        with self.assertRaises(ValueError):
            build_bot_application(token="")

    def test_build_bot_application_with_token(self):
        dummy_token = "123456789:ABCDEF_mock_token_for_unit_tests_12345"
        app = build_bot_application(token=dummy_token)
        self.assertIsNotNone(app)
        self.assertTrue(len(app.handlers[0]) >= 15)


if __name__ == '__main__':
    unittest.main()


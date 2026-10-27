from datetime import timedelta
from django.test import TestCase, RequestFactory
from django.utils import timezone
from django.core.management import call_command
from django.contrib.auth.models import User
from django.contrib.messages.storage.cookie import CookieStorage
from rest_framework import status
from rest_framework.test import APITestCase

from events.models import Category, Club, Event, Admin as TelegramAdmin, EventStatus, PermissionLevel
from events.admin import (
    EventAdmin,
    approve_selected_events,
    reject_selected_events,
    cancel_selected_events,
)


class CategoryModelTest(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name="Academic",
            description="Lectures, seminars, research talks."
        )

    def test_category_creation_and_str(self):
        self.assertEqual(str(self.category), "Academic")
        self.assertEqual(self.category.name, "Academic")
        self.assertEqual(self.category.description, "Lectures, seminars, research talks.")


class ClubModelTest(TestCase):
    def setUp(self):
        self.club = Club.objects.create(
            name="ASTU Coding Club",
            category_type="Technology",
            verified_officers=[111222, "333444"],
            contact_info="contact@astu.edu.et"
        )

    def test_club_creation_and_str(self):
        self.assertEqual(str(self.club), "ASTU Coding Club")
        self.assertEqual(self.club.category_type, "Technology")

    def test_is_officer_check(self):
        # Should verify with integer or string ID
        self.assertTrue(self.club.is_officer(111222))
        self.assertTrue(self.club.is_officer("111222"))
        self.assertTrue(self.club.is_officer(333444))
        self.assertTrue(self.club.is_officer("333444"))
        self.assertFalse(self.club.is_officer(999999))


class AdminModelTest(TestCase):
    def setUp(self):
        self.admin = TelegramAdmin.objects.create(
            telegram_id=9876543210,
            name="Test Superadmin",
            permission_level=PermissionLevel.SUPERADMIN
        )

    def test_admin_creation_and_str(self):
        self.assertEqual(str(self.admin), "Test Superadmin (Superadmin)")
        self.assertEqual(self.admin.telegram_id, 9876543210)
        self.assertTrue(self.admin.is_active)


class EventModelTest(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Sports", description="Athletics")
        self.club = Club.objects.create(
            name="ASTU Sports Guild",
            category_type="Sports",
            verified_officers=[12345]
        )
        self.start = timezone.now() + timedelta(days=1)
        self.end = self.start + timedelta(hours=3)
        self.raw_content = {
            "media_type": "photo",
            "file_ids": ["AgACAgIAAxkBAAICamX1234"],
            "caption": "⚽ Come support our football team this Saturday!"
        }
        self.event = Event.objects.create(
            club=self.club,
            category=self.category,
            title="Football Semi-Finals",
            start_datetime=self.start,
            end_datetime=self.end,
            location="Main Stadium",
            raw_content=self.raw_content,
            status=EventStatus.PENDING
        )

    def test_event_creation_and_fields(self):
        self.assertEqual(self.event.title, "Football Semi-Finals")
        self.assertEqual(self.event.status, EventStatus.PENDING)
        self.assertEqual(self.event.raw_content["media_type"], "photo")
        self.assertEqual(len(self.event.raw_content["file_ids"]), 1)
        self.assertIn("Football Semi-Finals", str(self.event))

    def test_status_transitions_and_helper_methods(self):
        # Approve
        self.event.approve(approver_identifier="admin_alex", channel_msg_id=7788)
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, EventStatus.APPROVED)
        self.assertEqual(self.event.approved_by, "admin_alex")
        self.assertEqual(self.event.channel_message_id, 7788)
        self.assertIsNotNone(self.event.approved_at)

        # Reject
        self.event.reject(approver_identifier="admin_beth")
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, EventStatus.REJECTED)
        self.assertEqual(self.event.approved_by, "admin_beth")

        # Cancel
        self.event.cancel()
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, EventStatus.CANCELLED)

    def test_query_filter_by_status_and_date(self):
        # Create another event with different status
        approved_event = Event.objects.create(
            club=self.club,
            category=self.category,
            title="Approved Marathon",
            start_datetime=timezone.now() + timedelta(days=2),
            location="Campus Loop",
            status=EventStatus.APPROVED
        )

        pending_events = Event.objects.filter(status=EventStatus.PENDING)
        approved_events = Event.objects.filter(status=EventStatus.APPROVED)

        self.assertIn(self.event, pending_events)
        self.assertNotIn(approved_event, pending_events)
        self.assertIn(approved_event, approved_events)


class AdminActionTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_superuser(
            username='admin_user',
            email='admin@example.com',
            password='password123'
        )
        self.club = Club.objects.create(name="Tech Club")
        self.category = Category.objects.create(name="Tech")
        self.event1 = Event.objects.create(
            club=self.club,
            category=self.category,
            title="Event 1",
            start_datetime=timezone.now(),
            location="Hall A",
            status=EventStatus.PENDING
        )
        self.event2 = Event.objects.create(
            club=self.club,
            category=self.category,
            title="Event 2",
            start_datetime=timezone.now(),
            location="Hall B",
            status=EventStatus.PENDING
        )

    def test_admin_approve_and_reject_actions(self):
        request = self.factory.get('/admin/events/event/')
        request.user = self.user
        setattr(request, '_messages', CookieStorage(request))

        event_admin = EventAdmin(Event, None)

        # Test approve action
        approve_selected_events(event_admin, request, Event.objects.filter(id=self.event1.id))
        self.event1.refresh_from_db()
        self.assertEqual(self.event1.status, EventStatus.APPROVED)
        self.assertIsNotNone(self.event1.approved_at)

        # Test reject action
        reject_selected_events(event_admin, request, Event.objects.filter(id=self.event2.id))
        self.event2.refresh_from_db()
        self.assertEqual(self.event2.status, EventStatus.REJECTED)

        # Test cancel action
        cancel_selected_events(event_admin, request, Event.objects.filter(id=self.event1.id))
        self.event1.refresh_from_db()
        self.assertEqual(self.event1.status, EventStatus.CANCELLED)


class SeedDataCommandTest(TestCase):
    def test_seed_data_execution(self):
        call_command('seed_data', clear=True)
        self.assertGreaterEqual(Category.objects.count(), 7)
        self.assertGreaterEqual(Club.objects.count(), 3)
        self.assertGreaterEqual(TelegramAdmin.objects.count(), 3)
        self.assertGreaterEqual(Event.objects.count(), 5)

        # Verify all statuses are represented
        self.assertTrue(Event.objects.filter(status=EventStatus.PENDING).exists())
        self.assertTrue(Event.objects.filter(status=EventStatus.APPROVED).exists())
        self.assertTrue(Event.objects.filter(status=EventStatus.REJECTED).exists())
        self.assertTrue(Event.objects.filter(status=EventStatus.CANCELLED).exists())

        # Test idempotency (running without --clear shouldn't crash)
        call_command('seed_data')
        self.assertGreaterEqual(Event.objects.count(), 5)


class EventsAPITestCase(APITestCase):
    def setUp(self):
        from django.conf import settings
        self.internal_secret = getattr(settings, 'INTERNAL_API_SECRET', 'hub-secret-dev-token-987412365')
        self.client.credentials(HTTP_X_HUB_INTERNAL_SECRET=self.internal_secret)

        self.now = timezone.localtime(timezone.now())
        self.admin_telegram_id = 999000111
        self.admin = TelegramAdmin.objects.create(
            telegram_id=self.admin_telegram_id,
            name="API Superadmin",
            permission_level=PermissionLevel.SUPERADMIN,
            is_active=True
        )
        self.category_sports = Category.objects.create(name="Sports", description="Sports events")
        self.category_academic = Category.objects.create(name="Academic", description="Lectures")
        self.club = Club.objects.create(
            name="AASTU Developer Club",
            category_type="Technology",
            verified_officers=[123456],
            contact_info="devs@aastu.edu.et"
        )

        # Approved Event Today
        self.event_today = Event.objects.create(
            club=self.club,
            category=self.category_sports,
            title="Football Match Today",
            start_datetime=self.now.replace(hour=15, minute=0, second=0),
            location="Main Stadium",
            status=EventStatus.APPROVED,
            raw_content={"media_type": "photo", "file_ids": ["fid123"], "caption": "Today's match!"}
        )

        # Approved Event in 3 Days (This Week)
        self.event_week = Event.objects.create(
            club=self.club,
            category=self.category_academic,
            title="AI Workshop This Week",
            start_datetime=self.now + timedelta(days=3),
            location="Hall 508",
            status=EventStatus.APPROVED,
            raw_content={"media_type": "text", "file_ids": [], "caption": "Join us!"}
        )

        # Pending Event
        self.event_pending = Event.objects.create(
            club=self.club,
            category=self.category_academic,
            title="Pending Guest Lecture",
            start_datetime=self.now + timedelta(days=4),
            location="Auditorium",
            status=EventStatus.PENDING,
            raw_content={"media_type": "document", "file_ids": ["doc999"], "caption": "Pending approval"}
        )

    def test_missing_or_invalid_internal_api_secret_denied(self):
        # Request without header
        self.client.credentials()
        response = self.client.get('/api/events/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Request with wrong secret
        self.client.credentials(HTTP_X_HUB_INTERNAL_SECRET="wrong-secret")
        response = self.client.get('/api/events/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Restore valid secret
        self.client.credentials(HTTP_X_HUB_INTERNAL_SECRET=self.internal_secret)

    def test_get_events_today_range(self):
        response = self.client.get('/api/events/?range=today')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [e['title'] for e in response.data]
        self.assertIn("Football Match Today", titles)
        self.assertNotIn("AI Workshop This Week", titles)
        # Pending events should not appear in public query
        self.assertNotIn("Pending Guest Lecture", titles)

    def test_timezone_midnight_boundary_today_and_tomorrow(self):
        local_today_start = self.now.replace(hour=0, minute=0, second=0, microsecond=0)
        # 23:30 local time today
        event_late_today = Event.objects.create(
            club=self.club,
            category=self.category_sports,
            title="Late Night Hackathon Session",
            start_datetime=local_today_start.replace(hour=23, minute=30),
            location="ICT Lab",
            status=EventStatus.APPROVED
        )
        # 00:30 local time tomorrow
        event_early_tomorrow = Event.objects.create(
            club=self.club,
            category=self.category_sports,
            title="Early Morning Dawn Run",
            start_datetime=(local_today_start + timedelta(days=1)).replace(hour=0, minute=30),
            location="Track Field",
            status=EventStatus.APPROVED
        )

        response = self.client.get('/api/events/?range=today')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [e['title'] for e in response.data]
        self.assertIn("Late Night Hackathon Session", titles)
        self.assertNotIn("Early Morning Dawn Run", titles)

    def test_get_events_week_range(self):
        response = self.client.get('/api/events/?range=week')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [e['title'] for e in response.data]
        self.assertIn("Football Match Today", titles)
        self.assertIn("AI Workshop This Week", titles)
        self.assertNotIn("Pending Guest Lecture", titles)

    def test_get_events_filtered_by_category(self):
        response = self.client.get(f'/api/events/?category={self.category_sports.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [e['title'] for e in response.data]
        self.assertIn("Football Match Today", titles)
        self.assertNotIn("AI Workshop This Week", titles)

    def test_post_event_by_officer_creates_pending_status(self):
        payload = {
            "title": "Freshman Orientation",
            "club": self.club.id,
            "category": self.category_academic.id,
            "start_datetime": (self.now + timedelta(days=5)).isoformat(),
            "location": "Graduation Hall",
            "raw_content": {
                "media_type": "photo",
                "file_ids": ["AgACAgIAAxkBAAICsample"],
                "caption": "Welcome freshmen!"
            },
            # Submitter tries to set status to approved
            "status": "approved"
        }
        # Submitter is verified officer 123456
        response = self.client.post(
            '/api/events/',
            data=payload,
            format='json',
            HTTP_X_TELEGRAM_USER_ID="123456"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_id = response.data['id']
        created_event = Event.objects.get(id=created_id)
        # Verify status is forced to PENDING for officer
        self.assertEqual(created_event.status, EventStatus.PENDING)
        self.assertEqual(created_event.title, "Freshman Orientation")
        self.assertEqual(created_event.raw_content["media_type"], "photo")

    def test_post_event_by_admin_direct_publishes(self):
        payload = {
            "title": "Admin Direct Announcement",
            "club": self.club.id,
            "category": self.category_academic.id,
            "start_datetime": (self.now + timedelta(days=2)).isoformat(),
            "location": "Main Auditorium",
            "raw_content": {"media_type": "text", "file_ids": [], "caption": "Official announcement."}
        }
        response = self.client.post(
            '/api/events/',
            data=payload,
            format='json',
            HTTP_X_TELEGRAM_USER_ID=str(self.admin_telegram_id)
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_id = response.data['id']
        created_event = Event.objects.get(id=created_id)
        # Verify status is APPROVED directly
        self.assertEqual(created_event.status, EventStatus.APPROVED)
        self.assertIsNotNone(created_event.approved_at)
        self.assertEqual(created_event.approved_by, "API Superadmin")

    def test_post_event_by_unauthorized_user_denied(self):
        payload = {
            "title": "Unauthorized Event",
            "club": self.club.id,
            "category": self.category_academic.id,
            "start_datetime": (self.now + timedelta(days=2)).isoformat(),
            "location": "Room 101",
        }
        # Unregistered telegram ID
        response = self.client.post(
            '/api/events/',
            data=payload,
            format='json',
            HTTP_X_TELEGRAM_USER_ID="999888777"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_patch_event_status_as_admin(self):
        url = f'/api/events/{self.event_pending.id}/status/'
        payload = {
            "status": "approved",
            "channel_message_id": 8899
        }
        response = self.client.patch(
            url,
            data=payload,
            format='json',
            HTTP_X_TELEGRAM_USER_ID=str(self.admin_telegram_id)
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.event_pending.refresh_from_db()
        self.assertEqual(self.event_pending.status, EventStatus.APPROVED)
        self.assertEqual(self.event_pending.channel_message_id, 8899)
        self.assertEqual(self.event_pending.approved_by, "API Superadmin")
        self.assertIsNotNone(self.event_pending.approved_at)

    def test_patch_event_status_unauthorized(self):
        url = f'/api/events/{self.event_pending.id}/status/'
        payload = {"status": "approved"}
        # Without admin header
        response = self.client.patch(url, data=payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # With invalid admin header
        response = self.client.patch(
            url,
            data=payload,
            format='json',
            HTTP_X_TELEGRAM_USER_ID="1234567890123"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_patch_event_structured_fields_as_admin(self):
        url = f'/api/events/{self.event_today.id}/'
        payload = {
            "title": "Updated Football Semi-Finals",
            "location": "Updated Stadium Pitch 1"
        }
        response = self.client.patch(
            url,
            data=payload,
            format='json',
            HTTP_X_TELEGRAM_USER_ID=str(self.admin_telegram_id)
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.event_today.refresh_from_db()
        self.assertEqual(self.event_today.title, "Updated Football Semi-Finals")
        self.assertEqual(self.event_today.location, "Updated Stadium Pitch 1")

    def test_patch_event_structured_fields_unauthorized(self):
        url = f'/api/events/{self.event_today.id}/'
        payload = {"title": "Hacked Title"}
        response = self.client.patch(url, data=payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_clubs_list(self):
        response = self.client.get('/api/clubs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [c['name'] for c in response.data]
        self.assertIn("AASTU Developer Club", names)

    def test_create_club_as_admin(self):
        url = '/api/clubs/'
        payload = {
            "name": "AASTU Cybersecurity Club",
            "category_type": "Technology",
            "contact_info": "@aastusec",
        }
        response = self.client.post(
            url,
            data=payload,
            format='json',
            HTTP_X_TELEGRAM_USER_ID=str(self.admin_telegram_id),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "AASTU Cybersecurity Club")
        self.assertTrue(Club.objects.filter(name="AASTU Cybersecurity Club").exists())

    def test_create_club_unauthorized(self):
        url = '/api/clubs/'
        payload = {"name": "Unauthorized Club"}
        response = self.client.post(url, data=payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_add_officer_as_admin(self):
        url = f'/api/clubs/{self.club.id}/officers/'
        payload = {"telegram_id": 555666777}
        response = self.client.post(
            url,
            data=payload,
            format='json',
            HTTP_X_TELEGRAM_USER_ID=str(self.admin_telegram_id)
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.club.refresh_from_db()
        self.assertTrue(self.club.is_officer(555666777))

    def test_add_officer_unauthorized(self):
        url = f'/api/clubs/{self.club.id}/officers/'
        payload = {"telegram_id": 555666777}
        response = self.client.post(url, data=payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_officer_as_admin(self):
        self.club.verified_officers = [123456, 789012]
        self.club.save()

        url = f'/api/clubs/{self.club.id}/officers/'
        payload = {"telegram_id": 123456}
        response = self.client.delete(
            url,
            data=payload,
            format='json',
            HTTP_X_TELEGRAM_USER_ID=str(self.admin_telegram_id)
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.club.refresh_from_db()
        self.assertFalse(self.club.is_officer(123456))
        self.assertTrue(self.club.is_officer(789012))

    def test_get_categories_list(self):
        response = self.client.get('/api/categories/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [c['name'] for c in response.data]
        self.assertIn("Sports", names)
        self.assertIn("Academic", names)

    def test_admin_check_endpoint(self):
        # Admin check with valid admin telegram ID
        response = self.client.get('/api/admin-check/', HTTP_X_TELEGRAM_USER_ID=str(self.admin_telegram_id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data.get('is_admin'))

        # Admin check with non-admin telegram ID
        response = self.client.get('/api/admin-check/', HTTP_X_TELEGRAM_USER_ID="111222333")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(response.data.get('is_admin'))

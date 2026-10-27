from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from events.models import Category, Club, Event, Admin, EventStatus, PermissionLevel


class Command(BaseCommand):
    help = "Seed database with default categories, sample clubs, Telegram admins, and events across all statuses."

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing event/club/category/admin data before seeding',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write("Clearing existing data...")
            Event.objects.all().delete()
            Club.objects.all().delete()
            Category.objects.all().delete()
            Admin.objects.all().delete()

        now = timezone.now()

        # 1. Seed Categories
        categories_data = [
            ("Club Social", "Social gatherings, meetups, parties, and networking sessions."),
            ("Sports", "Tournaments, intramurals, fitness sessions, and outdoor activities."),
            ("Academic", "Lectures, seminars, research talks, and study sessions."),
            ("Entertainment", "Concerts, cultural nights, gaming, and performances."),
            ("Career/Workshop", "Skill-building bootcamps, resume reviews, hackathons, and career fairs."),
            ("Religious", "Fellowships, religious ceremonies, and faith-based community events."),
            ("Other", "Miscellaneous and interdisciplinary events."),
        ]

        categories = {}
        for name, description in categories_data:
            cat, created = Category.objects.get_or_create(
                name=name,
                defaults={'description': description}
            )
            categories[name] = cat
            status_text = "Created" if created else "Found"
            self.stdout.write(f"  Category: {name} ({status_text})")

        # 2. Seed Clubs
        clubs_data = [
            {
                "name": "AASTU Software Development Club",
                "category_type": "Technology",
                "verified_officers": [111222333, 444555666],
                "contact_info": "contact@aastucoding.org | TG: @aastu_devs",
            },
            {
                "name": "AASTU Robotics & AI Society",
                "category_type": "Engineering",
                "verified_officers": [777888999],
                "contact_info": "robotics@aastu.edu.et | TG: @aastu_robotics",
            },
            {
                "name": "AASTU Athletics & Sports Guild",
                "category_type": "Sports & Athletics",
                "verified_officers": [123456789, 987654321],
                "contact_info": "sports@aastu.edu.et | TG: @aastu_sports",
            },
        ]

        clubs = {}
        for cdata in clubs_data:
            club, created = Club.objects.get_or_create(
                name=cdata["name"],
                defaults={
                    "category_type": cdata["category_type"],
                    "verified_officers": cdata["verified_officers"],
                    "contact_info": cdata["contact_info"],
                }
            )
            clubs[cdata["name"]] = club
            status_text = "Created" if created else "Found"
            self.stdout.write(f"  Club: {club.name} ({status_text})")

        # 3. Seed Admins
        admins_data = [
            {
                "telegram_id": 100000001,
                "name": "Alex Superadmin",
                "permission_level": PermissionLevel.SUPERADMIN,
            },
            {
                "telegram_id": 100000002,
                "name": "Beth Moderating Admin",
                "permission_level": PermissionLevel.ADMIN,
            },
            {
                "telegram_id": 100000003,
                "name": "Charlie Moderator",
                "permission_level": PermissionLevel.MODERATOR,
            },
        ]

        for adata in admins_data:
            admin_obj, created = Admin.objects.get_or_create(
                telegram_id=adata["telegram_id"],
                defaults={
                    "name": adata["name"],
                    "permission_level": adata["permission_level"],
                    "is_active": True,
                }
            )
            status_text = "Created" if created else "Found"
            self.stdout.write(f"  Admin: {admin_obj.name} ID={admin_obj.telegram_id} ({status_text})")

        # 4. Seed Events across statuses (pending, approved, rejected, cancelled)
        sample_events = [
            {
                "title": "Annual AASTU Hackathon 2026 Opening Ceremony",
                "club": clubs["AASTU Software Development Club"],
                "category": categories["Career/Workshop"],
                "start_datetime": now + timedelta(hours=3),
                "end_datetime": now + timedelta(hours=8),
                "location": "ICT Center Block 508, Main Hall",
                "status": EventStatus.APPROVED,
                "channel_message_id": 1042,
                "approved_by": "Alex Superadmin",
                "approved_at": now - timedelta(days=1),
                "recurring": False,
                "raw_content": {
                    "media_type": "photo",
                    "file_ids": ["AgACAgIAAxkBAAICamX1234samplephoto"],
                    "caption": "🚀 Get ready for AASTU Hackathon 2026! 24 hours of non-stop coding, mentorship, and epic prizes. Doors open at 2 PM sharp!",
                },
            },
            {
                "title": "Autonomous Drone Demo & Hands-on ROS2 Workshop",
                "club": clubs["AASTU Robotics & AI Society"],
                "category": categories["Career/Workshop"],
                "start_datetime": now + timedelta(days=2, hours=4),
                "end_datetime": now + timedelta(days=2, hours=7),
                "location": "Engineering Lab 3 & Main Stadium",
                "status": EventStatus.APPROVED,
                "channel_message_id": 1043,
                "approved_by": "Beth Moderating Admin",
                "approved_at": now - timedelta(hours=6),
                "recurring": False,
                "raw_content": {
                    "media_type": "video",
                    "file_ids": ["BAACAgIAAxkBAAICbmY5678samplevideo"],
                    "caption": "🤖 Join us for our live Autonomous Drone flight showcase and hands-on ROS2 workshop. Refreshments provided!",
                },
            },
            {
                "title": "Inter-Department Football Tournament Finals",
                "club": clubs["AASTU Athletics & Sports Guild"],
                "category": categories["Sports"],
                "start_datetime": now + timedelta(days=4, hours=2),
                "end_datetime": now + timedelta(days=4, hours=5),
                "location": "AASTU Stadium",
                "status": EventStatus.PENDING,
                "channel_message_id": None,
                "approved_by": None,
                "approved_at": None,
                "recurring": False,
                "raw_content": {
                    "media_type": "photo",
                    "file_ids": ["AgACAgIAAxkBAAICcmZ9012samplephoto"],
                    "caption": "🏆 Finals are here! School of Applied Natural Sciences vs School of Electrical & Mechanical Engineering. Cheer for your team!",
                },
            },
            {
                "title": "Web3 & Distributed Systems Guest Lecture",
                "club": clubs["AASTU Software Development Club"],
                "category": categories["Academic"],
                "start_datetime": now + timedelta(days=5, hours=1),
                "end_datetime": now + timedelta(days=5, hours=3),
                "location": "Auditorium B",
                "status": EventStatus.PENDING,
                "channel_message_id": None,
                "approved_by": None,
                "approved_at": None,
                "recurring": False,
                "raw_content": {
                    "media_type": "document",
                    "file_ids": ["BQACAgIAAxkBAAICdmW3456sampledoc"],
                    "caption": "Guest lecture by alumni working on blockchain scalability and L2 protocols. Open to all students.",
                },
            },
            {
                "title": "Unofficial Weekend Camping Trip",
                "club": clubs["AASTU Software Development Club"],
                "category": categories["Club Social"],
                "start_datetime": now + timedelta(days=8),
                "end_datetime": now + timedelta(days=9),
                "location": "Lake Wonchi",
                "status": EventStatus.REJECTED,
                "channel_message_id": None,
                "approved_by": "Beth Moderating Admin",
                "approved_at": None,
                "recurring": False,
                "raw_content": {
                    "media_type": "text",
                    "file_ids": [],
                    "caption": "Road trip this weekend. Bring your own tent.",
                },
            },
            {
                "title": "Intramural Basketball League Match #4",
                "club": clubs["AASTU Athletics & Sports Guild"],
                "category": categories["Sports"],
                "start_datetime": now + timedelta(days=1, hours=6),
                "end_datetime": now + timedelta(days=1, hours=8),
                "location": "Campus Outdoor Basketball Courts",
                "status": EventStatus.CANCELLED,
                "channel_message_id": None,
                "approved_by": None,
                "approved_at": None,
                "recurring": False,
                "raw_content": {
                    "media_type": "photo",
                    "file_ids": ["AgACAgIAAxkBAAICemV7890samplephoto"],
                    "caption": "Postponed due to scheduled court maintenance.",
                },
            },
        ]

        for edata in sample_events:
            event, created = Event.objects.get_or_create(
                title=edata["title"],
                club=edata["club"],
                defaults=edata
            )
            status_text = "Created" if created else "Found"
            self.stdout.write(f"  Event: '{event.title}' [{event.status}] ({status_text})")

        self.stdout.write(self.style.SUCCESS("Database seeded successfully!"))

from django.core.management.base import BaseCommand
from events.models import Admin, PermissionLevel


class Command(BaseCommand):
    help = "Add or update a Telegram Admin in the database."

    def add_arguments(self, parser):
        parser.add_argument('telegram_id', type=int, help='Telegram User ID')
        parser.add_argument(
            '--level',
            type=str,
            default='superadmin',
            choices=['superadmin', 'admin', 'moderator'],
            help='Permission level (superadmin, admin, moderator)',
        )

    def handle(self, *args, **options):
        telegram_id = options['telegram_id']
        level = options['level']

        admin, created = Admin.objects.update_or_create(
            telegram_id=telegram_id,
            defaults={'permission_level': level, 'is_active': True},
        )

        action = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully {action} Admin (Telegram ID: {admin.telegram_id}, Level: {admin.permission_level})"
            )
        )

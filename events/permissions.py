from django.conf import settings
from rest_framework import permissions
from .models import Admin as TelegramAdmin, Club


def get_telegram_admin_from_request(request):
    """
    Extracts and validates Telegram admin identity from request.
    Strictly checks the 'X-Telegram-User-Id' header.
    Also allows authenticated Django superusers/staff.
    """
    if getattr(request, 'user', None) and request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
        return TelegramAdmin(
            telegram_id=0,
            name=request.user.username,
            permission_level="superadmin",
            is_active=True
        )

    telegram_id_raw = request.headers.get('X-Telegram-User-Id')

    if not telegram_id_raw:
        return None

    try:
        telegram_id = int(str(telegram_id_raw).strip())
        owner_raw = getattr(settings, 'TELEGRAM_OWNER_ID', '').strip()
        if owner_raw and str(telegram_id) == owner_raw:
            return TelegramAdmin(
                telegram_id=telegram_id,
                name="Bot Owner",
                permission_level="superadmin",
                is_active=True,
            )
        admin_obj = TelegramAdmin.objects.filter(telegram_id=telegram_id, is_active=True).first()
        return admin_obj
    except (ValueError, TypeError):
        return None


class IsTelegramAdminUser(permissions.BasePermission):
    """
    Permission check that grants access only to active Telegram Bot Admins
    (verified against the Admin model) or Django superusers.
    """
    message = "Admin access required. Provide a valid 'X-Telegram-User-Id' header for an active admin."

    def has_permission(self, request, view):
        admin_obj = get_telegram_admin_from_request(request)
        if admin_obj:
            request.telegram_admin = admin_obj
            return True
        return False


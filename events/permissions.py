from rest_framework import permissions
from .models import Admin as TelegramAdmin


def get_telegram_admin_from_request(request):
    """
    Extracts and validates Telegram admin identity from request.
    Checks headers: 'X-Telegram-User-Id', 'X-Telegram-Admin-Id', or query param 'telegram_admin_id'.
    Also allows authenticated Django superusers/staff.
    """
    if getattr(request, 'user', None) and request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
        return TelegramAdmin(
            telegram_id=0,
            name=request.user.username,
            permission_level="superadmin",
            is_active=True
        )

    telegram_id_raw = (
        request.headers.get('X-Telegram-User-Id')
        or request.headers.get('X-Telegram-Admin-Id')
        or request.query_params.get('telegram_admin_id')
    )

    if not telegram_id_raw:
        return None

    try:
        telegram_id = int(str(telegram_id_raw).strip())
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

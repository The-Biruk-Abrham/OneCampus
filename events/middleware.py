from django.conf import settings
from django.http import JsonResponse


class InternalApiSecretMiddleware:
    """
    Enforces that all requests to /api/ include the valid X-Hub-Internal-Secret header.
    Django's own /admin/ site and Django superuser/staff web sessions are exempt.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/api/'):
            # Allow authenticated Django staff/superusers browsing Browsable API
            if getattr(request, 'user', None) and request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
                return self.get_response(request)

            expected_secret = getattr(settings, 'INTERNAL_API_SECRET', '')
            provided_secret = request.headers.get('X-Hub-Internal-Secret', '')

            if not expected_secret or provided_secret != expected_secret:
                return JsonResponse(
                    {"detail": "Forbidden: Invalid or missing X-Hub-Internal-Secret header."},
                    status=403
                )

        return self.get_response(request)

from datetime import timedelta
from django.db.models import Q
from django.utils import timezone
from rest_framework import generics, status, views
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from .models import Category, Club, Event, EventStatus
from .permissions import IsTelegramAdminUser, get_telegram_admin_from_request
from .serializers import (
    CategorySerializer,
    ClubSerializer,
    OfficerManagementSerializer,
    EventSerializer,
    EventCreateSerializer,
    EventStatusUpdateSerializer,
    EventStructuredFieldsUpdateSerializer,
)


class EventListCreateView(generics.ListCreateAPIView):
    """
    GET /api/events/?range=today|week&category=<id>&status=<status>
    - range=today: returns events happening today
    - range=week: returns events happening in the upcoming 7 days
    - category=<id>: filters by category ID or name
    - status=<status>: default 'approved' for public queries; admins can query 'pending', 'rejected', etc.

    POST /api/events/
    - Submits a new event with status forced to 'pending'.
    """
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return EventCreateSerializer
        return EventSerializer

    def get_queryset(self):
        queryset = Event.objects.select_related('club', 'category').all()
        params = self.request.query_params

        # Filter by status: default to approved for public queries unless explicitly specified
        status_param = params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param.lower())
        else:
            # Check if an admin is requesting all statuses or if it's a general public query
            admin = get_telegram_admin_from_request(self.request)
            if not admin:
                queryset = queryset.filter(status=EventStatus.APPROVED)

        # Filter by date range (today, week) in local Addis Ababa timezone
        range_param = params.get('range', '').lower()
        local_now = timezone.localtime(timezone.now())
        start_of_today = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_today = start_of_today + timedelta(days=1)

        if range_param == 'today':
            queryset = queryset.filter(
                start_datetime__gte=start_of_today,
                start_datetime__lt=end_of_today,
            )
        elif range_param == 'week':
            end_of_week = start_of_today + timedelta(days=7)
            queryset = queryset.filter(
                start_datetime__gte=start_of_today,
                start_datetime__lt=end_of_week,
            )


        # Filter by category (by ID or exact/icontains name)
        category_param = params.get('category')
        if category_param:
            if category_param.isdigit():
                queryset = queryset.filter(
                    Q(category_id=int(category_param)) |
                    Q(custom_category__icontains=category_param)
                )
            else:
                queryset = queryset.filter(
                    Q(category__name__iexact=category_param) |
                    Q(custom_category__iexact=category_param)
                )

        # Filter by club
        club_param = params.get('club')
        if club_param:
            if club_param.isdigit():
                queryset = queryset.filter(
                    Q(club_id=int(club_param)) |
                    Q(custom_club__icontains=club_param)
                )
            else:
                queryset = queryset.filter(
                    Q(club__name__icontains=club_param) |
                    Q(custom_club__icontains=club_param)
                )

        return queryset.order_by('start_datetime')


class EventDetailUpdateView(generics.RetrieveUpdateAPIView):
    """
    GET /api/events/{id}/
    - Retrieve details of an event.

    PATCH /api/events/{id}/
    - Admin-only endpoint to edit structured fields of an event.
    """
    queryset = Event.objects.select_related('club', 'category').all()

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return EventStructuredFieldsUpdateSerializer
        return EventSerializer

    def get_permissions(self):
        if self.request.method in ['PUT', 'PATCH', 'DELETE']:
            return [IsTelegramAdminUser()]
        return [AllowAny()]


class EventStatusUpdateView(views.APIView):
    """
    PATCH /api/events/{id}/status/
    - Admin-only endpoint to transition event status (approved, rejected, cancelled).
    - Optional channel_message_id when approving.
    """
    permission_classes = [IsTelegramAdminUser]

    def patch(self, request, pk):
        try:
            event = Event.objects.get(pk=pk)
        except Event.DoesNotExist:
            return Response({"detail": "Event not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = EventStatusUpdateSerializer(event, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            updated_event = serializer.save()
            return Response(EventSerializer(updated_event).data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ClubListView(generics.ListCreateAPIView):
    """
    GET /api/clubs/
    - List all registered clubs and organizations.

    POST /api/clubs/
    - Admin/Owner endpoint to register a new club.
    """
    queryset = Club.objects.all().order_by('name')
    serializer_class = ClubSerializer

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsTelegramAdminUser()]
        return [AllowAny()]



class ClubDetailView(generics.RetrieveAPIView):
    """
    GET /api/clubs/{id}/
    - Retrieve club details.
    """
    queryset = Club.objects.all()
    serializer_class = ClubSerializer
    permission_classes = [AllowAny]


class ClubOfficersView(views.APIView):
    """
    POST /api/clubs/{id}/officers/
    - Admin-only endpoint to add a verified Telegram officer to a club.

    DELETE /api/clubs/{id}/officers/
    - Admin-only endpoint to remove a verified Telegram officer from a club.
    """
    permission_classes = [IsTelegramAdminUser]

    def post(self, request, pk):
        try:
            club = Club.objects.get(pk=pk)
        except Club.DoesNotExist:
            return Response({"detail": "Club not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = OfficerManagementSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        officer_id = serializer.validated_data['telegram_id']
        current_officers = list(club.verified_officers or [])

        # Avoid duplicates
        if officer_id not in current_officers and str(officer_id) not in [str(o) for o in current_officers]:
            current_officers.append(officer_id)
            club.verified_officers = current_officers
            club.save(update_fields=['verified_officers', 'updated_at'])

        return Response(ClubSerializer(club).data, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        try:
            club = Club.objects.get(pk=pk)
        except Club.DoesNotExist:
            return Response({"detail": "Club not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = OfficerManagementSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        officer_id = serializer.validated_data['telegram_id']
        current_officers = [
            o for o in (club.verified_officers or [])
            if str(o) != str(officer_id)
        ]
        club.verified_officers = current_officers
        club.save(update_fields=['verified_officers', 'updated_at'])

        return Response(ClubSerializer(club).data, status=status.HTTP_200_OK)


class AdminCheckView(views.APIView):
    """
    GET /api/admin-check/
    - Checks if the user supplied via X-Telegram-User-Id header is an active admin or owner.
    """
    def get(self, request):
        admin = get_telegram_admin_from_request(request)
        if admin:
            return Response({
                "is_admin": True,
                "name": admin.name,
                "permission_level": admin.permission_level,
            }, status=status.HTTP_200_OK)
        return Response({
            "is_admin": False,
        }, status=status.HTTP_403_FORBIDDEN)


class CategoryListView(generics.ListAPIView):
    """
    GET /api/categories/
    - List all event categories.
    """
    queryset = Category.objects.all().order_by('name')
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]

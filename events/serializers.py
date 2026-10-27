from rest_framework import serializers
from django.utils import timezone
from .models import Category, Club, Event, EventStatus, Admin as TelegramAdmin


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'description', 'created_at']


class ClubSerializer(serializers.ModelSerializer):
    class Meta:
        model = Club
        fields = [
            'id',
            'name',
            'category_type',
            'verified_officers',
            'contact_info',
            'created_at',
            'updated_at',
        ]


class OfficerManagementSerializer(serializers.Serializer):
    telegram_id = serializers.IntegerField(
        required=True,
        help_text="Telegram User ID (numeric integer) to add/remove as a verified club officer."
    )


class EventSerializer(serializers.ModelSerializer):
    """
    Detailed read representation of an event.
    Distinguishes raw forwarded media/caption from queryable structured fields.
    """
    club_name = serializers.SerializerMethodField()
    category_name = serializers.SerializerMethodField()
    is_custom_club = serializers.SerializerMethodField()
    is_custom_category = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Event
        fields = [
            'id',
            'title',
            'club',
            'club_name',
            'custom_club',
            'is_custom_club',
            'category',
            'category_name',
            'custom_category',
            'is_custom_category',
            'start_datetime',
            'end_datetime',
            'location',
            'raw_content',
            'status',
            'status_display',
            'recurring',
            'recurrence_pattern',
            'channel_message_id',
            'submitted_at',
            'approved_at',
            'approved_by',
        ]

    def get_club_name(self, obj):
        if obj.club:
            return obj.club.name
        return obj.custom_club or 'Other / Unlisted Club'

    def get_category_name(self, obj):
        if obj.category:
            return obj.category.name
        return obj.custom_category or 'Other'

    def get_is_custom_club(self, obj):
        return bool(not obj.club and obj.custom_club)

    def get_is_custom_category(self, obj):
        return bool(not obj.category and obj.custom_category)


class EventCreateSerializer(serializers.ModelSerializer):
    """
    Submission serializer for organizers.
    Enforces submitter authorization (verified officer, admin, or owner).
    Direct publish (status=approved) for owner and admins; status=pending for officers.
    """
    raw_content = serializers.JSONField(required=False, default=dict)
    club = serializers.PrimaryKeyRelatedField(queryset=Club.objects.all(), required=False, allow_null=True)
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), required=False, allow_null=True)
    custom_club = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    custom_category = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')

    class Meta:
        model = Event
        fields = [
            'id',
            'title',
            'club',
            'custom_club',
            'category',
            'custom_category',
            'start_datetime',
            'end_datetime',
            'location',
            'raw_content',
            'recurring',
            'recurrence_pattern',
            'submitted_at',
            'status',
            'approved_at',
            'approved_by',
        ]
        read_only_fields = ['id', 'submitted_at', 'status', 'approved_at', 'approved_by']

    def validate(self, attrs):
        from rest_framework.exceptions import PermissionDenied
        from .permissions import get_telegram_admin_from_request

        request = self.context.get('request')
        submitter_id_raw = request.headers.get('X-Telegram-User-Id') if request else None

        if not submitter_id_raw:
            raise PermissionDenied("Submitter Telegram ID is required via 'X-Telegram-User-Id' header.")

        try:
            submitter_id = int(str(submitter_id_raw).strip())
        except (ValueError, TypeError):
            raise PermissionDenied("Invalid 'X-Telegram-User-Id' header value.")

        admin_obj = get_telegram_admin_from_request(request) if request else None
        is_admin_or_owner = bool(admin_obj)

        club = attrs.get('club')
        custom_club = attrs.get('custom_club')

        if not club and not custom_club:
            attrs['custom_club'] = 'Independent / Student Initiative'
            custom_club = attrs['custom_club']

        # If not admin or owner, verify that the submitter is an authorized officer for the specified club
        if not is_admin_or_owner:
            if not club:
                raise PermissionDenied("Only admins or owner can submit events for custom unlisted clubs.")
            if not club.is_officer(submitter_id):
                raise PermissionDenied(f"Telegram ID {submitter_id} is not an authorized verified officer for '{club.name}'.")

        return attrs

    def create(self, validated_data):
        from .permissions import get_telegram_admin_from_request
        request = self.context.get('request')
        admin_obj = get_telegram_admin_from_request(request) if request else None

        if admin_obj:
            # Direct publish for owner and admins
            validated_data['status'] = EventStatus.APPROVED
            validated_data['approved_at'] = timezone.now()
            validated_data['approved_by'] = admin_obj.name or str(admin_obj.telegram_id)
        else:
            validated_data['status'] = EventStatus.PENDING

        return super().create(validated_data)



class EventStatusUpdateSerializer(serializers.ModelSerializer):
    """
    Admin-only status transition serializer (approve, reject, cancel).
    """
    status = serializers.ChoiceField(
        choices=[EventStatus.APPROVED, EventStatus.REJECTED, EventStatus.CANCELLED],
        required=True
    )
    channel_message_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="Telegram public channel message ID (set upon publication)"
    )

    class Meta:
        model = Event
        fields = ['status', 'channel_message_id']

    def update(self, instance, validated_data):
        request = self.context.get('request')
        new_status = validated_data.get('status')
        channel_msg_id = validated_data.get('channel_message_id', instance.channel_message_id)

        approver_identifier = "admin"
        if request and getattr(request, 'telegram_admin', None):
            approver = request.telegram_admin
            approver_identifier = approver.name or str(approver.telegram_id)
        elif request and hasattr(request, 'user') and request.user and request.user.is_authenticated:
            approver_identifier = request.user.username

        if new_status == EventStatus.APPROVED:
            instance.status = EventStatus.APPROVED
            instance.approved_at = timezone.now()
            instance.approved_by = approver_identifier
            if channel_msg_id is not None:
                instance.channel_message_id = channel_msg_id
            instance.save(update_fields=['status', 'approved_at', 'approved_by', 'channel_message_id'])
        elif new_status == EventStatus.REJECTED:
            instance.status = EventStatus.REJECTED
            instance.approved_by = approver_identifier
            instance.save(update_fields=['status', 'approved_by'])
        elif new_status == EventStatus.CANCELLED:
            instance.status = EventStatus.CANCELLED
            instance.save(update_fields=['status'])

        return instance


class EventStructuredFieldsUpdateSerializer(serializers.ModelSerializer):
    """
    Admin-only serializer for editing structured queryable fields of an event.
    """
    club = serializers.PrimaryKeyRelatedField(queryset=Club.objects.all(), required=False, allow_null=True)
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), required=False, allow_null=True)
    custom_club = serializers.CharField(max_length=100, required=False, allow_blank=True)
    custom_category = serializers.CharField(max_length=100, required=False, allow_blank=True)

    class Meta:
        model = Event
        fields = [
            'id',
            'title',
            'club',
            'custom_club',
            'category',
            'custom_category',
            'start_datetime',
            'end_datetime',
            'location',
            'recurring',
            'recurrence_pattern',
        ]

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
    Enforces initial status=pending and stores raw_content as-is.
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
        ]
        read_only_fields = ['id', 'submitted_at', 'status']

    def validate(self, attrs):
        club = attrs.get('club')
        custom_club = attrs.get('custom_club')
        if not club and not custom_club:
            # Default to custom club if neither provided
            attrs['custom_club'] = 'Independent / Student Initiative'
        return attrs

    def create(self, validated_data):
        # Force initial status to pending for submissions
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

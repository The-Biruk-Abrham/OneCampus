from django.db import models
from django.utils import timezone


class Category(models.Model):
    """
    Event Category (e.g. Club Social, Sports, Academic, Entertainment, Career/Workshop, Religious, Other).
    """
    name = models.CharField(max_length=100, unique=True, help_text="Category name")
    description = models.TextField(blank=True, help_text="Optional description of the category")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ['name']

    def __str__(self):
        return self.name


class Club(models.Model):
    """
    University Student Club or Organization.
    """
    name = models.CharField(max_length=200, unique=True, help_text="Official club name")
    category_type = models.CharField(max_length=100, blank=True, help_text="Club genre/type e.g. Academic, Tech, Cultural, Sports")
    verified_officers = models.JSONField(
        default=list,
        blank=True,
        help_text="List of Telegram user IDs (integers/strings) authorized to submit events for this club",
    )
    contact_info = models.TextField(blank=True, help_text="Contact email, phone, or Telegram handle")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Club"
        verbose_name_plural = "Clubs"
        ordering = ['name']

    def __str__(self):
        return self.name

    def is_officer(self, telegram_id: int | str) -> bool:
        """Check if a given telegram ID is among verified officers."""
        str_id = str(telegram_id)
        return any(str(officer_id) == str_id for officer_id in self.verified_officers)


class EventStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    APPROVED = 'approved', 'Approved'
    REJECTED = 'rejected', 'Rejected'
    CANCELLED = 'cancelled', 'Cancelled'


class Event(models.Model):
    """
    University Event.
    Distinguishes raw forwarded content (media file_ids + original caption)
    from queryable structured fields (start_datetime, end_datetime, location, category, club, title).
    """
    # Structured Fields (queryable)
    club = models.ForeignKey(
        Club,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='events',
        help_text="Host club or organization (optional if custom_club is specified)",
    )
    custom_club = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text="Custom unverified host club name entered via Other",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='events',
        help_text="Event classification category",
    )
    custom_category = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text="Custom category name entered via Other",
    )
    title = models.CharField(max_length=255, help_text="Short event title")
    start_datetime = models.DateTimeField(
        db_index=True,
        help_text="Start date and time (indexed for fast range queries like /today, /week)",
    )
    end_datetime = models.DateTimeField(
        null=True,
        blank=True,
        help_text="End date and time (nullable)",
    )
    location = models.CharField(max_length=255, help_text="Event venue or location description")

    # Raw Content (forwarded media file_id(s) + original caption as-is)
    raw_content = models.JSONField(
        default=dict,
        blank=True,
        help_text="Stores forwarded media file_id(s), media types, and original unmodified caption text",
    )

    # Moderation & Publication Status
    status = models.CharField(
        max_length=20,
        choices=EventStatus.choices,
        default=EventStatus.PENDING,
        db_index=True,
        help_text="Approval status (pending, approved, rejected, cancelled)",
    )
    recurring = models.BooleanField(default=False, help_text="Whether this event recurs regularly")
    recurrence_pattern = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Recurrence schedule description (e.g. 'Every Wednesday 5 PM')",
    )
    channel_message_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Telegram channel message ID once published (used for in-place message updates)",
    )

    # Submission & Audit Timestamps
    submitted_at = models.DateTimeField(auto_now_add=True, help_text="Timestamp when organizer submitted")
    approved_at = models.DateTimeField(null=True, blank=True, help_text="Timestamp when approved by an admin")
    approved_by = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Telegram ID or username of the approving admin",
    )

    class Meta:
        verbose_name = "Event"
        verbose_name_plural = "Events"
        ordering = ['start_datetime']
        indexes = [
            models.Index(fields=['status', 'start_datetime'], name='event_status_start_idx'),
        ]

    def __str__(self):
        start_str = self.start_datetime.strftime('%Y-%m-%d %H:%M') if self.start_datetime else 'No Date'
        return f"{self.title} ({self.get_status_display()}) - {start_str}"

    def approve(self, approver_identifier: str = None, channel_msg_id: int = None):
        """Helper to mark event as approved."""
        self.status = EventStatus.APPROVED
        self.approved_at = timezone.now()
        update_fields = ['status', 'approved_at']
        if approver_identifier:
            self.approved_by = str(approver_identifier)
            update_fields.append('approved_by')
        if channel_msg_id is not None:
            self.channel_message_id = channel_msg_id
            update_fields.append('channel_message_id')
        self.save(update_fields=update_fields)

    def reject(self, approver_identifier: str = None):
        """Helper to mark event as rejected."""
        self.status = EventStatus.REJECTED
        update_fields = ['status']
        if approver_identifier:
            self.approved_by = str(approver_identifier)
            update_fields.append('approved_by')
        self.save(update_fields=update_fields)

    def cancel(self):
        """Helper to mark event as cancelled."""
        self.status = EventStatus.CANCELLED
        self.save(update_fields=['status'])


class PermissionLevel(models.TextChoices):
    SUPERADMIN = 'superadmin', 'Superadmin'
    ADMIN = 'admin', 'Admin'
    MODERATOR = 'moderator', 'Moderator'


class Admin(models.Model):
    """
    Telegram Bot Admin / Approver with permission levels.
    """
    telegram_id = models.BigIntegerField(
        unique=True,
        db_index=True,
        help_text="Telegram user ID of the admin",
    )
    name = models.CharField(max_length=150, blank=True, help_text="Admin display name or handle")
    permission_level = models.CharField(
        max_length=50,
        choices=PermissionLevel.choices,
        default=PermissionLevel.MODERATOR,
        help_text="Role and permission level for moderation and admin actions",
    )
    is_active = models.BooleanField(default=True, help_text="Whether this admin account is currently active")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Admin"
        verbose_name_plural = "Admins"
        ordering = ['telegram_id']

    def __str__(self):
        return f"{self.name or self.telegram_id} ({self.get_permission_level_display()})"

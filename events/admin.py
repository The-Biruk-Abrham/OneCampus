from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from .models import Category, Club, Event, Admin as TelegramAdmin, EventStatus


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'events_count', 'created_at')
    search_fields = ('name', 'description')
    ordering = ('name',)

    def events_count(self, obj):
        return obj.events.count()
    events_count.short_description = 'Total Events'


@admin.register(Club)
class ClubAdmin(admin.ModelAdmin):
    list_display = ('name', 'category_type', 'officers_count', 'created_at')
    search_fields = ('name', 'category_type', 'contact_info')
    list_filter = ('category_type', 'created_at')
    ordering = ('name',)

    def officers_count(self, obj):
        count = len(obj.verified_officers) if isinstance(obj.verified_officers, list) else 0
        return f"{count} officer(s)"
    officers_count.short_description = 'Verified Officers'


@admin.action(description="Approve selected events")
def approve_selected_events(modeladmin, request, queryset):
    updated = queryset.update(
        status=EventStatus.APPROVED,
        approved_at=timezone.now(),
        approved_by=request.user.username or "django_admin"
    )
    modeladmin.message_user(request, f"{updated} event(s) successfully marked as Approved.")


@admin.action(description="Reject selected events")
def reject_selected_events(modeladmin, request, queryset):
    updated = queryset.update(
        status=EventStatus.REJECTED,
        approved_by=request.user.username or "django_admin"
    )
    modeladmin.message_user(request, f"{updated} event(s) marked as Rejected.")


@admin.action(description="Cancel selected events")
def cancel_selected_events(modeladmin, request, queryset):
    updated = queryset.update(status=EventStatus.CANCELLED)
    modeladmin.message_user(request, f"{updated} event(s) marked as Cancelled.")


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'club',
        'category',
        'status_badge',
        'start_datetime',
        'location',
        'channel_message_id',
        'submitted_at',
    )
    list_filter = (
        'status',
        'category',
        'club',
        'recurring',
        'start_datetime',
        'submitted_at',
    )
    search_fields = ('title', 'location', 'club__name', 'category__name', 'approved_by')
    date_hierarchy = 'start_datetime'
    readonly_fields = ('submitted_at', 'approved_at')
    actions = [approve_selected_events, reject_selected_events, cancel_selected_events]

    fieldsets = (
        ('Structured Fields (Queryable)', {
            'fields': (
                'title',
                'club',
                'category',
                'start_datetime',
                'end_datetime',
                'location',
            ),
            'description': 'Core structured details used for search, filtering, and calendar queries.',
        }),
        ('Raw Content (Forwarded Media & Caption)', {
            'fields': ('raw_content',),
            'description': 'Stores original forwarded media file_id(s) and original caption as-is.',
        }),
        ('Moderation & Channel Publication', {
            'fields': (
                'status',
                'channel_message_id',
                'approved_by',
                'approved_at',
                'submitted_at',
            ),
            'description': 'Approval queue state and Telegram broadcast metadata.',
        }),
        ('Recurrence Settings', {
            'classes': ('collapse',),
            'fields': (
                'recurring',
                'recurrence_pattern',
            ),
        }),
    )

    def status_badge(self, obj):
        color_map = {
            EventStatus.PENDING: '#f39c12',
            EventStatus.APPROVED: '#27ae60',
            EventStatus.REJECTED: '#c0392b',
            EventStatus.CANCELLED: '#7f8c8d',
        }
        color = color_map.get(obj.status, '#333')
        return format_html(
            '<span style="background-color: {}; color: #fff; padding: 3px 8px; border-radius: 4px; font-weight: bold; text-transform: uppercase; font-size: 11px;">{}</span>',
            color,
            obj.get_status_display(),
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'


@admin.register(TelegramAdmin)
class AdminAdmin(admin.ModelAdmin):
    list_display = ('telegram_id', 'name', 'permission_level', 'is_active', 'created_at')
    list_filter = ('permission_level', 'is_active', 'created_at')
    search_fields = ('telegram_id', 'name')
    ordering = ('-created_at',)

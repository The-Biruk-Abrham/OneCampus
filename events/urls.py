from django.urls import path, re_path
from .views import (
    EventListCreateView,
    EventDetailUpdateView,
    EventStatusUpdateView,
    ClubListView,
    ClubDetailView,
    ClubOfficersView,
    CategoryListView,
    AdminCheckView,
)

urlpatterns = [
    # Events
    path('events/', EventListCreateView.as_view(), name='event-list-create'),
    re_path(r'^events/(?P<pk>\d+)/?$', EventDetailUpdateView.as_view(), name='event-detail-update'),
    re_path(r'^events/(?P<pk>\d+)/status/?$', EventStatusUpdateView.as_view(), name='event-status-update'),

    # Clubs
    path('clubs/', ClubListView.as_view(), name='club-list'),
    re_path(r'^clubs/(?P<pk>\d+)/?$', ClubDetailView.as_view(), name='club-detail'),
    re_path(r'^clubs/(?P<pk>\d+)/officers/?$', ClubOfficersView.as_view(), name='club-officers'),

    # Categories
    path('categories/', CategoryListView.as_view(), name='category-list'),

    # Admin verification
    path('admin-check/', AdminCheckView.as_view(), name='admin-check'),
]

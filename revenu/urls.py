from django.urls import path

from .views import (
    RevenueListCreateView,
    RevenueDetailView,
    BulkDeleteRevenueView,
    RevenueAttachmentDetailView,
    RevenueAttachmentListCreateView,
)

app_name = "revenu"

urlpatterns = [
    path("", RevenueListCreateView.as_view(), name="revenue-list-create"),
    path("bulk_delete/", BulkDeleteRevenueView.as_view(), name="revenue-bulk-delete"),
    path(
        "<int:pk>/attachments/",
        RevenueAttachmentListCreateView.as_view(),
        name="revenue-attachment-list-create",
    ),
    path(
        "attachments/<int:pk>/",
        RevenueAttachmentDetailView.as_view(),
        name="revenue-attachment-detail",
    ),
    path("<int:pk>/", RevenueDetailView.as_view(), name="revenue-detail"),
]

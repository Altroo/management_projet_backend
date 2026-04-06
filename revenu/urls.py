from django.urls import path

from .views import (
    RevenueListCreateView,
    RevenueDetailView,
    BulkDeleteRevenueView,
)

app_name = "revenu"

urlpatterns = [
    path("", RevenueListCreateView.as_view(), name="revenue-list-create"),
    path("bulk_delete/", BulkDeleteRevenueView.as_view(), name="revenue-bulk-delete"),
    path("<int:pk>/", RevenueDetailView.as_view(), name="revenue-detail"),
]

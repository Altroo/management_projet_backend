from django.urls import path

from .views import (
    ExpenseListCreateView,
    ExpenseDetailView,
    BulkDeleteExpenseView,
    ExpenseAttachmentDetailView,
    ExpenseAttachmentListCreateView,
)

app_name = "depense"

urlpatterns = [
    path("", ExpenseListCreateView.as_view(), name="expense-list-create"),
    path("bulk_delete/", BulkDeleteExpenseView.as_view(), name="expense-bulk-delete"),
    path(
        "<int:pk>/attachments/",
        ExpenseAttachmentListCreateView.as_view(),
        name="expense-attachment-list-create",
    ),
    path(
        "attachments/<int:pk>/",
        ExpenseAttachmentDetailView.as_view(),
        name="expense-attachment-detail",
    ),
    path("<int:pk>/", ExpenseDetailView.as_view(), name="expense-detail"),
]

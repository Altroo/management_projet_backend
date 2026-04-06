from django.urls import path

from .views import (
    ExpenseListCreateView,
    ExpenseDetailView,
    BulkDeleteExpenseView,
)

app_name = "depense"

urlpatterns = [
    path("", ExpenseListCreateView.as_view(), name="expense-list-create"),
    path("bulk_delete/", BulkDeleteExpenseView.as_view(), name="expense-bulk-delete"),
    path("<int:pk>/", ExpenseDetailView.as_view(), name="expense-detail"),
]

from django.urls import path

from .views import (
    QuoteListCreateView,
    QuoteDetailView,
    BulkDeleteQuoteView,
    QuoteAttachmentDetailView,
    QuoteAttachmentListCreateView,
)

app_name = "devis"

urlpatterns = [
    path("", QuoteListCreateView.as_view(), name="quote-list-create"),
    path("bulk_delete/", BulkDeleteQuoteView.as_view(), name="quote-bulk-delete"),
    path(
        "<int:pk>/attachments/",
        QuoteAttachmentListCreateView.as_view(),
        name="quote-attachment-list-create",
    ),
    path(
        "attachments/<int:pk>/",
        QuoteAttachmentDetailView.as_view(),
        name="quote-attachment-detail",
    ),
    path("<int:pk>/", QuoteDetailView.as_view(), name="quote-detail"),
]

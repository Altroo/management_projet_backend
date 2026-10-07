from django.urls import path

from .views import AssistView, InternalAssistView, InternalTranslationView

app_name = "ai_assistant"

urlpatterns = [
    path(
        "internal/translate/",
        InternalTranslationView.as_view(),
        name="internal-translate",
    ),
    path("assist/", AssistView.as_view(), name="assist"),
    path("internal/assist/", InternalAssistView.as_view(), name="internal-assist"),
]

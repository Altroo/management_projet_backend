from django.urls import path

from .views import AssistView, InternalAssistView

app_name = "ai_assistant"

urlpatterns = [
    path("assist/", AssistView.as_view(), name="assist"),
    path("internal/assist/", InternalAssistView.as_view(), name="internal-assist"),
]

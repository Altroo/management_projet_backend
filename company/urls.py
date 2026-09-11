from django.urls import path

from .views import CompanyProfileView

app_name = "company"

urlpatterns = [
    path("profile/", CompanyProfileView.as_view(), name="profile"),
]

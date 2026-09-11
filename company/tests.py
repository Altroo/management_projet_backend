from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from account.models import CustomUser
from .models import CompanyProfile

pytestmark = pytest.mark.django_db


def authenticated_client(*, is_staff):
    user = CustomUser.objects.create_user(
        email=f"company-{is_staff}@test.com",
        password="securepass123",
        is_staff=is_staff,
    )
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return client


def png_file():
    content = BytesIO()
    Image.new("RGB", (80, 40), color="blue").save(content, format="PNG")
    return SimpleUploadedFile("logo.png", content.getvalue(), content_type="image/png")


class TestCompanyProfileView:
    def setup_method(self):
        self.url = reverse("company:profile")

    def test_staff_can_get_seeded_singleton(self):
        response = authenticated_client(is_staff=True).get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["raison_sociale"] == "E.B.H Gestion Projet"
        assert CompanyProfile.objects.count() == 1

    def test_regular_user_cannot_read_profile_settings(self):
        response = authenticated_client(is_staff=False).get(self.url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_staff_can_update_identity_and_remove_logo(self):
        client = authenticated_client(is_staff=True)
        update = client.patch(
            self.url,
            {
                "raison_sociale": "Société Test",
                "ICE": "001122334455667",
                "numero_du_compte": "000111222333444",
                "logo": png_file(),
                "logo_cropped": png_file(),
            },
            format="multipart",
        )
        assert update.status_code == status.HTTP_200_OK
        assert update.data["logo_url"]
        assert update.data["logo_cropped_url"]
        assert update.data["numero_du_compte"] == "000111222333444"

        remove = client.patch(self.url, {"remove_logo": True}, format="json")
        assert remove.status_code == status.HTTP_200_OK
        assert remove.data["logo_url"] is None
        assert remove.data["logo_cropped_url"] is None
        assert CompanyProfile.objects.get().raison_sociale == "Société Test"

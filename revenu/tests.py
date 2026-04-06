from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from account.models import CustomUser
from project.models import Project
from revenu.models import Revenue

pytestmark = pytest.mark.django_db


# ── Helpers ───────────────────────────────────────────────────────────────────


def make_staff_user(email="staff@test.com", password="securepass123"):
    """Staff user with all permissions."""
    user = CustomUser.objects.create_user(
        email=email,
        password=password,
        is_staff=True,
        can_create=True,
        can_edit=True,
        can_delete=True,
        can_view=True,
    )
    token = str(AccessToken.for_user(user))
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return user, client


def make_readonly_user(email="readonly@test.com", password="securepass123"):
    """Read-only user — no write permissions."""
    user = CustomUser.objects.create_user(
        email=email,
        password=password,
        is_staff=False,
        can_create=False,
        can_edit=False,
        can_delete=False,
        can_view=True,
    )
    token = str(AccessToken.for_user(user))
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return user, client


def make_project(created_by=None, **kwargs):
    defaults = {
        "nom": "Projet Test",
        "budget_total": "50000.00",
        "date_debut": date(2025, 1, 1),
        "date_fin": date(2025, 12, 31),
        "status": "En cours",
        "chef_de_projet": "Jean Dupont",
        "nom_client": "Client A",
    }
    defaults.update(kwargs)
    return Project.objects.create(created_by_user=created_by, **defaults)


def make_revenue(project, created_by=None, **kwargs):
    defaults = {
        "date": date(2025, 6, 15),
        "description": "Paiement client",
        "montant": "10000.00",
    }
    defaults.update(kwargs)
    return Revenue.objects.create(
        project=project, created_by_user=created_by, **defaults
    )


# ── Model Tests ───────────────────────────────────────────────────────────────


class TestRevenueModel:
    def test_str(self):
        proj = make_project(nom="P1")
        r = make_revenue(proj, description="Avance")
        assert "Avance" in str(r)


# ── Revenue List/Create ──────────────────────────────────────────────────────


class TestRevenueListCreateView:
    def setup_method(self):
        self.url = reverse("revenu:revenue-list-create")
        self.staff_user, self.staff_client = make_staff_user()
        self.readonly_user, self.readonly_client = make_readonly_user()
        self.anon_client = APIClient()
        self.project = make_project(created_by=self.staff_user)

    def test_list_returns_200(self):
        make_revenue(self.project, created_by=self.staff_user)
        response = self.staff_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_unauthenticated_returns_401(self):
        response = self.anon_client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_returns_201(self):
        payload = {
            "project": self.project.pk,
            "date": "2025-07-01",
            "description": "Nouveau paiement",
            "montant": "15000.00",
        }
        response = self.staff_client.post(self.url, payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["description"] == "Nouveau paiement"

    def test_create_without_permission_returns_403(self):
        payload = {
            "project": self.project.pk,
            "date": "2025-07-01",
            "description": "Blocked",
            "montant": "1000.00",
        }
        response = self.readonly_client.post(self.url, payload, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_missing_required_returns_400(self):
        payload = {"description": "Missing project and amount"}
        response = self.staff_client.post(self.url, payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_filter_by_project(self):
        p2 = make_project(nom="P2", created_by=self.staff_user)
        make_revenue(self.project, created_by=self.staff_user, description="R1")
        make_revenue(p2, created_by=self.staff_user, description="R2")
        response = self.staff_client.get(
            self.url, {"project": self.project.pk}
        )
        assert response.status_code == status.HTTP_200_OK
        for item in response.data:
            assert item["project"] == self.project.pk

    def test_filter_by_search(self):
        make_revenue(
            self.project, created_by=self.staff_user, description="Avance client"
        )
        make_revenue(
            self.project, created_by=self.staff_user, description="Solde final"
        )
        response = self.staff_client.get(self.url, {"search": "Avance"})
        assert response.status_code == status.HTTP_200_OK
        assert all("Avance" in r["description"] for r in response.data)


# ── Revenue Detail/Edit/Delete ────────────────────────────────────────────────


class TestRevenueDetailView:
    def setup_method(self):
        self.staff_user, self.staff_client = make_staff_user()
        self.readonly_user, self.readonly_client = make_readonly_user()
        self.anon_client = APIClient()
        self.project = make_project(created_by=self.staff_user)
        self.revenue = make_revenue(self.project, created_by=self.staff_user)
        self.url = reverse(
            "revenu:revenue-detail", kwargs={"pk": self.revenue.pk}
        )

    def test_get_returns_200(self):
        response = self.staff_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == self.revenue.pk

    def test_get_not_found_returns_404(self):
        url = reverse("revenu:revenue-detail", kwargs={"pk": 99999})
        response = self.staff_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_unauthenticated_returns_401(self):
        response = self.anon_client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_put_updates_revenue(self):
        payload = {
            "project": self.project.pk,
            "date": "2025-08-01",
            "description": "Updated Revenue",
            "montant": "20000.00",
        }
        response = self.staff_client.put(self.url, payload, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["description"] == "Updated Revenue"

    def test_put_without_permission_returns_403(self):
        payload = {
            "project": self.project.pk,
            "date": "2025-08-01",
            "description": "Nope",
            "montant": "1000.00",
        }
        response = self.readonly_client.put(self.url, payload, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_returns_204(self):
        response = self.staff_client.delete(self.url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Revenue.objects.filter(pk=self.revenue.pk).exists()

    def test_delete_without_permission_returns_403(self):
        response = self.readonly_client.delete(self.url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_unauthenticated_returns_401(self):
        response = self.anon_client.delete(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ── Bulk Delete ───────────────────────────────────────────────────────────────


class TestBulkDeleteRevenueView:
    def setup_method(self):
        self.url = reverse("revenu:revenue-bulk-delete")
        self.staff_user, self.staff_client = make_staff_user()
        self.readonly_user, self.readonly_client = make_readonly_user()
        self.project = make_project(created_by=self.staff_user)

    def test_bulk_delete_returns_204(self):
        r1 = make_revenue(self.project, date=date(2025, 8, 1), description="BD1")
        r2 = make_revenue(self.project, date=date(2025, 8, 2), description="BD2")
        response = self.staff_client.delete(
            self.url, {"ids": [r1.pk, r2.pk]}, format="json"
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Revenue.objects.filter(pk__in=[r1.pk, r2.pk]).exists()

    def test_bulk_delete_without_permission_returns_403(self):
        r = make_revenue(self.project, description="BD3")
        response = self.readonly_client.delete(
            self.url, {"ids": [r.pk]}, format="json"
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_bulk_delete_empty_ids_returns_400(self):
        response = self.staff_client.delete(self.url, {"ids": []}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_bulk_delete_missing_ids_returns_400(self):
        response = self.staff_client.delete(self.url, {}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

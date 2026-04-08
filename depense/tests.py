from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from account.models import CustomUser
from depense.models import Expense
from project.models import Category, SubCategory, Project

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


def make_category(name="Matériaux"):
    return Category.objects.create(name=name)


def make_subcategory(name="Ciment", category=None):
    if category is None:
        category = make_category()
    return SubCategory.objects.create(name=name, category=category)


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


def make_expense(project, created_by=None, **kwargs):
    defaults = {
        "date": date(2025, 6, 15),
        "description": "Achat matériaux",
        "montant": "5000.00",
    }
    defaults.update(kwargs)
    return Expense.objects.create(
        project=project, created_by_user=created_by, **defaults
    )


# ── Model Tests ───────────────────────────────────────────────────────────────


class TestExpenseModel:
    def test_str(self):
        proj = make_project(nom="P1")
        e = make_expense(proj, description="Ciment")
        assert "Ciment" in str(e)


# ── Expense List/Create ──────────────────────────────────────────────────────


class TestExpenseListCreateView:
    def setup_method(self):
        self.url = reverse("depense:expense-list-create")
        self.staff_user, self.staff_client = make_staff_user()
        self.readonly_user, self.readonly_client = make_readonly_user()
        self.anon_client = APIClient()
        self.project = make_project(created_by=self.staff_user)

    def test_list_returns_200(self):
        make_expense(self.project, created_by=self.staff_user)
        response = self.staff_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_unauthenticated_returns_401(self):
        response = self.anon_client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_returns_201(self):
        cat = make_category(name="CatTest")
        payload = {
            "project": self.project.pk,
            "date": "2025-07-01",
            "category": cat.pk,
            "element": "Sable fin",
            "description": "Achat sable",
            "montant": "3000.00",
            "fournisseur": "Fournisseur X",
        }
        response = self.staff_client.post(self.url, payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["description"] == "Achat sable"

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
        payload = {"description": "Missing fields"}
        response = self.staff_client.post(self.url, payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_filter_by_project(self):
        p2 = make_project(nom="P2", created_by=self.staff_user)
        make_expense(self.project, created_by=self.staff_user, description="E1")
        make_expense(p2, created_by=self.staff_user, description="E2")
        response = self.staff_client.get(self.url, {"project": self.project.pk})
        assert response.status_code == status.HTTP_200_OK
        for item in response.data:
            assert item["project"] == self.project.pk

    def test_filter_by_category(self):
        cat = make_category(name="FilterCat")
        make_expense(
            self.project,
            created_by=self.staff_user,
            category=cat,
            description="With Cat",
        )
        make_expense(
            self.project,
            created_by=self.staff_user,
            description="No Cat",
        )
        response = self.staff_client.get(self.url, {"category": cat.pk})
        assert response.status_code == status.HTTP_200_OK
        for item in response.data:
            assert item["category"] == cat.pk

    def test_filter_by_search(self):
        make_expense(
            self.project, created_by=self.staff_user, description="Achat ciment"
        )
        make_expense(
            self.project, created_by=self.staff_user, description="Location grue"
        )
        response = self.staff_client.get(self.url, {"search": "ciment"})
        assert response.status_code == status.HTTP_200_OK
        assert all("ciment" in r["description"].lower() for r in response.data)

    def test_filter_by_fournisseur(self):
        make_expense(
            self.project,
            created_by=self.staff_user,
            fournisseur="ABC Corp",
            description="F1",
        )
        make_expense(
            self.project,
            created_by=self.staff_user,
            fournisseur="XYZ Ltd",
            description="F2",
        )
        response = self.staff_client.get(self.url, {"fournisseur": "ABC Corp"})
        assert response.status_code == status.HTTP_200_OK
        for item in response.data:
            assert item["fournisseur"] == "ABC Corp"


# ── Expense Detail/Edit/Delete ────────────────────────────────────────────────


class TestExpenseDetailView:
    def setup_method(self):
        self.staff_user, self.staff_client = make_staff_user()
        self.readonly_user, self.readonly_client = make_readonly_user()
        self.anon_client = APIClient()
        self.project = make_project(created_by=self.staff_user)
        self.expense = make_expense(self.project, created_by=self.staff_user)
        self.url = reverse("depense:expense-detail", kwargs={"pk": self.expense.pk})

    def test_get_returns_200(self):
        response = self.staff_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == self.expense.pk

    def test_get_not_found_returns_404(self):
        url = reverse("depense:expense-detail", kwargs={"pk": 99999})
        response = self.staff_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_unauthenticated_returns_401(self):
        response = self.anon_client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_put_updates_expense(self):
        payload = {
            "project": self.project.pk,
            "date": "2025-08-01",
            "description": "Updated Expense",
            "montant": "8000.00",
        }
        response = self.staff_client.put(self.url, payload, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["description"] == "Updated Expense"

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
        assert not Expense.objects.filter(pk=self.expense.pk).exists()

    def test_delete_without_permission_returns_403(self):
        response = self.readonly_client.delete(self.url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_unauthenticated_returns_401(self):
        response = self.anon_client.delete(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ── Bulk Delete ───────────────────────────────────────────────────────────────


class TestBulkDeleteExpenseView:
    def setup_method(self):
        self.url = reverse("depense:expense-bulk-delete")
        self.staff_user, self.staff_client = make_staff_user()
        self.readonly_user, self.readonly_client = make_readonly_user()
        self.project = make_project(created_by=self.staff_user)

    def test_bulk_delete_returns_204(self):
        e1 = make_expense(self.project, date=date(2025, 8, 1), description="BD1")
        e2 = make_expense(self.project, date=date(2025, 8, 2), description="BD2")
        response = self.staff_client.delete(
            self.url, {"ids": [e1.pk, e2.pk]}, format="json"
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Expense.objects.filter(pk__in=[e1.pk, e2.pk]).exists()

    def test_bulk_delete_without_permission_returns_403(self):
        e = make_expense(self.project, description="BD3")
        response = self.readonly_client.delete(self.url, {"ids": [e.pk]}, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_bulk_delete_empty_ids_returns_400(self):
        response = self.staff_client.delete(self.url, {"ids": []}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_bulk_delete_missing_ids_returns_400(self):
        response = self.staff_client.delete(self.url, {}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

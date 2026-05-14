from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.db import IntegrityError
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from account.models import CustomUser
from depense.models import Expense
from project.models import Category, SubCategory, Project
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


def make_category(name="Matériaux", created_by=None):
    return Category.objects.create(name=name, created_by_user=created_by)


def make_subcategory(name="Ciment", category=None, created_by=None):
    if category is None:
        category = make_category(created_by=created_by)
    return SubCategory.objects.create(
        name=name, category=category, created_by_user=created_by
    )


def make_project(created_by=None, **kwargs):
    defaults = {
        "nom": "Projet Alpha",
        "description": "Description du projet",
        "budget_total": "50000.00",
        "date_debut": date(2025, 1, 1),
        "date_fin": date(2025, 12, 31),
        "status": "En cours",
        "chef_de_projet": "Jean Dupont",
        "nom_client": "Client A",
        "telephone_client": "+212600000000",
        "email_client": "client@example.com",
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


class TestCategoryModel:
    def test_str(self):
        cat = Category(name="Matériaux")
        assert str(cat) == "Matériaux"

    def test_unique_name(self):
        make_category(name="Unique")
        with pytest.raises(IntegrityError):
            make_category(name="Unique")


class TestSubCategoryModel:
    def test_str(self):
        sub = SubCategory(name="Ciment")
        assert str(sub) == "Ciment"

    def test_unique_together(self):
        cat = make_category(name="Cat1")
        make_subcategory(name="Sub1", category=cat)
        with pytest.raises(IntegrityError):
            make_subcategory(name="Sub1", category=cat)

    def test_same_name_different_category(self):
        cat1 = make_category(name="CatA")
        cat2 = make_category(name="CatB")
        s1 = make_subcategory(name="SharedName", category=cat1)
        s2 = make_subcategory(name="SharedName", category=cat2)
        assert s1.pk is not None
        assert s2.pk is not None


class TestProjectModel:
    def test_str(self):
        p = Project(nom="Test Proj")
        assert str(p) == "Test Proj"

    def test_jours_restants_positive(self):
        p = make_project(date_fin=date.today() + timedelta(days=10))
        assert p.jours_restants == 10

    def test_jours_restants_past(self):
        p = make_project(date_fin=date.today() - timedelta(days=5))
        assert p.jours_restants == 0

    def test_status_choices(self):
        for s in ("Complété", "En cours", "Pas commencé", "En attente"):
            p = make_project(
                nom=f"P-{s}",
                status=s,
                date_debut=date(2025, 1, 1),
                date_fin=date(2025, 12, 31),
            )
            assert p.status == s


# ── Category API ──────────────────────────────────────────────────────────────


class TestCategoryListCreateView:
    def setup_method(self):
        self.url = reverse("project:category-list-create")
        self.staff_user, self.staff_client = make_staff_user()
        self.readonly_user, self.readonly_client = make_readonly_user()
        self.anon_client = APIClient()

    def test_list_returns_200(self):
        make_category(name="Cat1", created_by=self.staff_user)
        make_category(name="Cat2", created_by=self.staff_user)
        response = self.staff_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        names = [c["name"] for c in response.data]
        assert "Cat1" in names
        assert "Cat2" in names

    def test_unauthenticated_returns_401(self):
        response = self.anon_client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_returns_201(self):
        payload = {"name": "Nouvelle Catégorie"}
        response = self.staff_client.post(self.url, payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "Nouvelle Catégorie"

    def test_create_without_permission_returns_403(self):
        response = self.readonly_client.post(
            self.url, {"name": "Blocked"}, format="json"
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_duplicate_name_returns_400(self):
        make_category(name="Dup")
        response = self.staff_client.post(self.url, {"name": "Dup"}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestCategoryDetailView:
    def setup_method(self):
        self.staff_user, self.staff_client = make_staff_user()
        self.readonly_user, self.readonly_client = make_readonly_user()
        self.anon_client = APIClient()
        self.category = make_category(name="DetailCat", created_by=self.staff_user)
        self.url = reverse("project:category-detail", kwargs={"pk": self.category.pk})

    def test_get_returns_200(self):
        response = self.staff_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == self.category.pk

    def test_get_not_found_returns_404(self):
        url = reverse("project:category-detail", kwargs={"pk": 99999})
        response = self.staff_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_put_updates_category(self):
        response = self.staff_client.put(self.url, {"name": "Updated"}, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "Updated"

    def test_put_without_permission_returns_403(self):
        response = self.readonly_client.put(self.url, {"name": "Nope"}, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_returns_204(self):
        response = self.staff_client.delete(self.url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Category.objects.filter(pk=self.category.pk).exists()

    def test_delete_without_permission_returns_403(self):
        response = self.readonly_client.delete(self.url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_returns_401(self):
        response = self.anon_client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestBulkDeleteCategoryView:
    def setup_method(self):
        self.url = reverse("project:category-bulk-delete")
        self.staff_user, self.staff_client = make_staff_user()
        self.readonly_user, self.readonly_client = make_readonly_user()

    def test_bulk_delete_returns_204(self):
        c1 = make_category(name="BD1")
        c2 = make_category(name="BD2")
        response = self.staff_client.delete(
            self.url, {"ids": [c1.pk, c2.pk]}, format="json"
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Category.objects.filter(pk__in=[c1.pk, c2.pk]).exists()

    def test_bulk_delete_without_permission_returns_403(self):
        c = make_category(name="BD3")
        response = self.readonly_client.delete(self.url, {"ids": [c.pk]}, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_bulk_delete_empty_ids_returns_400(self):
        response = self.staff_client.delete(self.url, {"ids": []}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_bulk_delete_missing_ids_returns_400(self):
        response = self.staff_client.delete(self.url, {}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ── SubCategory API ───────────────────────────────────────────────────────────


class TestSubCategoryListCreateView:
    def setup_method(self):
        self.url = reverse("project:subcategory-list-create")
        self.staff_user, self.staff_client = make_staff_user()
        self.readonly_user, self.readonly_client = make_readonly_user()
        self.anon_client = APIClient()
        self.category = make_category(name="ParentCat", created_by=self.staff_user)

    def test_list_returns_200(self):
        make_subcategory(name="Sub1", category=self.category)
        response = self.staff_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_filter_by_category(self):
        cat2 = make_category(name="OtherCat")
        make_subcategory(name="S-P", category=self.category)
        make_subcategory(name="S-O", category=cat2)
        response = self.staff_client.get(self.url, {"category": self.category.pk})
        assert response.status_code == status.HTTP_200_OK
        for item in response.data:
            assert item["category"] == self.category.pk

    def test_create_returns_201(self):
        payload = {"name": "New Sub", "category": self.category.pk}
        response = self.staff_client.post(self.url, payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "New Sub"

    def test_create_without_permission_returns_403(self):
        payload = {"name": "Blocked", "category": self.category.pk}
        response = self.readonly_client.post(self.url, payload, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_returns_401(self):
        response = self.anon_client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestSubCategoryDetailView:
    def setup_method(self):
        self.staff_user, self.staff_client = make_staff_user()
        self.readonly_user, self.readonly_client = make_readonly_user()
        self.anon_client = APIClient()
        self.category = make_category(name="SDCat", created_by=self.staff_user)
        self.sub = make_subcategory(
            name="SubDetail", category=self.category, created_by=self.staff_user
        )
        self.url = reverse("project:subcategory-detail", kwargs={"pk": self.sub.pk})

    def test_get_returns_200(self):
        response = self.staff_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == self.sub.pk

    def test_get_not_found_returns_404(self):
        url = reverse("project:subcategory-detail", kwargs={"pk": 99999})
        response = self.staff_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_put_updates(self):
        response = self.staff_client.put(
            self.url,
            {"name": "Updated Sub", "category": self.category.pk},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "Updated Sub"

    def test_put_without_permission_returns_403(self):
        response = self.readonly_client.put(
            self.url, {"name": "No", "category": self.category.pk}, format="json"
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_returns_204(self):
        response = self.staff_client.delete(self.url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not SubCategory.objects.filter(pk=self.sub.pk).exists()

    def test_delete_without_permission_returns_403(self):
        response = self.readonly_client.delete(self.url)
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestBulkDeleteSubCategoryView:
    def setup_method(self):
        self.url = reverse("project:subcategory-bulk-delete")
        self.staff_user, self.staff_client = make_staff_user()
        self.readonly_user, self.readonly_client = make_readonly_user()
        self.category = make_category(name="BDSCat")

    def test_bulk_delete_returns_204(self):
        s1 = make_subcategory(name="BDS1", category=self.category)
        s2 = make_subcategory(name="BDS2", category=self.category)
        response = self.staff_client.delete(
            self.url, {"ids": [s1.pk, s2.pk]}, format="json"
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_bulk_delete_without_permission_returns_403(self):
        s = make_subcategory(name="BDS3", category=self.category)
        response = self.readonly_client.delete(self.url, {"ids": [s.pk]}, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_bulk_delete_empty_ids_returns_400(self):
        response = self.staff_client.delete(self.url, {"ids": []}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ── Project API ───────────────────────────────────────────────────────────────


class TestProjectListCreateView:
    def setup_method(self):
        self.url = reverse("project:project-list-create")
        self.staff_user, self.staff_client = make_staff_user()
        self.readonly_user, self.readonly_client = make_readonly_user()
        self.anon_client = APIClient()

    def test_list_returns_200(self):
        make_project(created_by=self.staff_user)
        response = self.staff_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_list_paginated(self):
        for i in range(3):
            make_project(
                nom=f"Proj{i}",
                created_by=self.staff_user,
                date_debut=date(2025, 1, i + 1),
                date_fin=date(2025, 12, 31),
            )
        response = self.staff_client.get(self.url, {"pagination": "true", "page": 1})
        assert response.status_code == status.HTTP_200_OK
        assert "results" in response.data
        assert "count" in response.data

    def test_unauthenticated_returns_401(self):
        response = self.anon_client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_returns_201(self):
        payload = {
            "nom": "Nouveau Projet",
            "budget_total": "100000.00",
            "date_debut": "2025-06-01",
            "date_fin": "2025-12-31",
            "status": "Pas commencé",
            "chef_de_projet": "Marie Curie",
            "nom_client": "Client Z",
            "telephone_client": "+212600000000",
            "email_client": "z@example.com",
        }
        response = self.staff_client.post(self.url, payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["nom"] == "Nouveau Projet"

    def test_create_without_permission_returns_403(self):
        payload = {
            "nom": "Blocked",
            "budget_total": "5000.00",
            "date_debut": "2025-06-01",
            "date_fin": "2025-12-31",
            "status": "Pas commencé",
            "chef_de_projet": "Nobody",
            "nom_client": "Client X",
        }
        response = self.readonly_client.post(self.url, payload, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_missing_required_field_returns_400(self):
        payload = {"nom": "Missing fields"}
        response = self.staff_client.post(self.url, payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_filter_by_status(self):
        make_project(
            nom="EC",
            status="En cours",
            created_by=self.staff_user,
            date_debut=date(2025, 1, 1),
            date_fin=date(2025, 12, 31),
        )
        make_project(
            nom="PC",
            status="Pas commencé",
            created_by=self.staff_user,
            date_debut=date(2025, 2, 1),
            date_fin=date(2025, 12, 31),
        )
        response = self.staff_client.get(self.url, {"status": "En cours"})
        assert response.status_code == status.HTTP_200_OK
        for item in response.data:
            assert item["status"] == "En cours"

    def test_filter_by_search(self):
        make_project(
            nom="Résidence X",
            created_by=self.staff_user,
            date_debut=date(2025, 1, 1),
            date_fin=date(2025, 12, 31),
        )
        make_project(
            nom="Bureau Y",
            created_by=self.staff_user,
            date_debut=date(2025, 2, 1),
            date_fin=date(2025, 12, 31),
        )
        response = self.staff_client.get(self.url, {"search": "Résidence"})
        assert response.status_code == status.HTTP_200_OK
        assert all("Résidence" in r["nom"] for r in response.data)


# ── Project Detail/Edit/Delete ────────────────────────────────────────────────


class TestProjectDetailEditDeleteView:
    def setup_method(self):
        self.staff_user, self.staff_client = make_staff_user()
        self.readonly_user, self.readonly_client = make_readonly_user()
        self.anon_client = APIClient()
        self.project = make_project(created_by=self.staff_user)
        self.url = reverse("project:project-detail", kwargs={"pk": self.project.pk})

    def test_get_returns_200(self):
        response = self.staff_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == self.project.pk

    def test_get_not_found_returns_404(self):
        url = reverse("project:project-detail", kwargs={"pk": 99999})
        response = self.staff_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_unauthenticated_returns_401(self):
        response = self.anon_client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_put_updates_project(self):
        payload = {
            "nom": "Updated Projet",
            "budget_total": "75000.00",
            "date_debut": "2025-02-01",
            "date_fin": "2025-11-30",
            "status": "En cours",
            "chef_de_projet": "Updated Chef",
            "nom_client": "Updated Client",
            "telephone_client": "+212600000001",
            "email_client": "updated@example.com",
        }
        response = self.staff_client.put(self.url, payload, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["nom"] == "Updated Projet"

    def test_put_without_permission_returns_403(self):
        payload = {
            "nom": "Blocked",
            "budget_total": "5000.00",
            "date_debut": "2025-06-01",
            "date_fin": "2025-12-31",
            "status": "Pas commencé",
            "chef_de_projet": "Nobody",
            "nom_client": "Client X",
        }
        response = self.readonly_client.put(self.url, payload, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_returns_204(self):
        response = self.staff_client.delete(self.url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Project.objects.filter(pk=self.project.pk).exists()

    def test_delete_without_permission_returns_403(self):
        response = self.readonly_client.delete(self.url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_unauthenticated_returns_401(self):
        response = self.anon_client.delete(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestBulkDeleteProjectView:
    def setup_method(self):
        self.url = reverse("project:project-bulk-delete")
        self.staff_user, self.staff_client = make_staff_user()
        self.readonly_user, self.readonly_client = make_readonly_user()

    def test_bulk_delete_returns_204(self):
        p1 = make_project(nom="BD-P1", created_by=self.staff_user)
        p2 = make_project(nom="BD-P2", created_by=self.staff_user)
        response = self.staff_client.delete(
            self.url, {"ids": [p1.pk, p2.pk]}, format="json"
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Project.objects.filter(pk__in=[p1.pk, p2.pk]).exists()

    def test_bulk_delete_without_permission_returns_403(self):
        p = make_project(nom="BD-P3")
        response = self.readonly_client.delete(self.url, {"ids": [p.pk]}, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_bulk_delete_empty_ids_returns_400(self):
        response = self.staff_client.delete(self.url, {"ids": []}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_bulk_delete_missing_ids_returns_400(self):
        response = self.staff_client.delete(self.url, {}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ── Dashboard Tests ───────────────────────────────────────────────────────────


class TestProjectDashboardView:
    def setup_method(self):
        self.staff_user, self.staff_client = make_staff_user()
        self.anon_client = APIClient()
        self.project = make_project(
            nom="Dashboard Proj", created_by=self.staff_user, budget_total="100000.00"
        )
        self.url = reverse("project:project-dashboard", kwargs={"pk": self.project.pk})

    def test_returns_200(self):
        response = self.staff_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK

    def test_response_structure(self):
        response = self.staff_client.get(self.url)
        for key in (
            "project_id",
            "nom",
            "budget_total",
            "revenue_total",
            "depenses_totales",
            "benefice",
            "marge",
            "service_fees",
            "revenue_reelle",
            "top_categories",
            "top_subcategories",
            "top_vendors",
            "expense_history",
            "revenue_history",
        ):
            assert key in response.data

    def test_not_found_returns_404(self):
        url = reverse("project:project-dashboard", kwargs={"pk": 99999})
        response = self.staff_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_internal_project_dashboard_exposes_service_totals(self):
        make_revenue(self.project, montant="1000.00")
        make_expense(
            self.project,
            montant="990.00",
            frais_de_service=True,
            frais_de_service_valeur="10.00",
            frais_de_service_type="fixed",
        )

        response = self.staff_client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert Decimal(response.data["service_fees"]) == Decimal("10.00")
        assert Decimal(response.data["revenue_reelle"]) == Decimal("1010.00")

    def test_unauthenticated_returns_401(self):
        response = self.anon_client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestMultiProjectDashboardView:
    def setup_method(self):
        self.url = reverse("project:multi-project-dashboard")
        self.staff_user, self.staff_client = make_staff_user()
        self.anon_client = APIClient()

    def test_returns_200(self):
        response = self.staff_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK

    def test_response_structure(self):
        make_project(nom="MP1", created_by=self.staff_user)
        response = self.staff_client.get(self.url)
        for key in (
            "total_budget",
            "total_revenue",
            "total_expenses",
            "total_profit",
            "total_margin",
            "total_service_fees",
            "total_revenue_reelle",
            "top_expense_clients",
            "top_revenue_clients",
            "top_categories",
            "top_subcategories",
            "top_vendors",
            "expense_history",
            "revenue_history",
            "projects",
        ):
            assert key in response.data

    def test_top_clients_and_breakdowns_are_grouped(self):
        p1 = make_project(nom="MP1", nom_client="Client A", created_by=self.staff_user)
        p2 = make_project(nom="MP2", nom_client="Client B", created_by=self.staff_user)
        category = make_category(name="Lots techniques")
        subcategory = make_subcategory(name="Electricité", category=category)
        make_expense(p1, montant="300.00")
        make_expense(
            p2,
            montant="900.00",
            category=category,
            sous_categorie=subcategory,
            fournisseur="Abdelhak",
        )
        make_revenue(p1, montant="1200.00")
        make_revenue(p2, montant="400.00")

        response = self.staff_client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["top_expense_clients"][0]["client"] == "Client B"
        assert response.data["top_revenue_clients"][0]["client"] == "Client A"
        assert response.data["top_categories"][0]["category__name"] == "Lots techniques"
        assert response.data["top_subcategories"][0]["sous_categorie__name"] == "Electricité"
        assert response.data["top_vendors"][0]["fournisseur"] == "Abdelhak"
        assert response.data["expense_history"]
        assert response.data["revenue_history"]

    def test_internal_dashboard_exposes_service_totals(self):
        project = make_project(
            nom="MP Fees", nom_client="Client Fees", created_by=self.staff_user
        )
        make_revenue(project, montant="1000.00")
        make_expense(
            project,
            montant="990.00",
            frais_de_service=True,
            frais_de_service_valeur="10.00",
            frais_de_service_type="fixed",
        )

        response = self.staff_client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert Decimal(response.data["total_service_fees"]) == Decimal("10.00")
        assert Decimal(response.data["total_revenue_reelle"]) == Decimal("1010.00")

    def test_unauthenticated_returns_401(self):
        response = self.anon_client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestClientDashboardView:
    def setup_method(self):
        self.url = reverse("project:client-dashboard")
        self.staff_user, self.staff_client = make_staff_user()
        self.anon_client = APIClient()

    def test_response_structure(self):
        make_project(nom="Client Dashboard", created_by=self.staff_user)
        response = self.staff_client.get(self.url)
        for key in (
            "total_budget",
            "total_revenue",
            "total_expenses",
            "total_profit",
            "total_margin",
            "top_expense_clients",
            "top_revenue_clients",
            "top_categories",
            "top_subcategories",
            "top_vendors",
            "expense_history",
            "revenue_history",
            "projects",
        ):
            assert key in response.data
        assert "total_service_fees" not in response.data
        assert "total_revenue_reelle" not in response.data

    def test_expense_totals_include_service_fees_without_exposing_them(self):
        project = make_project(
            nom="Client P", nom_client="Client A", created_by=self.staff_user
        )
        make_revenue(project, montant="1000.00")
        make_expense(
            project,
            montant="500.00",
            frais_de_service=True,
            frais_de_service_valeur="10.00",
            frais_de_service_type="percentage",
        )

        response = self.staff_client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert Decimal(response.data["total_expenses"]) == Decimal("550.00")
        assert response.data["top_expense_clients"][0]["total"] == Decimal("550.00")
        assert "total_service_fees" not in response.data
        assert "total_revenue_reelle" not in response.data
        assert "service_fees" not in response.data["projects"][0]

    def test_unauthenticated_returns_401(self):
        response = self.anon_client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestClientProjectDashboardView:
    def setup_method(self):
        self.staff_user, self.staff_client = make_staff_user()
        self.anon_client = APIClient()
        self.project = make_project(
            nom="Client Project", created_by=self.staff_user, budget_total="1000.00"
        )
        self.url = reverse(
            "project:client-project-dashboard", kwargs={"pk": self.project.pk}
        )

    def test_project_totals_include_service_fees_without_exposing_them(self):
        make_revenue(self.project, montant="1000.00")
        make_expense(
            self.project,
            montant="990.00",
            frais_de_service=True,
            frais_de_service_valeur="10.00",
            frais_de_service_type="fixed",
        )

        response = self.staff_client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert Decimal(response.data["depenses_totales"]) == Decimal("1000.00")
        assert Decimal(response.data["benefice"]) == Decimal("0.00")
        assert "service_fees" not in response.data
        assert "revenue_reelle" not in response.data

    def test_not_found_returns_404(self):
        url = reverse("project:client-project-dashboard", kwargs={"pk": 99999})
        response = self.staff_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_unauthenticated_returns_401(self):
        response = self.anon_client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

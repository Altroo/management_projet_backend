from decimal import Decimal
import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory, force_authenticate
from account.views import UsersListCreateView
from management_projet_backend.ordering import apply_list_ordering, fields_for

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "model",
    [
        "accounts.CustomUser",
        "project.Project",
        "project.Category",
        "project.Client",
        "project.Supplier",
        "revenu.Revenue",
        "depense.Expense",
        "devis.Quote",
    ],
)
def test_every_public_ordering_expression_executes(model):
    qs = apps.get_model(model).objects.all()
    _, fields = fields_for(qs, "", {"store": "1"})
    assert fields
    for field in fields:
        for prefix in ["", "-"]:
            list(
                apply_list_ordering(qs, {"ordering": prefix + field, "store": "1"})[:2]
            )


def test_api_sorts_complete_result_before_pagination_and_keeps_filter():
    User = get_user_model()
    admin = User.objects.create_user(
        email="sort-admin@example.test", password="test", is_staff=True
    )
    names = ["Zulu", "Bravo", "Echo", "alpha", "Delta", "Charlie", "Foxtrot"]
    for i, name in enumerate(names):
        User.objects.create_user(
            email=f"sort-{i}@example.test",
            password="test",
            first_name=name,
            last_name="included",
        )
    User.objects.create_user(
        email="sort-excluded@example.test",
        password="test",
        first_name="AAA",
        last_name="excluded",
    )
    factory = APIRequestFactory()

    def page(ordering, number=1):
        request = factory.get(
            "/",
            {
                "pagination": "true",
                "page": number,
                "page_size": 5,
                "ordering": ordering,
                "last_name": "included",
            },
        )
        force_authenticate(request, admin)
        response = UsersListCreateView.as_view()(request)
        assert response.status_code == 200, response.data
        assert response.data["count"] == 7
        return [row["first_name"] for row in response.data["results"]]

    expected = sorted(names, key=str.casefold)
    assert page("first_name") + page("first_name", 2) == expected
    assert page("-first_name") + page("-first_name", 2) == expected[::-1]


@pytest.mark.parametrize(
    "ordering",
    [
        "password",
        "-password",
        "groups__name",
        "first_name,-id",
        "id; DROP TABLE account",
        "-",
    ],
)
def test_unknown_columns_cannot_order_private_or_related_data(ordering):
    qs = get_user_model().objects.order_by("-id")
    assert str(apply_list_ordering(qs, {"ordering": ordering}).query) == str(qs.query)


def test_directory_array_endpoints_order_on_server():
    from project.models import Category, Client, Supplier
    from project.views import (
        CategoryListCreateView,
        ClientListCreateView,
        SupplierListCreateView,
    )

    user = get_user_model().objects.create_user(
        email="directory@example.test", password="test", is_staff=True
    )
    for Model, View, field in [
        (Category, CategoryListCreateView, "name"),
        (Client, ClientListCreateView, "nom"),
        (Supplier, SupplierListCreateView, "nom"),
    ]:
        for name in ["Zulu", "Alpha", "Mike"]:
            Model.objects.create(**{field: name})
        request = APIRequestFactory().get("/", {"ordering": "-" + field})
        force_authenticate(request, user)
        response = View.as_view()(request)
        assert response.status_code == 200, response.data
        assert [row[field] for row in response.data] == ["Zulu", "Mike", "Alpha"]


def test_client_totals_include_legacy_project_names_without_double_counting():
    from datetime import date
    from project.models import Client, Project
    from revenu.models import Revenue

    a = Client.objects.create(nom="Alpha")
    b = Client.objects.create(nom="Bravo")
    linked = Project.objects.create(
        date_debut=date(2026, 1, 1), date_fin=date(2026, 12, 31), nom="Linked", client=a, nom_client="Alpha"
    )
    legacy = Project.objects.create(
        date_debut=date(2026, 1, 1), date_fin=date(2026, 12, 31), nom="Legacy", nom_client="ALPHA"
    )
    other = Project.objects.create(date_debut=date(2026, 1, 1), date_fin=date(2026, 12, 31), nom="Other", client=b)
    for project, amount in [(linked, 2), (legacy, 10), (other, 100)]:
        Revenue.objects.create(project=project, montant=amount, date=date(2026, 1, 1))
    assert list(
        apply_list_ordering(Client.objects.all(), {"ordering": "total_encaisse"})
    ) == [a, b]
    assert list(
        apply_list_ordering(Client.objects.all(), {"ordering": "-projects_count"})
    ) == [a, b]

from datetime import date
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from account.models import CustomUser
from depense.models import Expense
from revenu.models import Revenue
from .models import Category, Project, SubCategory, Supplier
from .pdf import (
    GREEN,
    NAVY,
    RED,
    TABLE_HEADER_BG,
    TRANSLATIONS,
    _build_totals,
    _nice_max,
    _report_data,
    _styles,
    _timeline_chart,
    _transaction_table,
    build_financial_report_pdf,
)

pytestmark = pytest.mark.django_db


def make_user(*, can_print=True):
    user = CustomUser.objects.create_user(
        email=f"report-{can_print}@test.com",
        password="securepass123",
        can_print=can_print,
    )
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return client


def make_project():
    return Project.objects.create(
        nom="Projet Rapport",
        budget_total="50000.00",
        date_debut=date(2026, 1, 1),
        date_fin=date(2026, 12, 31),
        status="En cours",
        nom_client="Client Rapport",
    )


class TestFinancialReportPDFView:
    def test_forwards_inclusive_period_project_and_language(self):
        project = make_project()
        url = reverse("project:financial-report-pdf-en")
        with patch(
            "project.views.build_financial_report_pdf",
            return_value=BytesIO(b"%PDF-1.4 test"),
        ) as generator:
            response = make_user().get(
                url,
                {
                    "date_from": "2026-01-01",
                    "date_to": "2026-12-31",
                    "project_id": project.id,
                },
            )

        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "application/pdf"
        assert response["Cache-Control"] == "no-store, no-cache, must-revalidate"
        generator.assert_called_once_with(
            project=project,
            date_from=date(2026, 1, 1),
            date_to=date(2026, 12, 31),
            language="en",
        )

    def test_denies_user_without_print_permission(self):
        response = make_user(can_print=False).get(
            reverse("project:financial-report-pdf-fr")
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.parametrize(
        "params",
        [
            {"date_from": "2026-01-01"},
            {"date_from": "bad", "date_to": "2026-01-02"},
            {"date_from": "2026-02-01", "date_to": "2026-01-01"},
        ],
    )
    def test_rejects_invalid_periods(self, params):
        response = make_user().get(reverse("project:financial-report-pdf-fr"), params)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_legacy_project_route_enforces_print_permission(self):
        project = make_project()
        response = make_user(can_print=False).get(
            reverse("project:project-report-pdf", kwargs={"pk": project.id})
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


def test_report_data_filters_boundaries_and_excludes_service_fee():
    project = make_project()
    Revenue.objects.create(
        project=project,
        date=date(2026, 1, 1),
        description="Included revenue",
        montant="1200.00",
    )
    Revenue.objects.create(
        project=project,
        date=date(2025, 12, 31),
        description="Excluded revenue",
        montant="99999.00",
    )
    Expense.objects.create(
        project=project,
        date=date(2026, 1, 31),
        description="Included expense",
        montant="400.00",
        frais_de_service=True,
        frais_de_service_valeur="9000.00",
        frais_de_service_type=Expense.SERVICE_FEE_TYPE_FIXED,
    )

    data = _report_data(
        project,
        date(2026, 1, 1),
        date(2026, 1, 31),
        {"uncategorized": "Sans catégorie"},
        "fr",
    )

    assert data["total_revenue"] == Decimal("1200.00")
    assert data["total_expenses"] == Decimal("400.00")
    assert data["cash_remaining"] == Decimal("800.00")
    assert [row.description for row in data["revenue_rows"]] == ["Included revenue"]
    assert [row.description for row in data["expense_rows"]] == ["Included expense"]


def test_transaction_tables_include_payment_and_expense_details():
    project = make_project()
    category = Category.objects.create(name="Matériaux")
    subcategory = SubCategory.objects.create(name="Marbre", category=category)
    supplier = Supplier.objects.create(nom="Fournisseur Atlas")
    advance = Revenue.objects.create(
        project=project,
        date=date(2026, 4, 3),
        description="Deuxième avance",
        notes="Virement bancaire",
        montant="15000.00",
    )
    expense = Expense.objects.create(
        project=project,
        date=date(2026, 4, 6),
        category=category,
        sous_categorie=subcategory,
        supplier=supplier,
        element="Plan de travail",
        description="Achat de marbre",
        notes="Bon de livraison reçu",
        montant="7200.00",
    )
    labels = TRANSLATIONS["fr"]
    styles = _styles()

    advances_table = _transaction_table(
        "advances",
        [advance],
        labels,
        "fr",
        520,
        styles,
        GREEN,
        single_project=False,
    )
    expenses_table = _transaction_table(
        "expenses",
        [expense],
        labels,
        "fr",
        520,
        styles,
        RED,
        single_project=False,
    )

    assert advances_table.repeatRows == 1
    assert advances_table._cellvalues[0][0].style.textColor.hexval() == NAVY.replace(
        "#", "0x"
    )
    assert any(
        command[3].hexval() == TABLE_HEADER_BG.replace("#", "0x")
        for command in advances_table._bkgrndcmds
        if command[:3] == ("BACKGROUND", (0, 0), (-1, 0))
    )
    assert advances_table._cellvalues[1][1].getPlainText() == "Projet Rapport"
    assert "Deuxième avance" in advances_table._cellvalues[1][3].getPlainText()
    assert "Virement bancaire" in advances_table._cellvalues[1][3].getPlainText()
    assert expenses_table.repeatRows == 1
    assert "Matériaux" in expenses_table._cellvalues[1][2].getPlainText()
    assert "Marbre" in expenses_table._cellvalues[1][2].getPlainText()
    assert expenses_table._cellvalues[1][3].getPlainText() == "Fournisseur Atlas"
    assert "Plan de travail" in expenses_table._cellvalues[1][4].getPlainText()
    assert "Bon de livraison reçu" in expenses_table._cellvalues[1][4].getPlainText()


def test_actual_report_builds_with_vector_charts():
    project = make_project()
    Revenue.objects.create(
        project=project,
        date=date(2026, 3, 10),
        description="Revenue",
        montant="1800.00",
    )
    Expense.objects.create(
        project=project,
        date=date(2026, 3, 12),
        description="Expense",
        montant="725.00",
    )

    buffer = build_financial_report_pdf(
        project=project,
        date_from=date(2026, 3, 1),
        date_to=date(2026, 3, 31),
        language="fr",
    )

    assert buffer.read(5) == b"%PDF-"


@pytest.mark.parametrize(
    ("largest_value", "expected_max"),
    [
        (1_698_000, 2_000_000),
        (20_000, 25_000),
        (26_815, 30_000),
    ],
)
def test_chart_axis_tracks_the_largest_plotted_value(largest_value, expected_max):
    assert _nice_max(largest_value) == expected_max


def test_totals_include_cash_remaining_as_revenue_minus_expenses():
    totals = _build_totals(
        {
            "total_revenue": Decimal("1200"),
            "total_expenses": Decimal("725"),
            "cash_remaining": Decimal("475"),
        },
        {
            "total_revenue": "Total revenus",
            "total_expenses": "Total dépenses",
            "cash_remaining": "Reste en caisse",
        },
        520,
        _styles(),
    )

    assert totals._colWidths[1] > 0
    assert totals._colWidths[3] > 0
    assert totals._cellvalues[0][0]._colWidths[0] == 4
    assert totals._cellvalues[0][2]._colWidths[0] == 4
    assert totals._cellvalues[0][4]._colWidths[0] == 4


def test_timeline_value_label_sits_above_its_marker():
    drawing = _timeline_chart(
        {
            "bucket_labels": ["05/2026"],
            "revenue_history": [0],
            "expense_history": [20_000],
        },
        {"revenue": "Revenus", "expenses": "Dépenses"},
        520,
    )

    label = next(
        item for item in drawing.contents if getattr(item, "text", None) == "20.0k"
    )
    markers = [
        item for item in drawing.contents if hasattr(item, "cx") and item.cx == label.x
    ]
    assert label.y > max(marker.cy for marker in markers)

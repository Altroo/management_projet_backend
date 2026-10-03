from datetime import date
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile, UploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from account.models import CustomUser
from depense.models import Expense
from project.models import Category, SubCategory, Project, Supplier
from project.pdf import build_financial_report_pdf
from revenu.models import Revenue
from .models import Quote
from .services import project_estimate_summary
from .serializers import QuoteAttachmentSerializer

pytestmark = pytest.mark.django_db


@pytest.fixture
def setup():
    user = CustomUser.objects.create_user(
        email="quotes@test.com", password="test-password", is_staff=True
    )
    client = APIClient()
    client.force_authenticate(user)
    project = Project.objects.create(
        nom="Projet devis",
        budget_total="90000",
        date_debut=date(2026, 1, 1),
        date_fin=date(2026, 12, 31),
    )
    supplier = Supplier.objects.create(nom="Céramique")
    category = Category.objects.create(name="Finitions")
    sub = SubCategory.objects.create(name="Pose céramique", category=category)
    payload = dict(
        project=project.pk,
        supplier=supplier.pk,
        category=category.pk,
        sous_categorie=sub.pk,
        number="DEV-001",
        date="2026-10-03",
        description="Pose de céramique",
        amount_ht="16666.67",
        amount_tva="3333.33",
        status="validated",
    )
    return client, project, payload


def create_quote(setup, **changes):
    client, project, payload = setup
    response = client.post("/api/devis/", {**payload, **changes}, format="json")
    assert response.status_code == 201, response.data
    return response.data


def expense_payload(quote, amount="5000.00"):
    return {
        key: quote[key] for key in ("project", "supplier", "category", "sous_categorie")
    } | {
        "quote": quote["id"],
        "date": "2026-10-03",
        "description": "Acompte pose",
        "montant": amount,
    }


def test_quote_crud_and_decimal_totals(setup):
    client, project, payload = setup
    quote = create_quote(setup, amount_ttc="1.00")
    assert quote["amount_ttc"] == "20000.00" and quote["spent"] == "0.00"
    assert Decimal(quote["remaining"]) == 20000
    response = client.put(
        f"/api/devis/{quote['id']}/",
        {**payload, "amount_ht": "0.10", "amount_tva": "0.20"},
        format="json",
    )
    assert response.status_code == 200 and response.data["amount_ttc"] == "0.30"
    assert client.delete(f"/api/devis/{quote['id']}/").status_code == 204


@pytest.mark.parametrize(
    "changes",
    [
        {"amount_ht": "0"},
        {"amount_ht": "-1"},
        {"amount_tva": "-1"},
        {"amount_ht": "1.001"},
        {"amount_ht": "NaN"},
        {"amount_ht": "999999999999.99", "amount_tva": "1"},
        {"status": "invalid"},
        {"supplier": None},
    ],
)
def test_quote_rejects_invalid_fields(setup, changes):
    client, project, payload = setup
    assert (
        client.post("/api/devis/", {**payload, **changes}, format="json").status_code
        == 400
    )


def test_category_subcategory_must_match(setup):
    client, project, payload = setup
    other = Category.objects.create(name="Autre")
    assert (
        client.post(
            "/api/devis/", {**payload, "category": other.pk}, format="json"
        ).status_code
        == 400
    )


def test_spend_update_delete_overrun_and_protection(setup):
    client, project, payload = setup
    quote = create_quote(setup)
    expense = client.post(
        "/api/depense/", expense_payload(quote, "25000"), format="json"
    )
    assert expense.status_code == 201, expense.data
    detail = client.get(f"/api/devis/{quote['id']}/").data
    assert detail["spent"] == "25000.00" and detail["overrun"] is True
    assert Decimal(detail["remaining"]) == 0 and Decimal(detail["variance"]) == -5000
    assert Decimal(detail["consumption_percent"]) == 125
    assert client.delete(f"/api/devis/{quote['id']}/").status_code == 400
    assert (
        client.put(
            f"/api/devis/{quote['id']}/",
            {**payload, "status": "rejected"},
            format="json",
        ).status_code
        == 400
    )
    other = Project.objects.create(
        nom="Autre", date_debut=date(2026, 1, 1), date_fin=date(2026, 12, 31)
    )
    assert (
        client.put(
            f"/api/devis/{quote['id']}/",
            {**payload, "project": other.pk},
            format="json",
        ).status_code
        == 400
    )
    update = client.put(
        f"/api/depense/{expense.data['id']}/",
        expense_payload(quote, "15000"),
        format="json",
    )
    assert update.status_code == 200, update.data
    assert client.get(f"/api/devis/{quote['id']}/").data["spent"] == "15000.00"
    assert client.delete(f"/api/depense/{expense.data['id']}/").status_code == 204
    assert client.get(f"/api/devis/{quote['id']}/").data["spent"] == "0.00"
    assert client.delete(f"/api/devis/{quote['id']}/").status_code == 204


@pytest.mark.parametrize("field", ["project", "category", "sous_categorie", "supplier"])
def test_expense_must_match_quote(setup, field):
    client, project, payload = setup
    quote = create_quote(setup)
    invalid = expense_payload(quote)
    if field == "project":
        other = Project.objects.create(
            nom="Autre", date_debut=date(2026, 1, 1), date_fin=date(2026, 12, 31)
        )
        invalid[field] = other.pk
    else:
        invalid[field] = None
    assert client.post("/api/depense/", invalid, format="json").status_code == 400


@pytest.mark.parametrize("status", ["received", "rejected"])
def test_expense_requires_validated_quote(setup, status):
    quote = create_quote(setup, status=status)
    assert (
        setup[0]
        .post("/api/depense/", expense_payload(quote), format="json")
        .status_code
        == 400
    )


def test_summary_counts_only_validated_and_all_expenses_once(setup):
    client, project, payload = setup
    quote = create_quote(setup)
    create_quote(setup, number="DEV-002", status="received")
    create_quote(setup, number="DEV-003", status="rejected")
    for amount in ("4000", "6000"):
        assert (
            client.post(
                "/api/depense/", expense_payload(quote, amount), format="json"
            ).status_code
            == 201
        )
    Expense.objects.create(
        project=project,
        date=date(2026, 1, 1),
        description="Sans devis",
        montant="3000",
        frais_de_service=True,
        frais_de_service_valeur="500",
    )
    Revenue.objects.create(
        project=project, date=date(2026, 1, 1), montant="15000", description="Avance"
    )
    summary = project_estimate_summary(project)
    assert summary["estimated"] == 20000 and summary["spent"] == 13000
    assert summary["remaining"] == 7000 and summary["unlinked_spent"] == 3000
    assert summary["advances"] == 15000 and summary["validated_count"] == 1
    assert sum(row["spent"] for row in summary["by_category"]) == 13000
    assert sum(row["estimated"] for row in summary["by_subcategory"]) == 20000
    assert any(
        row["category"] is None and row["spent"] == 3000
        for row in summary["by_category"]
    )
    dashboard = client.get(f"/api/project/dashboard/{project.pk}/")
    assert dashboard.status_code == 200
    assert Decimal(str(dashboard.data["estimate_summary"]["estimated"])) == 20000
    assert (
        "estimate_summary"
        not in client.get(f"/api/project/dashboard/client/{project.pk}/").data
    )


def test_empty_summary_marks_consumption_unavailable(setup):
    summary = project_estimate_summary(setup[1])
    assert summary["estimated"] == 0 and summary["validated_count"] == 0
    assert summary["consumption_percent"] is None


def test_search_filters_and_bulk_delete_atomicity(setup):
    client, project, payload = setup
    first = create_quote(setup)
    second = create_quote(setup, number="OTHER", status="received")
    assert (
        len(
            client.get(
                "/api/devis/",
                {"search": "DEV-001", "status": "validated", "project": project.pk},
            ).data
        )
        == 1
    )
    assert (
        len(
            client.get(
                "/api/devis/",
                {"status": "validated,received", "amount_ttc__gte": 20000},
            ).data
        )
        == 2
    )
    assert client.get("/api/devis/", {"date_after": "bad"}).status_code == 400
    client.post("/api/depense/", expense_payload(first), format="json")
    assert (
        client.delete(
            "/api/devis/bulk_delete/",
            {"ids": [first["id"], second["id"]]},
            format="json",
        ).status_code
        == 400
    )
    assert Quote.objects.count() == 2
    assert len(client.get("/api/depense/", {"quote": first["id"]}).data) == 1


def test_permissions(setup):
    client, project, payload = setup
    quote = create_quote(setup)
    user = CustomUser.objects.create_user(
        email="readonly-quotes@test.com",
        password="test-password",
        can_view=True,
        can_create=False,
        can_edit=False,
        can_delete=False,
        can_print=False,
    )
    client.force_authenticate(user)
    assert client.get("/api/devis/").status_code == 200
    assert client.post("/api/devis/", payload, format="json").status_code == 403
    assert (
        client.put(f"/api/devis/{quote['id']}/", payload, format="json").status_code
        == 403
    )
    assert client.delete(f"/api/devis/{quote['id']}/").status_code == 403
    assert (
        client.get(
            reverse("project:financial-report-pdf-fr"),
            {"project_id": project.pk, "include_estimates": "true"},
        ).status_code
        == 403
    )
    user.can_view = False
    user.save()
    assert client.get("/api/devis/").status_code == 403
    client.force_authenticate(None)
    assert client.get("/api/devis/").status_code == 401


def test_attachments(setup, tmp_path):
    client, project, payload = setup
    quote = create_quote(setup)
    url = f"/api/devis/{quote['id']}/attachments/"
    with override_settings(MEDIA_ROOT=tmp_path):
        file = SimpleUploadedFile(
            "quote.pdf", b"%PDF-1.4 sample", content_type="application/pdf"
        )
        response = client.post(url, {"file": file}, format="multipart")
        assert response.status_code == 201, response.data
        assert (
            response.data["file_url"].endswith(".pdf")
            and len(client.get(url).data) == 1
        )
        bad = SimpleUploadedFile("quote.html", b"<html/>", content_type="text/html")
        assert client.post(url, {"file": bad}, format="multipart").status_code == 400
        assert (
            client.delete(f"/api/devis/attachments/{response.data['id']}/").status_code
            == 204
        )
        assert not list(tmp_path.rglob("*.pdf"))


@pytest.mark.parametrize(
    "size, accepted",
    [(21 * 1024 * 1024, True), (250 * 1024 * 1024, True), (250 * 1024 * 1024 + 1, False)],
)
def test_quote_attachment_size_limit(size, accepted):
    # Supply upload metadata without allocating hundreds of MB for each boundary.
    file = UploadedFile(
        BytesIO(b"%PDF-1.4 sample"),
        name="quote.pdf",
        content_type="application/pdf",
        size=size,
    )
    serializer = QuoteAttachmentSerializer(data={"file": file})
    assert serializer.is_valid() is accepted
    if not accepted:
        assert "250 Mo" in str(serializer.errors["file"])


def test_report_option_is_explicit_and_project_only(setup):
    client, project, payload = setup
    url = reverse("project:financial-report-pdf-fr")
    with patch(
        "project.views.build_financial_report_pdf", return_value=BytesIO(b"%PDF-1.4")
    ) as generator:
        assert (
            client.get(
                url, {"project_id": project.pk, "include_estimates": "true"}
            ).status_code
            == 200
        )
        assert generator.call_args.kwargs["include_estimates"] is True
    assert client.get(url, {"include_estimates": "true"}).status_code == 400
    assert (
        client.get(
            url, {"project_id": project.pk, "include_estimates": "invalid"}
        ).status_code
        == 400
    )


def test_pdf_comparison_is_optional_and_uses_lifetime_totals(setup):
    import subprocess

    def extract(pdf):
        return subprocess.run(
            ["pdftotext", "-", "-"],
            input=pdf.getvalue(),
            capture_output=True,
            check=True,
        ).stdout.decode()

    client, project, payload = setup
    quote = create_quote(setup)
    client.post("/api/depense/", expense_payload(quote, "5000"), format="json")
    with override_settings(AI_PDF_TRANSLATION_ENABLED=False):
        normal = build_financial_report_pdf(project=project, language="en")
        comparison = build_financial_report_pdf(
            project=project,
            language="en",
            include_estimates=True,
            date_from=date(2025, 1, 1),
            date_to=date(2025, 12, 31),
        )
    text = extract(comparison)
    assert "Estimated budget / actual spending" in text
    assert "20 000.00" in text and "5 000.00" in text and "15 000.00" in text
    assert "Estimated budget / actual spending" not in extract(normal)


@pytest.mark.parametrize("field", ["project", "supplier", "category", "sous_categorie"])
def test_id_filters_reject_non_numbers(setup, field):
    assert setup[0].get("/api/devis/", {field: "invalid"}).status_code == 400


def test_deleting_project_cascades_linked_quotes_and_expenses(setup):
    client, project, payload = setup
    quote = create_quote(setup)
    assert (
        client.post("/api/depense/", expense_payload(quote), format="json").status_code
        == 201
    )
    project.delete()
    assert not Quote.objects.filter(pk=quote["id"]).exists()
    assert not Expense.objects.filter(quote_id=quote["id"]).exists()

#!/usr/bin/env python3
"""Render sanitized bilingual PDF fixtures without reading or writing the database."""

import argparse
import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "management_projet_backend.settings_test")

import django  # noqa: E402

django.setup()

from django.test import override_settings  # noqa: E402

from project.pdf import build_financial_report_pdf  # noqa: E402


def _company():
    return SimpleNamespace(
        raison_sociale="Entreprise Démonstration",
        adresse="10 rue Exemple, Casablanca",
        telephone="+212 5 00 00 00 00",
        email="contact@example.test",
        site_web="https://example.test",
        ICE="001122334455667",
        registre_de_commerce="RC-2048",
        numero_du_compte="MA64 0000 0000 0000 0000 0000 000",
        identifiant_fiscal="IF-4096",
        CNSS="CNSS-8192",
        logo=None,
        logo_cropped=None,
    )


def _fixture(language):
    if language == "en":
        copy = {
            "project_description": "Rénovation complète de la cuisine",
            "project_notes": "Livraison avant décembre",
            "revenue_description": "Deuxième acompte reçu",
            "revenue_notes": "Virement confirmé",
            "category": "Matériaux naturels",
            "subcategory": "Pierre décorative",
            "item": "Plan de travail principal",
            "expense_description": "Achat de marbre blanc",
            "expense_notes": "Bon de livraison reçu",
            "schedule_description": "Dernier acompte contractuel",
            "schedule_notes": "Après validation finale",
        }
        translated = {
            "Rénovation complète de la cuisine": "Complete kitchen renovation",
            "Livraison avant décembre": "Delivery before December",
            "Deuxième acompte reçu": "Second deposit received",
            "Virement confirmé": "Transfer confirmed",
            "Matériaux naturels": "Natural materials",
            "Pierre décorative": "Decorative stone",
            "Plan de travail principal": "Main countertop",
            "Achat de marbre blanc": "White marble purchase",
            "Bon de livraison reçu": "Delivery note received",
            "Dernier acompte contractuel": "Final contractual deposit",
            "Après validation finale": "After final approval",
        }
    else:
        copy = {
            "project_description": "Complete kitchen renovation",
            "project_notes": "Delivery before December",
            "revenue_description": "Second deposit received",
            "revenue_notes": "Transfer confirmed",
            "category": "Natural materials",
            "subcategory": "Decorative stone",
            "item": "Main countertop",
            "expense_description": "White marble purchase",
            "expense_notes": "Delivery note received",
            "schedule_description": "Final contractual deposit",
            "schedule_notes": "After final approval",
        }
        translated = {
            "Complete kitchen renovation": "Rénovation complète de la cuisine",
            "Delivery before December": "Livraison avant décembre",
            "Second deposit received": "Deuxième acompte reçu",
            "Transfer confirmed": "Virement confirmé",
            "Natural materials": "Matériaux naturels",
            "Decorative stone": "Pierre décorative",
            "Main countertop": "Plan de travail principal",
            "White marble purchase": "Achat de marbre blanc",
            "Delivery note received": "Bon de livraison reçu",
            "Final contractual deposit": "Dernier acompte contractuel",
            "After final approval": "Après validation finale",
        }

    client = SimpleNamespace(nom="Maison Atlas")
    project = SimpleNamespace(
        id=1,
        nom="Projet Atlas 2026",
        client=client,
        nom_client="Maison Atlas",
        status="En cours",
        description=copy["project_description"],
        notes=copy["project_notes"],
    )
    revenue = SimpleNamespace(
        id=1,
        project_id=1,
        project=project,
        date=date(2026, 3, 10),
        description=copy["revenue_description"],
        notes=copy["revenue_notes"],
        montant=Decimal("18000.00"),
    )
    category = SimpleNamespace(name=copy["category"])
    subcategory = SimpleNamespace(name=copy["subcategory"])
    supplier = SimpleNamespace(nom="Fournisseur Atlas")
    expense = SimpleNamespace(
        id=1,
        project_id=1,
        project=project,
        date=date(2026, 3, 12),
        category=category,
        sous_categorie=subcategory,
        supplier=supplier,
        element=copy["item"],
        description=copy["expense_description"],
        notes=copy["expense_notes"],
        montant=Decimal("7250.00"),
    )
    schedule = SimpleNamespace(
        id=1,
        project=project,
        due_date=date(2026, 4, 15),
        expected_amount=Decimal("5000.00"),
        description=copy["schedule_description"],
        notes=copy["schedule_notes"],
    )
    data = {
        "total_revenue": revenue.montant,
        "total_expenses": expense.montant,
        "cash_remaining": revenue.montant - expense.montant,
        "revenue_rows": [revenue],
        "expense_rows": [expense],
        "payment_schedule_rows": [schedule],
        "project_rows": [
            {
                "project": project,
                "revenue": revenue.montant,
                "expenses": expense.montant,
            }
        ],
        "category_totals": [(category.name, expense.montant)],
        "bucket_labels": ["03/2026"],
        "revenue_history": [float(revenue.montant)],
        "expense_history": [float(expense.montant)],
    }
    return project, data, translated


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()
    args.output_directory.mkdir(parents=True, exist_ok=True)

    for language in ("fr", "en"):
        project, data, translations = _fixture(language)
        with (
            override_settings(AI_PDF_TRANSLATION_ENABLED=True),
            patch("project.pdf._report_data", return_value=data),
            patch(
                "project.pdf.AiAssistantService.translate_many",
                return_value=translations,
            ),
        ):
            pdf = build_financial_report_pdf(
                project=project,
                language=language,
                company=_company(),
            )
        output = args.output_directory / f"ai-report-{language}.pdf"
        output.write_bytes(pdf.read())
        print(output)


if __name__ == "__main__":
    main()

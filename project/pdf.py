import math
import os
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape

from django.conf import settings
from django.utils import timezone

from ai_assistant.service import AiAssistantService
from company.views import get_company_profile
from depense.models import Expense
from project.models import ProjectPaymentSchedule
from revenu.models import Revenue

try:
    from reportlab.graphics.charts.piecharts import Pie
    from reportlab.graphics.shapes import Circle, Drawing, Line, PolyLine, Rect, String
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        CondPageBreak,
        Image,
        KeepTogether,
        LongTable,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
except ImportError:  # pragma: no cover - handled by the API view.
    REPORTLAB_AVAILABLE = False
else:
    REPORTLAB_AVAILABLE = True


TRANSLATIONS = {
    "fr": {
        "title": "RAPPORT FINANCIER",
        "all_projects": "Tous les projets",
        "project": "Projet",
        "client": "Client",
        "status": "Statut",
        "scope": "Périmètre",
        "period": "Période",
        "all_dates": "Toutes les dates",
        "generated": "Généré le",
        "report_date": "DATE DU RAPPORT",
        "issued_by": "RAPPORT ÉMIS PAR",
        "amounts_in_mad": "Toutes les valeurs sont en MAD",
        "other": "Autres",
        "total_revenue": "Total revenus",
        "total_expenses": "Total dépenses",
        "cash_remaining": "Reste en caisse",
        "revenue": "Revenus",
        "expenses": "Dépenses",
        "timeline": "Évolution des revenus et dépenses",
        "categories": "Dépenses par catégorie",
        "comparison": "Comparaison revenus / dépenses par projet",
        "project_comparison": "Comparaison des totaux du projet",
        "summary": "Synthèse par projet",
        "client_advances_detail": "Détail des avances client",
        "expenses_detail": "Détail des dépenses",
        "entries": "opérations",
        "date": "Date",
        "description": "Description",
        "notes": "Notes",
        "project_description": "Description du projet",
        "payment_schedule_detail": "Échéancier prévisionnel",
        "due_date": "Date prévue",
        "expected_amount": "Montant prévu",
        "amount": "Montant",
        "category": "Catégorie",
        "supplier": "Fournisseur",
        "item": "Élément",
        "total": "Total",
        "legal_information": "INFORMATIONS LÉGALES",
        "contact_information": "COORDONNÉES",
        "projects_in_scope": "projets inclus",
        "no_data": "Aucune donnée disponible pour la période sélectionnée.",
        "uncategorized": "Sans catégorie",
        "page": "Page",
    },
    "en": {
        "title": "FINANCIAL REPORT",
        "all_projects": "All projects",
        "project": "Project",
        "client": "Client",
        "status": "Status",
        "scope": "Scope",
        "period": "Period",
        "all_dates": "All dates",
        "generated": "Generated on",
        "report_date": "REPORT DATE",
        "issued_by": "REPORT ISSUED BY",
        "amounts_in_mad": "All amounts are in MAD",
        "other": "Other",
        "total_revenue": "Total revenue",
        "total_expenses": "Total expenses",
        "cash_remaining": "Cash remaining",
        "revenue": "Revenue",
        "expenses": "Expenses",
        "timeline": "Revenue and expenses over time",
        "categories": "Expenses by category",
        "comparison": "Revenue / expenses comparison by project",
        "project_comparison": "Project totals comparison",
        "summary": "Project summary",
        "client_advances_detail": "Client advances detail",
        "expenses_detail": "Expense detail",
        "entries": "entries",
        "date": "Date",
        "description": "Description",
        "notes": "Notes",
        "project_description": "Project description",
        "payment_schedule_detail": "Payment schedule",
        "due_date": "Due date",
        "expected_amount": "Expected amount",
        "amount": "Amount",
        "category": "Category",
        "supplier": "Supplier",
        "item": "Item",
        "total": "Total",
        "legal_information": "LEGAL INFORMATION",
        "contact_information": "CONTACT DETAILS",
        "projects_in_scope": "projects included",
        "no_data": "No data is available for the selected period.",
        "uncategorized": "Uncategorized",
        "page": "Page",
    },
}

STATUS_TRANSLATIONS = {
    "fr": {
        "Complété": "Complété",
        "En cours": "En cours",
        "Pas commencé": "Pas commencé",
        "En attente": "En attente",
        "En pause": "En pause",
        "Annulé": "Annulé",
        "En attente de démarrage": "En attente de démarrage",
        "Livré": "Livré",
    },
    "en": {
        "Complété": "Completed",
        "En cours": "In progress",
        "Pas commencé": "Not started",
        "En attente": "Pending",
        "En pause": "On hold",
        "Annulé": "Cancelled",
        "En attente de démarrage": "Waiting to start",
        "Livré": "Delivered",
    },
}

ACCENT = "#a8834f"
NAVY = "#121826"
MUTED = "#667085"
GREEN = "#087f5b"
RED = "#c0362c"
BORDER = "#d9d6cf"
SOFT_BG = "#f8f6f1"
TABLE_HEADER_BG = "#eee8dc"
PALETTE = (
    "#a8834f",
    "#087f5b",
    "#c0362c",
    "#52667a",
    "#80635a",
    "#0f766e",
    "#b56576",
    "#6b7c45",
)


def build_project_report_pdf(project, language="fr"):
    """Compatibility wrapper for the existing project report endpoint."""
    return build_financial_report_pdf(project=project, language=language)


def build_financial_report_pdf(
    *, project=None, date_from=None, date_to=None, language="fr", company=None
):
    if not REPORTLAB_AVAILABLE:
        raise ImportError("ReportLab is required to generate PDF reports.")

    language = language if language in TRANSLATIONS else "fr"
    labels = TRANSLATIONS[language]
    company = company or get_company_profile()
    report_data = _report_data(project, date_from, date_to, labels, language)
    if settings.AI_PDF_TRANSLATION_ENABLED:
        _translate_report_content(report_data, project, language)

    margin = 0.9 * cm
    page_width, _page_height = A4
    content_width = page_width - (2 * margin)
    styles = _styles()
    buffer = BytesIO()
    scope_name = project.nom if project else labels["all_projects"]
    generated_at = timezone.localtime(timezone.now())
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=margin,
        leftMargin=margin,
        topMargin=0.75 * cm,
        bottomMargin=2.0 * cm,
        title=f"{labels['title']} - {scope_name}",
        author=company.raison_sociale,
    )

    story = [
        _build_header(
            company,
            scope_name,
            date_from,
            date_to,
            labels,
            language,
            content_width,
            styles,
            generated_at,
        ),
        Spacer(1, 0.35 * cm),
    ]
    if project:
        story.extend(
            [
                _build_project_context(project, labels, content_width, styles),
                Spacer(1, 0.28 * cm),
            ]
        )
    story.extend(
        [
            _build_totals(report_data, labels, content_width, styles),
            Spacer(1, 0.4 * cm),
            _chart_section(
                labels["timeline"],
                _timeline_chart(report_data, labels, content_width),
                labels["amounts_in_mad"],
                styles,
                content_width,
            ),
            Spacer(1, 0.35 * cm),
            _chart_section(
                labels["categories"],
                _category_chart(report_data, labels, content_width),
                labels["amounts_in_mad"],
                styles,
                content_width,
            ),
            Spacer(1, 0.35 * cm),
            _chart_section(
                labels["project_comparison"] if project else labels["comparison"],
                _project_chart(report_data, labels, project is not None, content_width),
                labels["amounts_in_mad"],
                styles,
                content_width,
            ),
        ]
    )
    if not project:
        story.extend(
            [
                Spacer(1, 0.45 * cm),
                _section_heading(
                    labels["summary"],
                    f"{len(report_data['project_rows'])} "
                    f"{labels['projects_in_scope']}",
                    styles,
                    content_width,
                ),
                Spacer(1, 0.18 * cm),
                *_summary_cards(report_data, labels, content_width, styles),
            ]
        )
    story.extend(
        [
            CondPageBreak(8 * cm),
            *_transaction_details(
                report_data,
                labels,
                language,
                content_width,
                styles,
                single_project=project is not None,
            ),
        ]
    )

    footer = _footer(company.raison_sociale, generated_at, labels, language)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    return buffer


def _report_data(project, date_from, date_to, labels, language):
    revenues = Revenue.objects.select_related("project", "project__client").all()
    expenses = Expense.objects.select_related(
        "project",
        "project__client",
        "category",
        "sous_categorie",
        "supplier",
    ).all()
    payment_schedules = ProjectPaymentSchedule.objects.select_related("project").all()
    if project:
        revenues = revenues.filter(project=project)
        expenses = expenses.filter(project=project)
        payment_schedules = payment_schedules.filter(project=project)
    if date_from:
        revenues = revenues.filter(date__gte=date_from)
        expenses = expenses.filter(date__gte=date_from)
        payment_schedules = payment_schedules.filter(due_date__gte=date_from)
    if date_to:
        revenues = revenues.filter(date__lte=date_to)
        expenses = expenses.filter(date__lte=date_to)
        payment_schedules = payment_schedules.filter(due_date__lte=date_to)

    revenue_rows = list(revenues.order_by("date", "id"))
    expense_rows = list(expenses.order_by("date", "id"))
    total_revenue = sum((row.montant for row in revenue_rows), Decimal("0.00"))
    total_expenses = sum((row.montant for row in expense_rows), Decimal("0.00"))
    cash_remaining = total_revenue - total_expenses

    revenue_by_project = defaultdict(lambda: Decimal("0.00"))
    expense_by_project = defaultdict(lambda: Decimal("0.00"))
    projects_by_id = {}
    for row in revenue_rows:
        projects_by_id[row.project_id] = row.project
        revenue_by_project[row.project_id] += row.montant
    for row in expense_rows:
        projects_by_id[row.project_id] = row.project
        expense_by_project[row.project_id] += row.montant
    if project:
        projects_by_id[project.id] = project
    project_rows = [
        {
            "project": item,
            "revenue": revenue_by_project[item.id],
            "expenses": expense_by_project[item.id],
        }
        for item in sorted(projects_by_id.values(), key=lambda value: value.nom.lower())
    ]

    category_totals = defaultdict(lambda: Decimal("0.00"))
    for row in expense_rows:
        category_totals[
            row.category.name if row.category else labels["uncategorized"]
        ] += row.montant
    bucket_labels, revenue_history, expense_history = _time_buckets(
        revenue_rows, expense_rows, date_from, date_to, language
    )
    return {
        "total_revenue": total_revenue,
        "total_expenses": total_expenses,
        "cash_remaining": cash_remaining,
        "revenue_rows": revenue_rows,
        "expense_rows": expense_rows,
        "payment_schedule_rows": list(payment_schedules.order_by("due_date", "id")),
        "project_rows": project_rows,
        "category_totals": sorted(
            category_totals.items(), key=lambda item: item[1], reverse=True
        ),
        "bucket_labels": bucket_labels,
        "revenue_history": revenue_history,
        "expense_history": expense_history,
    }


def _translate_report_content(data, project, language):
    """Translate only human-authored copy on transient ORM instances."""
    fields = []
    if project:
        fields.extend((project.description, project.notes))
    for row in data["revenue_rows"]:
        fields.extend((row.description, row.notes))
    for row in data["expense_rows"]:
        fields.extend(
            (
                row.category.name if row.category else None,
                row.sous_categorie.name if row.sous_categorie else None,
                row.element,
                row.description,
                row.notes,
            )
        )
    for row in data["payment_schedule_rows"]:
        fields.extend((row.description, row.notes))

    translations = AiAssistantService().translate_many(
        fields, target_language=language, context="project"
    )

    def translated(value):
        return translations.get(value.strip(), value) if value and value.strip() else value

    if project:
        project.description = translated(project.description)
        project.notes = translated(project.notes)
    for row in data["revenue_rows"]:
        row.description = translated(row.description)
        row.notes = translated(row.notes)
    for row in data["expense_rows"]:
        if row.category:
            row.category.name = translated(row.category.name)
        if row.sous_categorie:
            row.sous_categorie.name = translated(row.sous_categorie.name)
        row.element = translated(row.element)
        row.description = translated(row.description)
        row.notes = translated(row.notes)
    for row in data["payment_schedule_rows"]:
        row.description = translated(row.description)
        row.notes = translated(row.notes)

    category_totals = defaultdict(lambda: Decimal("0.00"))
    for row in data["expense_rows"]:
        category_totals[
            row.category.name if row.category else TRANSLATIONS[language]["uncategorized"]
        ] += row.montant
    data["category_totals"] = sorted(
        category_totals.items(), key=lambda item: item[1], reverse=True
    )


def _time_buckets(revenues, expenses, date_from, date_to, language):
    all_dates = [row.date for row in revenues] + [row.date for row in expenses]
    if date_from and date_to:
        start, end = date_from, date_to
    elif all_dates:
        start, end = min(all_dates), max(all_dates)
    else:
        return [], [], []

    span_days = (end - start).days
    granularity = "day" if span_days <= 14 else "week" if span_days <= 90 else "month"
    revenue_totals = defaultdict(lambda: Decimal("0.00"))
    expense_totals = defaultdict(lambda: Decimal("0.00"))

    def bucket_key(value):
        if granularity == "day":
            return value
        if granularity == "week":
            return (value - start).days // 7
        return value.year, value.month

    for row in revenues:
        revenue_totals[bucket_key(row.date)] += row.montant
    for row in expenses:
        expense_totals[bucket_key(row.date)] += row.montant

    buckets = []
    if granularity == "day":
        current = start
        while current <= end:
            buckets.append(current)
            current += timedelta(days=1)
    elif granularity == "week":
        buckets = list(range((span_days // 7) + 1))
    else:
        current = date(start.year, start.month, 1)
        last = date(end.year, end.month, 1)
        while current <= last:
            buckets.append((current.year, current.month))
            current = date(
                current.year + (1 if current.month == 12 else 0),
                1 if current.month == 12 else current.month + 1,
                1,
            )

    if granularity == "day":
        date_format = "%d/%m" if language == "fr" else "%m/%d"
        display_labels = [bucket.strftime(date_format) for bucket in buckets]
    elif granularity == "week":
        date_format = "%d/%m" if language == "fr" else "%m/%d"
        display_labels = []
        for bucket in buckets:
            bucket_start = start + timedelta(days=bucket * 7)
            bucket_end = min(bucket_start + timedelta(days=6), end)
            display_labels.append(
                f"{bucket_start.strftime(date_format)}-{bucket_end.strftime(date_format)}"
            )
    else:
        display_labels = [f"{month:02d}/{year}" for year, month in buckets]
    return (
        display_labels,
        [float(revenue_totals[bucket]) for bucket in buckets],
        [float(expense_totals[bucket]) for bucket in buckets],
    )


def _styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            "CompanyName",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            textColor=colors.HexColor(NAVY),
        )
    )
    styles.add(
        ParagraphStyle(
            "Meta",
            parent=styles["Normal"],
            fontSize=8,
            leading=10.5,
            textColor=colors.HexColor(MUTED),
        )
    )
    styles.add(
        ParagraphStyle(
            "ReportTitle",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            alignment=TA_RIGHT,
            textColor=colors.HexColor(NAVY),
        )
    )
    styles.add(
        ParagraphStyle(
            "SectionTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=colors.HexColor(NAVY),
        )
    )
    styles.add(
        ParagraphStyle(
            "Kpi",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=19,
            alignment=TA_CENTER,
            textColor=colors.HexColor(NAVY),
        )
    )
    styles.add(
        ParagraphStyle(
            "Small",
            parent=styles["Normal"],
            fontSize=7.6,
            leading=9.4,
            textColor=colors.HexColor(NAVY),
        )
    )
    styles.add(
        ParagraphStyle(
            "SmallHeader",
            parent=styles["Small"],
            fontName="Helvetica-Bold",
            fontSize=7.2,
            leading=9,
            textColor=colors.HexColor(NAVY),
        )
    )
    styles.add(ParagraphStyle("SmallRight", parent=styles["Small"], alignment=TA_RIGHT))
    styles.add(
        ParagraphStyle(
            "TableCell",
            parent=styles["Small"],
            fontSize=6.8,
            leading=8.5,
        )
    )
    styles.add(
        ParagraphStyle(
            "TableCellRight",
            parent=styles["TableCell"],
            alignment=TA_RIGHT,
        )
    )
    styles.add(
        ParagraphStyle(
            "TableTotal",
            parent=styles["TableCell"],
            fontName="Helvetica-Bold",
            fontSize=7.2,
            leading=9,
        )
    )
    return styles


def _build_header(
    company,
    scope_name,
    date_from,
    date_to,
    labels,
    language,
    width,
    styles,
    generated_at,
):
    period = _period_label(date_from, date_to, labels, language)
    report_block = Paragraph(
        f"{labels['title']}<br/>"
        f"<font size='8.5' color='{NAVY}'>{_text(labels['report_date'])}: "
        f"{_format_date(generated_at, language)}</font><br/>"
        f"<font size='7.5' color='{MUTED}'>{_text(labels['scope'])}: "
        f"{_text(scope_name)}<br/>{_text(labels['period'])}: {_text(period)}</font>",
        styles["ReportTitle"],
    )

    brand_copy = Paragraph(
        f"<font size='6.5' color='{ACCENT}'><b>"
        f"{_text(labels['issued_by'])}</b></font><br/>"
        f"<font size='13' color='{NAVY}'><b>"
        f"{_text(company.raison_sociale)}</b></font>"
        + (
            f"<br/><font size='7' color='{MUTED}'>{_text(company.adresse)}</font>"
            if company.adresse
            else ""
        ),
        styles["CompanyName"],
    )
    brand = Table(
        [[_logo(company), brand_copy]],
        colWidths=[width * 0.19, width * 0.33],
        hAlign="LEFT",
    )
    brand.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(SOFT_BG)),
                ("LINEBEFORE", (0, 0), (0, 0), 3, colors.HexColor(ACCENT)),
                ("BOX", (0, 0), (-1, -1), 0.45, colors.HexColor(BORDER)),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    top = Table(
        [[brand, report_block]],
        colWidths=[width * 0.54, width * 0.46],
        hAlign="LEFT",
    )
    top.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("LINEBELOW", (0, 0), (-1, -1), 1.2, colors.HexColor(ACCENT)),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )

    legal_lines = [
        f"ICE: {_text(company.ICE)}" if company.ICE else None,
        (
            f"RC: {_text(company.registre_de_commerce)}"
            if company.registre_de_commerce
            else None
        ),
        f"RIB: {_text(company.numero_du_compte)}" if company.numero_du_compte else None,
        (
            f"IF: {_text(company.identifiant_fiscal)}"
            if company.identifiant_fiscal
            else None
        ),
        f"CNSS: {_text(company.CNSS)}" if company.CNSS else None,
    ]
    contact_lines = [
        _text(value)
        for value in (company.telephone, company.email, company.site_web)
        if value
    ]
    legal_block = Paragraph(
        f"<font size='6.5' color='{ACCENT}'><b>"
        f"{_text(labels['legal_information'])}</b></font><br/>"
        + "<br/>".join(item for item in legal_lines if item),
        styles["Small"],
    )
    contact_block = Paragraph(
        f"<font size='6.5' color='{ACCENT}'><b>"
        f"{_text(labels['contact_information'])}</b></font><br/>"
        + "<br/>".join(contact_lines),
        styles["Small"],
    )
    company_details = Table(
        [[legal_block, contact_block]],
        colWidths=[width * 0.58, width * 0.42],
        hAlign="LEFT",
    )
    company_details.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(SOFT_BG)),
                ("BOX", (0, 0), (-1, -1), 0.45, colors.HexColor(BORDER)),
                ("LINEBEFORE", (1, 0), (1, 0), 0.45, colors.HexColor(BORDER)),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return KeepTogether([top, Spacer(1, 0.18 * cm), company_details])


def _logo(company):
    logo = company.logo_cropped or company.logo
    if logo:
        try:
            if os.path.exists(logo.path):
                image = Image(logo.path)
                image._restrictSize(2.8 * cm, 2.0 * cm)
                return image
        except (AttributeError, OSError, ValueError):
            pass
    drawing = Drawing(116, 70)
    drawing.add(
        Rect(
            1,
            1,
            68,
            68,
            fillColor=colors.white,
            strokeColor=colors.HexColor(NAVY),
            strokeWidth=1,
        )
    )
    drawing.add(
        String(
            35,
            28,
            "LOGO",
            textAnchor="middle",
            fontName="Helvetica-Bold",
            fontSize=10,
            fillColor=colors.HexColor(NAVY),
        )
    )
    return drawing


def _build_project_context(project, labels, width, styles):
    client_name = project.client.nom if project.client else project.nom_client
    cells = [
        (labels["project"], project.nom),
        (labels["client"], client_name or "-"),
        (labels["status"], _status_label(project.status, labels)),
    ]
    table = Table(
        [
            [
                Paragraph(f"<b>{_text(label)}</b><br/>{_text(value)}", styles["Small"])
                for label, value in cells
            ]
        ],
        colWidths=[width / 3] * 3,
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(SOFT_BG)),
                ("BOX", (0, 0), (-1, -1), 0.45, colors.HexColor(BORDER)),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor(BORDER)),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    details = []
    if project.description:
        details.append(
            Paragraph(
                f"<b>{_text(labels['project_description'])}</b><br/>"
                f"{_text(project.description)}",
                styles["Small"],
            )
        )
    if project.notes:
        details.append(
            Paragraph(
                f"<b>{_text(labels['notes'])}</b><br/>{_text(project.notes)}",
                styles["Small"],
            )
        )
    if not details:
        return table
    detail_table = Table(
        [details],
        colWidths=[width / len(details)] * len(details),
        hAlign="LEFT",
    )
    detail_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.45, colors.HexColor(BORDER)),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor(BORDER)),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return KeepTogether([table, detail_table])


def _build_totals(data, labels, width, styles):
    gap = 0.28 * cm
    card_width = (width - (2 * gap)) / 3
    cash_color = ACCENT if data["cash_remaining"] >= 0 else RED
    table = Table(
        [
            [
                _kpi_card(
                    labels["total_revenue"],
                    data["total_revenue"],
                    GREEN,
                    card_width,
                    styles,
                ),
                "",
                _kpi_card(
                    labels["total_expenses"],
                    data["total_expenses"],
                    RED,
                    card_width,
                    styles,
                ),
                "",
                _kpi_card(
                    labels["cash_remaining"],
                    data["cash_remaining"],
                    cash_color,
                    card_width,
                    styles,
                ),
            ]
        ],
        colWidths=[card_width, gap, card_width, gap, card_width],
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return table


def _kpi_card(label, value, color, width, styles):
    content = Paragraph(
        f"<font size='8' color='{MUTED}'>{_text(label).upper()}</font>"
        f"<br/><font size='17' color='{color}'>{_money(value)}</font>"
        f"<font size='8' color='{MUTED}'> MAD</font>",
        styles["Kpi"],
    )
    card = Table(
        [["", content]],
        colWidths=[4, width - 4],
        hAlign="LEFT",
    )
    card.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), colors.HexColor(color)),
                ("BACKGROUND", (1, 0), (1, 0), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor(BORDER)),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (0, 0), 0),
                ("BOTTOMPADDING", (0, 0), (0, 0), 0),
                ("TOPPADDING", (1, 0), (1, 0), 13),
                ("BOTTOMPADDING", (1, 0), (1, 0), 13),
                ("LEFTPADDING", (1, 0), (1, 0), 8),
                ("RIGHTPADDING", (1, 0), (1, 0), 8),
            ]
        )
    )
    return card


def _section_heading(title, note, styles, width):
    heading = Table(
        [
            [
                Paragraph(
                    f"<b>{_text(title)}</b>",
                    styles["SectionTitle"],
                ),
                Paragraph(_text(note), styles["SmallRight"]),
            ]
        ],
        colWidths=[width * 0.72, width * 0.28],
        hAlign="LEFT",
    )
    heading.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (0, 0), (-1, -1), 0.8, colors.HexColor(ACCENT)),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("LEFTPADDING", (0, 0), (0, 0), 0),
                ("RIGHTPADDING", (1, 0), (1, 0), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return heading


def _chart_section(title, chart, note, styles, width):
    heading = _section_heading(title, note, styles, width)
    return KeepTogether([heading, Spacer(1, 0.08 * cm), chart])


def _transaction_details(data, labels, language, width, styles, *, single_project):
    sections = []
    table_specs = (
        (
            "advances",
            labels["client_advances_detail"],
            data["revenue_rows"],
            GREEN,
        ),
        (
            "expenses",
            labels["expenses_detail"],
            data["expense_rows"],
            RED,
        ),
    )
    for index, (kind, title, rows, accent) in enumerate(table_specs):
        if index:
            sections.extend([Spacer(1, 0.4 * cm), CondPageBreak(7 * cm)])
        sections.extend(
            [
                _section_heading(
                    title,
                    f"{len(rows)} {labels['entries']}",
                    styles,
                    width,
                ),
                Spacer(1, 0.16 * cm),
                _transaction_table(
                    kind,
                    rows,
                    labels,
                    language,
                    width,
                    styles,
                    accent,
                    single_project=single_project,
                ),
            ]
        )
    schedule_rows = data.get("payment_schedule_rows", [])
    if schedule_rows:
        sections.extend(
            [
                Spacer(1, 0.4 * cm),
                CondPageBreak(7 * cm),
                _section_heading(
                    labels["payment_schedule_detail"],
                    f"{len(schedule_rows)} {labels['entries']}",
                    styles,
                    width,
                ),
                Spacer(1, 0.16 * cm),
                _payment_schedule_table(
                    schedule_rows,
                    labels,
                    language,
                    width,
                    styles,
                    single_project=single_project,
                ),
            ]
        )
    return sections


def _payment_schedule_table(rows, labels, language, width, styles, *, single_project):
    if single_project:
        headers = [labels["due_date"], labels["description"], labels["expected_amount"]]
        col_widths = [width * 0.16, width * 0.62, width * 0.22]
    else:
        headers = [
            labels["due_date"],
            labels["project"],
            labels["description"],
            labels["expected_amount"],
        ]
        col_widths = [width * 0.14, width * 0.24, width * 0.42, width * 0.20]
    header_row = [
        Paragraph(f"<b>{_text(header)}</b>", styles["SmallHeader"])
        for header in headers
    ]
    body = []
    for row in rows:
        description = _table_cell(row.description or "-", styles, secondary=row.notes)
        cells = [
            _table_cell(_format_date(row.due_date, language), styles),
            description,
            _amount_cell(row.expected_amount, styles, color=ACCENT),
        ]
        if not single_project:
            cells.insert(1, _table_cell(row.project.nom, styles))
        body.append(cells)
    table = LongTable(
        [header_row, *body],
        colWidths=col_widths,
        repeatRows=1,
        splitByRow=1,
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(TABLE_HEADER_BG)),
                ("LINEABOVE", (0, 0), (-1, 0), 0.8, colors.HexColor(ACCENT)),
                ("LINEBELOW", (0, 0), (-1, 0), 1.2, colors.HexColor(ACCENT)),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(SOFT_BG)]),
                ("LINEBEFORE", (0, 0), (0, -1), 2.2, colors.HexColor(ACCENT)),
                ("LINEBELOW", (0, 1), (-1, -1), 0.35, colors.HexColor(BORDER)),
                ("BOX", (0, 0), (-1, -1), 0.45, colors.HexColor(BORDER)),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (-1, 0), (-1, -1), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def _transaction_table(
    kind,
    rows,
    labels,
    language,
    width,
    styles,
    accent,
    *,
    single_project,
):
    if not rows:
        empty = Table(
            [[Paragraph(_text(labels["no_data"]), styles["TableCell"])]],
            colWidths=[width],
            hAlign="LEFT",
        )
        empty.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(SOFT_BG)),
                    ("LINEBEFORE", (0, 0), (0, -1), 3, colors.HexColor(accent)),
                    ("BOX", (0, 0), (-1, -1), 0.45, colors.HexColor(BORDER)),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ]
            )
        )
        return empty

    if kind == "advances":
        headers, col_widths = _advance_table_columns(labels, width, single_project)
        body_rows = [
            _advance_table_row(row, labels, language, styles, single_project)
            for row in rows
        ]
    else:
        headers, col_widths = _expense_table_columns(labels, width, single_project)
        body_rows = [
            _expense_table_row(row, labels, language, styles, single_project)
            for row in rows
        ]

    header_row = [
        Paragraph(f"<b>{_text(header)}</b>", styles["SmallHeader"])
        for header in headers
    ]
    total = sum(
        (Decimal(str(row.montant or 0)) for row in rows),
        Decimal("0.00"),
    )
    total_row = [
        Paragraph(
            f"{_text(labels['total']).upper()} - {len(rows)} "
            f"{_text(labels['entries'])}",
            styles["TableTotal"],
        ),
        *([""] * (len(headers) - 2)),
        _amount_cell(total, styles, color=accent),
    ]
    table = LongTable(
        [header_row, *body_rows, total_row],
        colWidths=col_widths,
        repeatRows=1,
        splitByRow=1,
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor(TABLE_HEADER_BG),
                ),
                ("LINEABOVE", (0, 0), (-1, 0), 0.8, colors.HexColor(ACCENT)),
                ("LINEBELOW", (0, 0), (-1, 0), 1.2, colors.HexColor(accent)),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -2),
                    [colors.white, colors.HexColor(SOFT_BG)],
                ),
                ("LINEBEFORE", (0, 0), (0, -1), 2.2, colors.HexColor(accent)),
                ("LINEBELOW", (0, 1), (-1, -2), 0.35, colors.HexColor(BORDER)),
                ("BOX", (0, 0), (-1, -1), 0.45, colors.HexColor(BORDER)),
                (
                    "BACKGROUND",
                    (0, -1),
                    (-1, -1),
                    colors.HexColor(TABLE_HEADER_BG),
                ),
                ("LINEABOVE", (0, -1), (-1, -1), 0.9, colors.HexColor(accent)),
                ("SPAN", (0, -1), (-2, -1)),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (-1, 0), (-1, -1), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, 0), 7),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 7),
                ("TOPPADDING", (0, 1), (-1, -2), 6),
                ("BOTTOMPADDING", (0, 1), (-1, -2), 6),
                ("TOPPADDING", (0, -1), (-1, -1), 8),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 8),
            ]
        )
    )
    return table


def _advance_table_columns(labels, width, single_project):
    if single_project:
        return (
            [labels["date"], labels["description"], labels["amount"]],
            [width * 0.14, width * 0.66, width * 0.20],
        )
    return (
        [
            labels["date"],
            labels["project"],
            labels["client"],
            labels["description"],
            labels["amount"],
        ],
        [
            width * 0.11,
            width * 0.22,
            width * 0.18,
            width * 0.32,
            width * 0.17,
        ],
    )


def _expense_table_columns(labels, width, single_project):
    if single_project:
        return (
            [
                labels["date"],
                labels["category"],
                labels["supplier"],
                labels["description"],
                labels["amount"],
            ],
            [
                width * 0.11,
                width * 0.21,
                width * 0.18,
                width * 0.33,
                width * 0.17,
            ],
        )
    return (
        [
            labels["date"],
            labels["project"],
            labels["category"],
            labels["supplier"],
            labels["description"],
            labels["amount"],
        ],
        [
            width * 0.10,
            width * 0.17,
            width * 0.18,
            width * 0.15,
            width * 0.26,
            width * 0.14,
        ],
    )


def _advance_table_row(row, labels, language, styles, single_project):
    description = _table_cell(row.description, styles, secondary=row.notes)
    cells = [
        _table_cell(_format_date(row.date, language), styles),
        description,
        _amount_cell(row.montant, styles, color=GREEN),
    ]
    if single_project:
        return cells
    client_name = (
        row.project.client.nom if row.project.client else row.project.nom_client
    )
    return [
        cells[0],
        _table_cell(row.project.nom, styles),
        _table_cell(client_name or "-", styles),
        cells[1],
        cells[2],
    ]


def _expense_table_row(row, labels, language, styles, single_project):
    category_name = row.category.name if row.category else labels["uncategorized"]
    category = _table_cell(
        category_name,
        styles,
        secondary=row.sous_categorie.name if row.sous_categorie else None,
    )
    detail_parts = []
    if row.element and row.element.strip() != row.description.strip():
        detail_parts.append(f"{labels['item']}: {row.element}")
    if row.notes:
        detail_parts.append(f"{labels['notes']}: {row.notes}")
    description = _table_cell(
        row.description,
        styles,
        secondary=" | ".join(detail_parts),
    )
    base_cells = [
        _table_cell(_format_date(row.date, language), styles),
        category,
        _table_cell(row.supplier.nom if row.supplier else "-", styles),
        description,
        _amount_cell(row.montant, styles, color=RED),
    ]
    if single_project:
        return base_cells
    return [
        base_cells[0],
        _table_cell(row.project.nom, styles),
        *base_cells[1:],
    ]


def _table_cell(value, styles, *, secondary=None):
    copy = _text(value)
    if secondary:
        copy += (
            f"<br/><font size='6.1' color='{MUTED}'>"
            f"{_text(_short(secondary, 180))}</font>"
        )
    return Paragraph(copy, styles["TableCell"])


def _amount_cell(value, styles, *, color):
    return Paragraph(
        f"<font color='{color}'><b>{_money(value)}</b></font>"
        f"<br/><font size='5.8' color='{MUTED}'>MAD</font>",
        styles["TableCellRight"],
    )


def _empty_chart(labels, width):
    drawing = Drawing(width, 150)
    drawing.hAlign = "LEFT"
    drawing.add(
        Rect(
            0,
            0,
            width,
            145,
            fillColor=colors.HexColor(SOFT_BG),
            strokeColor=colors.HexColor(BORDER),
            strokeWidth=0.6,
            rx=8,
            ry=8,
        )
    )
    drawing.add(
        String(
            width / 2,
            70,
            labels["no_data"],
            textAnchor="middle",
            fontName="Helvetica",
            fontSize=9,
            fillColor=colors.HexColor(MUTED),
        )
    )
    return drawing


def _timeline_chart(data, labels, width):
    if not data["bucket_labels"]:
        return _empty_chart(labels, width)
    drawing = _chart_frame(width, 250)
    plot_x, plot_y, plot_width, plot_height = 55, 48, width - 78, 148
    values = data["revenue_history"] + data["expense_history"]
    value_max = _nice_max(max([1, *values]))
    _draw_plot_area(drawing, plot_x, plot_y, plot_width, plot_height)
    _draw_value_axis(drawing, plot_x, plot_y, plot_width, plot_height, value_max)
    _draw_series_key(drawing, width - 198, 226, GREEN, labels["revenue"])
    _draw_series_key(drawing, width - 102, 226, RED, labels["expenses"])

    count = len(data["bucket_labels"])
    step = plot_width / max(1, count - 1)
    for index, bucket_label in enumerate(data["bucket_labels"]):
        x = plot_x + (plot_width / 2 if count == 1 else index * step)
        drawing.add(
            String(
                x,
                25,
                _short(bucket_label, 13),
                textAnchor="middle",
                fontName="Helvetica",
                fontSize=6.3,
                fillColor=colors.HexColor(MUTED),
            )
        )

    series_specs = (
        (data["revenue_history"], GREEN),
        (data["expense_history"], RED),
    )
    series_points = []
    for series, color in series_specs:
        points = []
        for index, value in enumerate(series):
            x = plot_x + (plot_width / 2 if count == 1 else index * step)
            y = plot_y + (float(value) / value_max * plot_height)
            points.append((x, y))
        series_points.append(points)
        if len(points) > 1:
            drawing.add(
                PolyLine(
                    points,
                    strokeColor=colors.HexColor(color),
                    strokeWidth=2.6,
                )
            )
        for x, y in points:
            drawing.add(
                Circle(
                    x,
                    y,
                    3.6,
                    fillColor=colors.white,
                    strokeColor=colors.HexColor(color),
                    strokeWidth=2,
                )
            )

    for series_index, ((series, color), points) in enumerate(
        zip(series_specs, series_points)
    ):
        other_series = series_specs[1 - series_index][0]
        other_points = series_points[1 - series_index]
        for point_index, ((x, y), value) in enumerate(zip(points, series)):
            if value:
                label_y = y + 11
                if (
                    other_series[point_index]
                    and abs(other_points[point_index][1] - y) < 14
                ):
                    label_y += 12 * series_index
                _draw_value_badge(
                    drawing,
                    x,
                    label_y,
                    _chart_money(value),
                    color,
                )
    return drawing


def _category_chart(data, labels, width):
    positive_rows = [
        (name, value) for name, value in data["category_totals"] if value > 0
    ]
    if not positive_rows:
        return _empty_chart(labels, width)
    visible = positive_rows[:6]
    if len(positive_rows) > 6:
        visible.append(
            (
                labels["other"],
                sum((row[1] for row in positive_rows[6:]), Decimal("0.00")),
            )
        )
    drawing = _chart_frame(width, 230)
    pie = Pie()
    pie.x, pie.y, pie.width, pie.height = 24, 36, 170, 170
    pie.data = [float(value) for _name, value in visible]
    pie.labels = None
    pie.slices.strokeColor = colors.white
    pie.slices.strokeWidth = 1
    color_pairs = []
    for index, (name, value) in enumerate(visible):
        color = colors.HexColor(PALETTE[index % len(PALETTE)])
        pie.slices[index].fillColor = color
        color_pairs.append((color, name, value))
    drawing.add(pie)
    drawing.add(
        Circle(
            109,
            121,
            40,
            fillColor=colors.white,
            strokeColor=colors.white,
        )
    )
    drawing.add(
        String(
            109,
            124,
            _chart_money(sum(value for _name, value in visible)),
            textAnchor="middle",
            fontName="Helvetica-Bold",
            fontSize=10.5,
            fillColor=colors.HexColor(NAVY),
        )
    )
    drawing.add(
        String(
            109,
            109,
            labels["total"].upper(),
            textAnchor="middle",
            fontName="Helvetica-Bold",
            fontSize=6.2,
            fillColor=colors.HexColor(MUTED),
        )
    )
    total = sum(value for _name, value in visible)
    for index, (color, name, value) in enumerate(color_pairs):
        y = 203 - (index * 25)
        percentage = (value / total * 100) if total else Decimal("0")
        drawing.add(
            Rect(
                210,
                y - 7,
                width - 226,
                18,
                rx=3,
                ry=3,
                fillColor=(
                    colors.HexColor("#faf9f6") if index % 2 == 0 else colors.white
                ),
                strokeColor=colors.HexColor("#ece9e2"),
                strokeWidth=0.35,
            )
        )
        drawing.add(
            Rect(
                220,
                y - 2,
                9,
                9,
                rx=2,
                ry=2,
                fillColor=color,
                strokeColor=None,
            )
        )
        drawing.add(
            String(
                237,
                y,
                _short(name, 25),
                fontName="Helvetica-Bold",
                fontSize=7.2,
                fillColor=colors.HexColor(NAVY),
            )
        )
        drawing.add(
            String(
                width - 18,
                y,
                f"{_money(value)} MAD  |  {percentage:.1f}%",
                textAnchor="end",
                fontName="Helvetica-Bold",
                fontSize=6.8,
                fillColor=colors.HexColor(MUTED),
            )
        )
    return drawing


def _project_chart(data, labels, single_project, width):
    rows = data["project_rows"]
    if not rows:
        return _empty_chart(labels, width)
    if not single_project:
        rows = sorted(
            rows, key=lambda row: row["revenue"] + row["expenses"], reverse=True
        )[:8]
    chart_height = 245 if single_project else 286
    drawing = _chart_frame(width, chart_height)
    plot_x = 55
    plot_y = 58 if single_project else 96
    plot_width = width - 78
    plot_height = 126
    values = [float(row["revenue"]) for row in rows] + [
        float(row["expenses"]) for row in rows
    ]
    value_max = _nice_max(max([1, *values]))
    _draw_plot_area(drawing, plot_x, plot_y, plot_width, plot_height)
    _draw_value_axis(drawing, plot_x, plot_y, plot_width, plot_height, value_max)
    legend_y = chart_height - 24
    _draw_series_key(drawing, width - 198, legend_y, GREEN, labels["revenue"])
    _draw_series_key(drawing, width - 102, legend_y, RED, labels["expenses"])

    group_width = plot_width / len(rows)
    bar_width = min(31 if single_project else 18, group_width * 0.27)
    for index, row in enumerate(rows):
        center_x = plot_x + ((index + 0.5) * group_width)
        bar_specs = (
            (float(row["revenue"]), GREEN, center_x - bar_width - 2),
            (float(row["expenses"]), RED, center_x + 2),
        )
        label_positions = []
        for value, color, x in bar_specs:
            bar_height = value / value_max * plot_height
            if value:
                drawing.add(
                    Rect(
                        x,
                        plot_y,
                        bar_width,
                        bar_height,
                        rx=2,
                        ry=2,
                        fillColor=colors.HexColor(color),
                        strokeColor=None,
                    )
                )
            label_positions.append(
                [x + (bar_width / 2), plot_y + bar_height + 9, value, color]
            )
        if abs(label_positions[0][1] - label_positions[1][1]) < 13:
            label_positions[1][1] += 12
        for label_x, label_y, value, color in label_positions:
            _draw_value_badge(
                drawing,
                label_x,
                label_y,
                _chart_money(value),
                color,
            )
        if single_project:
            drawing.add(
                String(
                    center_x - (bar_width / 2) - 2,
                    42,
                    labels["revenue"],
                    textAnchor="middle",
                    fontName="Helvetica-Bold",
                    fontSize=6.5,
                    fillColor=colors.HexColor(GREEN),
                )
            )
            drawing.add(
                String(
                    center_x + (bar_width / 2) + 2,
                    42,
                    labels["expenses"],
                    textAnchor="middle",
                    fontName="Helvetica-Bold",
                    fontSize=6.5,
                    fillColor=colors.HexColor(RED),
                )
            )
        else:
            drawing.add(
                String(
                    center_x,
                    plot_y - 15,
                    f"P{index + 1}",
                    textAnchor="middle",
                    fontName="Helvetica-Bold",
                    fontSize=6.5,
                    fillColor=colors.HexColor(ACCENT),
                )
            )
    if not single_project:
        _draw_project_key(drawing, rows, width)
    return drawing


def _chart_frame(width, height):
    drawing = Drawing(width, height)
    drawing.hAlign = "LEFT"
    drawing.add(
        Rect(
            0,
            0,
            width,
            height - 2,
            rx=8,
            ry=8,
            fillColor=colors.white,
            strokeColor=colors.HexColor(BORDER),
            strokeWidth=0.6,
        )
    )
    return drawing


def _draw_plot_area(drawing, x, y, width, height):
    drawing.add(
        Rect(
            x,
            y,
            width,
            height,
            fillColor=colors.HexColor("#fcfcfb"),
            strokeColor=None,
        )
    )


def _draw_value_axis(drawing, x, y, width, height, value_max):
    for step in range(5):
        value = value_max * step / 4
        line_y = y + (height * step / 4)
        drawing.add(
            Line(
                x,
                line_y,
                x + width,
                line_y,
                strokeColor=colors.HexColor("#d8dee8"),
                strokeWidth=0.8 if step == 0 else 0.45,
            )
        )
        drawing.add(
            String(
                x - 7,
                line_y - 2,
                _chart_money(value),
                textAnchor="end",
                fontName="Helvetica",
                fontSize=6.2,
                fillColor=colors.HexColor(MUTED),
            )
        )
    drawing.add(
        String(
            x,
            y + height + 9,
            "MAD",
            fontName="Helvetica-Bold",
            fontSize=6.5,
            fillColor=colors.HexColor(MUTED),
        )
    )
    drawing.add(
        Line(
            x,
            y,
            x,
            y + height,
            strokeColor=colors.HexColor("#c9d1dc"),
            strokeWidth=0.55,
        )
    )


def _draw_series_key(drawing, x, y, color, label):
    drawing.add(
        Rect(
            x,
            y - 3,
            9,
            9,
            rx=2,
            ry=2,
            fillColor=colors.HexColor(color),
            strokeColor=None,
        )
    )
    drawing.add(
        String(
            x + 14,
            y,
            label,
            fontName="Helvetica-Bold",
            fontSize=7,
            fillColor=colors.HexColor(NAVY),
        )
    )


def _draw_value_badge(drawing, x, y, label, color):
    badge_width = max(19, (len(label) * 3.7) + 8)
    drawing.add(
        Rect(
            x - (badge_width / 2),
            y - 4,
            badge_width,
            11,
            rx=3,
            ry=3,
            fillColor=colors.white,
            strokeColor=colors.HexColor(color),
            strokeWidth=0.45,
        )
    )
    drawing.add(
        String(
            x,
            y - 0.5,
            label,
            textAnchor="middle",
            fontName="Helvetica-Bold",
            fontSize=6.2,
            fillColor=colors.HexColor(color),
        )
    )


def _draw_project_key(drawing, rows, width):
    rows_per_column = math.ceil(len(rows) / 2)
    column_width = width / 2
    for index, row in enumerate(rows):
        column = index // rows_per_column
        row_index = index % rows_per_column
        x = 20 + (column * column_width)
        y = 61 - (row_index * 13)
        drawing.add(
            Rect(
                x,
                y - 3,
                16,
                9,
                rx=2,
                ry=2,
                fillColor=colors.HexColor("#eee8dc"),
                strokeColor=colors.HexColor(ACCENT),
                strokeWidth=0.4,
            )
        )
        drawing.add(
            String(
                x + 8,
                y,
                f"P{index + 1}",
                textAnchor="middle",
                fontName="Helvetica-Bold",
                fontSize=5.8,
                fillColor=colors.HexColor(ACCENT),
            )
        )
        drawing.add(
            String(
                x + 22,
                y,
                _short(row["project"].nom, 33),
                fontName="Helvetica",
                fontSize=6.2,
                fillColor=colors.HexColor(NAVY),
            )
        )


def _nice_max(value):
    if value <= 0:
        return 1
    padded = value * 1.1
    magnitude = 10 ** math.floor(math.log10(padded))
    normalized = padded / magnitude
    steps = (1, 1.25, 1.5, 2, 2.5, 3, 4, 5, 7.5, 10)
    nice = next(step for step in steps if normalized <= step)
    return nice * magnitude


def _summary_cards(data, labels, width, styles):
    rows = data["project_rows"]
    if not rows:
        return [Paragraph(labels["no_data"], styles["Small"])]

    value_max = max(
        1,
        *[float(item["revenue"]) for item in rows],
        *[float(item["expenses"]) for item in rows],
    )
    cards = []
    for item in rows:
        project = item["project"]
        client_name = project.client.nom if project.client else project.nom_client
        identity = Paragraph(
            f"<font size='10'><b>{_text(project.nom)}</b></font><br/>"
            f"<font size='7' color='{MUTED}'>{_text(labels['client'])}: "
            f"{_text(client_name or '-')}</font><br/>"
            f"<font size='7' color='{ACCENT}'><b>"
            f"{_text(_status_label(project.status, labels))}</b></font>",
            styles["Small"],
        )
        metrics_width = width * 0.48 - 20
        metrics = Table(
            [
                [
                    Paragraph(
                        f"<font size='6.5' color='{MUTED}'>"
                        f"{_text(labels['revenue']).upper()}</font><br/>"
                        f"<font size='10' color='{GREEN}'><b>"
                        f"{_money(item['revenue'])}</b></font>",
                        styles["Small"],
                    ),
                    Paragraph(
                        f"<font size='6.5' color='{MUTED}'>"
                        f"{_text(labels['expenses']).upper()}</font><br/>"
                        f"<font size='10' color='{RED}'><b>"
                        f"{_money(item['expenses'])}</b></font>",
                        styles["SmallRight"],
                    ),
                ],
                [
                    _performance_bars(
                        float(item["revenue"]),
                        float(item["expenses"]),
                        value_max,
                        metrics_width,
                    ),
                    "",
                ],
            ],
            colWidths=[metrics_width / 2] * 2,
            hAlign="LEFT",
        )
        metrics.setStyle(
            TableStyle(
                [
                    ("SPAN", (0, 1), (1, 1)),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        card = Table(
            [[identity, metrics]],
            colWidths=[width * 0.52, width * 0.48],
            hAlign="LEFT",
        )
        card.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(SOFT_BG)),
                    ("LINEBEFORE", (0, 0), (0, 0), 3, colors.HexColor(ACCENT)),
                    ("BOX", (0, 0), (-1, -1), 0.45, colors.HexColor(BORDER)),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        cards.extend([KeepTogether([card]), Spacer(1, 0.12 * cm)])
    return cards


def _performance_bars(revenue, expenses, value_max, width):
    drawing = Drawing(width, 15)
    drawing.hAlign = "LEFT"
    for y, value, color in ((10, revenue, GREEN), (2, expenses, RED)):
        drawing.add(
            Rect(
                0,
                y,
                width,
                4,
                rx=2,
                ry=2,
                fillColor=colors.HexColor("#e7e3db"),
                strokeColor=None,
            )
        )
        if value:
            drawing.add(
                Rect(
                    0,
                    y,
                    max(2, width * value / value_max),
                    4,
                    rx=2,
                    ry=2,
                    fillColor=colors.HexColor(color),
                    strokeColor=None,
                )
            )
    return drawing


def _footer(company_name, generated_at, labels, language):
    generated_text = _format_datetime(generated_at, language)

    def _draw(canvas, doc):
        canvas.saveState()
        width, _height = doc.pagesize
        canvas.setStrokeColor(colors.HexColor(BORDER))
        canvas.setLineWidth(0.5)
        canvas.line(doc.leftMargin, 1.0 * cm, width - doc.rightMargin, 1.0 * cm)
        canvas.setFillColor(colors.HexColor(MUTED))
        canvas.setFont("Helvetica", 7)
        canvas.drawString(
            doc.leftMargin,
            0.62 * cm,
            f"{company_name} - {labels['generated']} {generated_text}",
        )
        canvas.drawRightString(
            width - doc.rightMargin,
            0.62 * cm,
            f"{labels['page']} {canvas.getPageNumber()}",
        )
        canvas.restoreState()

    return _draw


def _period_label(date_from, date_to, labels, language):
    if not date_from or not date_to:
        return labels["all_dates"]
    return f"{_format_date(date_from, language)} - {_format_date(date_to, language)}"


def _format_date(value, language):
    return value.strftime("%d/%m/%Y" if language == "fr" else "%m/%d/%Y")


def _format_datetime(value, language):
    return value.strftime("%d/%m/%Y %H:%M" if language == "fr" else "%m/%d/%Y %H:%M")


def _money(value):
    amount = Decimal(value or 0).quantize(Decimal("0.01"))
    return f"{amount:,.2f}".replace(",", " ")


def _status_label(status, labels):
    language = "en" if labels["title"] == "FINANCIAL REPORT" else "fr"
    return STATUS_TRANSLATIONS[language].get(status, status)


def _chart_money(value):
    amount = float(value or 0)
    absolute = abs(amount)
    if absolute >= 1_000_000:
        return f"{amount / 1_000_000:.1f}M"
    if absolute >= 1_000:
        return f"{amount / 1_000:.1f}k"
    return f"{amount:,.0f}".replace(",", " ")


def _text(value):
    return escape(str(value or "-"))


def _short(value, length):
    value = str(value)
    return value if len(value) <= length else f"{value[: length - 3]}..."

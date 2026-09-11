import math
import os
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape

from django.utils import timezone

from company.views import get_company_profile
from depense.models import Expense
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
        Image,
        KeepTogether,
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
        "revenue": "Revenus",
        "expenses": "Dépenses",
        "timeline": "Évolution des revenus et dépenses",
        "categories": "Dépenses par catégorie",
        "comparison": "Comparaison revenus / dépenses par projet",
        "project_comparison": "Comparaison des totaux du projet",
        "summary": "Synthèse par projet",
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
        "revenue": "Revenue",
        "expenses": "Expenses",
        "timeline": "Revenue and expenses over time",
        "categories": "Expenses by category",
        "comparison": "Revenue / expenses comparison by project",
        "project_comparison": "Project totals comparison",
        "summary": "Project summary",
        "no_data": "No data is available for the selected period.",
        "uncategorized": "Uncategorized",
        "page": "Page",
    },
}

ACCENT = "#1d4ed8"
NAVY = "#0f172a"
MUTED = "#64748b"
GREEN = "#047857"
RED = "#b91c1c"
BORDER = "#cbd5e1"
SOFT_BG = "#f8fafc"
PALETTE = (
    "#1d4ed8",
    "#047857",
    "#b91c1c",
    "#c2410c",
    "#6d28d9",
    "#0f766e",
    "#be123c",
    "#4d7c0f",
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
                "01",
                labels["timeline"],
                _timeline_chart(report_data, labels),
                labels["amounts_in_mad"],
                styles,
            ),
            Spacer(1, 0.35 * cm),
            _chart_section(
                "02",
                labels["categories"],
                _category_chart(report_data, labels),
                labels["amounts_in_mad"],
                styles,
            ),
            Spacer(1, 0.35 * cm),
            _chart_section(
                "03",
                labels["project_comparison"] if project else labels["comparison"],
                _project_chart(report_data, labels, project is not None),
                labels["amounts_in_mad"],
                styles,
            ),
        ]
    )
    if not project:
        story.extend(
            [
                Spacer(1, 0.45 * cm),
                Paragraph(labels["summary"], styles["SectionTitle"]),
                Spacer(1, 0.1 * cm),
                _summary_table(report_data, labels, content_width, styles),
            ]
        )

    footer = _footer(company.raison_sociale, generated_at, labels, language)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    return buffer


def _report_data(project, date_from, date_to, labels, language):
    revenues = Revenue.objects.select_related("project", "project__client").all()
    expenses = Expense.objects.select_related(
        "project", "project__client", "category"
    ).all()
    if project:
        revenues = revenues.filter(project=project)
        expenses = expenses.filter(project=project)
    if date_from:
        revenues = revenues.filter(date__gte=date_from)
        expenses = expenses.filter(date__gte=date_from)
    if date_to:
        revenues = revenues.filter(date__lte=date_to)
        expenses = expenses.filter(date__lte=date_to)

    revenue_rows = list(revenues.order_by("date", "id"))
    expense_rows = list(expenses.order_by("date", "id"))
    total_revenue = sum((row.montant for row in revenue_rows), Decimal("0.00"))
    total_expenses = sum((row.montant for row in expense_rows), Decimal("0.00"))

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
        "project_rows": project_rows,
        "category_totals": sorted(
            category_totals.items(), key=lambda item: item[1], reverse=True
        ),
        "bucket_labels": bucket_labels,
        "revenue_history": revenue_history,
        "expense_history": expense_history,
    }


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
            fontSize=20,
            leading=24,
            alignment=TA_RIGHT,
            textColor=colors.HexColor(ACCENT),
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
            textColor=colors.white,
        )
    )
    styles.add(ParagraphStyle("SmallRight", parent=styles["Small"], alignment=TA_RIGHT))
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
        f"<font size='9' color='{NAVY}'>{_text(labels['report_date'])}: "
        f"{_format_date(generated_at, language)}</font><br/>"
        f"<font size='8' color='{MUTED}'>{_text(labels['scope'])}: "
        f"{_text(scope_name)}<br/>{_text(labels['period'])}: {_text(period)}</font>",
        styles["ReportTitle"],
    )
    top = Table(
        [[_logo(company), report_block]], colWidths=[width * 0.46, width * 0.54]
    )
    top.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("LINEBELOW", (0, 0), (-1, -1), 1.5, colors.HexColor(ACCENT)),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )

    identity_lines = [f"<b>{_text(company.raison_sociale)}</b>"]
    if company.adresse:
        identity_lines.append(_text(company.adresse))
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
    issuer_title = Paragraph(
        f"<font color='{ACCENT}'><b>{_text(labels['issued_by'])}</b></font>",
        styles["Small"],
    )
    issuer = Table(
        [
            [issuer_title, "", ""],
            [
                Paragraph("<br/>".join(identity_lines), styles["CompanyName"]),
                Paragraph(
                    "<br/>".join(item for item in legal_lines if item) or "-",
                    styles["Small"],
                ),
                Paragraph("<br/>".join(contact_lines) or "-", styles["Small"]),
            ],
        ],
        colWidths=[width * 0.42, width * 0.34, width * 0.24],
    )
    issuer.setStyle(
        TableStyle(
            [
                ("SPAN", (0, 0), (-1, 0)),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(SOFT_BG)),
                ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.HexColor(ACCENT)),
                ("BOX", (0, 0), (-1, -1), 0.45, colors.HexColor(BORDER)),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return KeepTogether([top, Spacer(1, 0.18 * cm), issuer])


def _logo(company):
    logo = company.logo_cropped or company.logo
    if logo:
        try:
            if os.path.exists(logo.path):
                image = Image(logo.path)
                image._restrictSize(4.1 * cm, 2.7 * cm)
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
        (labels["status"], project.status),
    ]
    table = Table(
        [
            [
                Paragraph(f"<b>{_text(label)}</b><br/>{_text(value)}", styles["Small"])
                for label, value in cells
            ]
        ],
        colWidths=[width / 3] * 3,
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
    return table


def _build_totals(data, labels, width, styles):
    cells = [
        Paragraph(
            f"<font size='8' color='{MUTED}'>{_text(labels['total_revenue']).upper()}</font>"
            f"<br/><font size='17' color='{GREEN}'>{_money(data['total_revenue'])}</font>"
            f"<font size='8' color='{MUTED}'> MAD</font>",
            styles["Kpi"],
        ),
        Paragraph(
            f"<font size='8' color='{MUTED}'>{_text(labels['total_expenses']).upper()}</font>"
            f"<br/><font size='17' color='{RED}'>{_money(data['total_expenses'])}</font>"
            f"<font size='8' color='{MUTED}'> MAD</font>",
            styles["Kpi"],
        ),
    ]
    table = Table([cells], colWidths=[width / 2] * 2)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor(BORDER)),
                ("INNERGRID", (0, 0), (-1, -1), 0.45, colors.HexColor(BORDER)),
                ("LINEBEFORE", (0, 0), (0, 0), 4, colors.HexColor(GREEN)),
                ("LINEBEFORE", (1, 0), (1, 0), 4, colors.HexColor(RED)),
                ("TOPPADDING", (0, 0), (-1, -1), 13),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 13),
            ]
        )
    )
    return table


def _chart_section(number, title, chart, note, styles):
    heading = Table(
        [
            [
                Paragraph(f"<b>{number}</b>", styles["SmallHeader"]),
                Paragraph(
                    f"<b>{_text(title)}</b><br/><font size='7' color='{MUTED}'>"
                    f"{_text(note)}</font>",
                    styles["SectionTitle"],
                ),
            ]
        ],
        colWidths=[30, 490],
    )
    heading.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), colors.HexColor(ACCENT)),
                ("ALIGN", (0, 0), (0, 0), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (1, 0), (1, 0), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return KeepTogether([heading, Spacer(1, 0.08 * cm), chart])


def _empty_chart(labels):
    drawing = Drawing(520, 150)
    drawing.add(
        Rect(
            0,
            0,
            520,
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
            260,
            70,
            labels["no_data"],
            textAnchor="middle",
            fontName="Helvetica",
            fontSize=9,
            fillColor=colors.HexColor(MUTED),
        )
    )
    return drawing


def _timeline_chart(data, labels):
    if not data["bucket_labels"]:
        return _empty_chart(labels)
    drawing = _chart_frame(235)
    plot_x, plot_y, plot_width, plot_height = 52, 44, 448, 136
    values = data["revenue_history"] + data["expense_history"]
    value_max = _nice_max(max([1, *values]) * 1.2)
    _draw_value_axis(drawing, plot_x, plot_y, plot_width, plot_height, value_max)
    _draw_series_key(drawing, 330, 213, GREEN, labels["revenue"])
    _draw_series_key(drawing, 420, 213, RED, labels["expenses"])

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
                fontSize=5.8,
                fillColor=colors.HexColor(MUTED),
            )
        )

    for series, color, label_offset in (
        (data["revenue_history"], GREEN, 8),
        (data["expense_history"], RED, -12),
    ):
        points = []
        for index, value in enumerate(series):
            x = plot_x + (plot_width / 2 if count == 1 else index * step)
            y = plot_y + (float(value) / value_max * plot_height)
            points.append((x, y))
        if len(points) > 1:
            drawing.add(
                PolyLine(
                    points,
                    strokeColor=colors.HexColor(color),
                    strokeWidth=2.2,
                )
            )
        for (x, y), value in zip(points, series):
            drawing.add(
                Circle(
                    x,
                    y,
                    3.2,
                    fillColor=colors.white,
                    strokeColor=colors.HexColor(color),
                    strokeWidth=1.8,
                )
            )
            drawing.add(
                String(
                    x,
                    y + label_offset,
                    _chart_money(value),
                    textAnchor="middle",
                    fontName="Helvetica-Bold",
                    fontSize=5.8,
                    fillColor=colors.HexColor(color),
                )
            )
    return drawing


def _category_chart(data, labels):
    positive_rows = [
        (name, value) for name, value in data["category_totals"] if value > 0
    ]
    if not positive_rows:
        return _empty_chart(labels)
    visible = positive_rows[:6]
    if len(positive_rows) > 6:
        visible.append(
            (
                labels["other"],
                sum((row[1] for row in positive_rows[6:]), Decimal("0.00")),
            )
        )
    drawing = _chart_frame(210)
    pie = Pie()
    pie.x, pie.y, pie.width, pie.height = 32, 34, 160, 160
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
            112,
            114,
            37,
            fillColor=colors.white,
            strokeColor=colors.white,
        )
    )
    drawing.add(
        String(
            112,
            116,
            _chart_money(sum(value for _name, value in visible)),
            textAnchor="middle",
            fontName="Helvetica-Bold",
            fontSize=10,
            fillColor=colors.HexColor(NAVY),
        )
    )
    drawing.add(
        String(
            112,
            103,
            "MAD",
            textAnchor="middle",
            fontName="Helvetica",
            fontSize=6,
            fillColor=colors.HexColor(MUTED),
        )
    )
    total = sum(value for _name, value in visible)
    for index, (color, name, value) in enumerate(color_pairs):
        y = 183 - (index * 24)
        percentage = (value / total * 100) if total else Decimal("0")
        drawing.add(
            Rect(
                226,
                y - 2,
                8,
                8,
                rx=2,
                ry=2,
                fillColor=color,
                strokeColor=None,
            )
        )
        drawing.add(
            String(
                241,
                y,
                _short(name, 27),
                fontName="Helvetica-Bold",
                fontSize=7,
                fillColor=colors.HexColor(NAVY),
            )
        )
        drawing.add(
            String(
                495,
                y,
                f"{_money(value)} MAD  |  {percentage:.1f}%",
                textAnchor="end",
                fontName="Helvetica",
                fontSize=7,
                fillColor=colors.HexColor(MUTED),
            )
        )
    return drawing


def _project_chart(data, labels, single_project):
    rows = data["project_rows"]
    if not rows:
        return _empty_chart(labels)
    if not single_project:
        rows = sorted(
            rows, key=lambda row: row["revenue"] + row["expenses"], reverse=True
        )[:8]
    drawing = _chart_frame(230)
    plot_x, plot_y, plot_width, plot_height = 52, 60, 448, 115
    values = [float(row["revenue"]) for row in rows] + [
        float(row["expenses"]) for row in rows
    ]
    value_max = _nice_max(max([1, *values]) * 1.2)
    _draw_value_axis(drawing, plot_x, plot_y, plot_width, plot_height, value_max)
    _draw_series_key(drawing, 330, 212, GREEN, labels["revenue"])
    _draw_series_key(drawing, 420, 212, RED, labels["expenses"])

    group_width = plot_width / len(rows)
    bar_width = min(20, group_width * 0.28)
    for index, row in enumerate(rows):
        center_x = plot_x + ((index + 0.5) * group_width)
        for value, color, x in (
            (float(row["revenue"]), GREEN, center_x - bar_width - 1),
            (float(row["expenses"]), RED, center_x + 1),
        ):
            bar_height = value / value_max * plot_height
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
            drawing.add(
                String(
                    x + (bar_width / 2),
                    plot_y + bar_height + 5,
                    _chart_money(value),
                    textAnchor="middle",
                    fontName="Helvetica-Bold",
                    fontSize=5.8,
                    fillColor=colors.HexColor(color),
                )
            )
        drawing.add(
            String(
                center_x,
                44,
                _short(row["project"].nom, 15),
                textAnchor="middle",
                fontName="Helvetica",
                fontSize=5.8,
                fillColor=colors.HexColor(MUTED),
            )
        )
    return drawing


def _chart_frame(height):
    drawing = Drawing(520, height)
    drawing.add(
        Rect(
            0,
            0,
            520,
            height - 2,
            rx=8,
            ry=8,
            fillColor=colors.white,
            strokeColor=colors.HexColor(BORDER),
            strokeWidth=0.6,
        )
    )
    return drawing


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
                strokeColor=colors.HexColor("#e2e8f0"),
                strokeWidth=0.45,
            )
        )
        drawing.add(
            String(
                x - 7,
                line_y - 2,
                _chart_money(value),
                textAnchor="end",
                fontName="Helvetica",
                fontSize=5.8,
                fillColor=colors.HexColor(MUTED),
            )
        )
    drawing.add(
        String(
            x,
            y + height + 9,
            "MAD",
            fontName="Helvetica-Bold",
            fontSize=6,
            fillColor=colors.HexColor(MUTED),
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
            fontSize=6.5,
            fillColor=colors.HexColor(NAVY),
        )
    )


def _nice_max(value):
    if value <= 0:
        return 1
    magnitude = 10 ** math.floor(math.log10(value))
    normalized = value / magnitude
    nice = (
        1 if normalized <= 1 else 2 if normalized <= 2 else 5 if normalized <= 5 else 10
    )
    return nice * magnitude


def _summary_table(data, labels, width, styles):
    headers = [
        labels["project"],
        labels["client"],
        labels["status"],
        labels["revenue"],
        labels["expenses"],
    ]
    rows = [[Paragraph(_text(value), styles["SmallHeader"]) for value in headers]]
    for item in data["project_rows"]:
        project = item["project"]
        client_name = project.client.nom if project.client else project.nom_client
        rows.append(
            [
                Paragraph(_text(project.nom), styles["Small"]),
                Paragraph(_text(client_name or "-"), styles["Small"]),
                Paragraph(_text(project.status), styles["Small"]),
                Paragraph(_money(item["revenue"]), styles["SmallRight"]),
                Paragraph(_money(item["expenses"]), styles["SmallRight"]),
            ]
        )
    if len(rows) == 1:
        rows.append([Paragraph(labels["no_data"], styles["Small"]), "", "", "", ""])
    table = Table(
        rows,
        colWidths=[width * value for value in (0.25, 0.24, 0.17, 0.17, 0.17)],
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor(BORDER)),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor(SOFT_BG)],
                ),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


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

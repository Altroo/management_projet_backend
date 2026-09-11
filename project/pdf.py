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
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.graphics.charts.legends import Legend
    from reportlab.graphics.charts.linecharts import HorizontalLineChart
    from reportlab.graphics.charts.piecharts import Pie
    from reportlab.graphics.shapes import Drawing, Rect, String
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
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=margin,
        leftMargin=margin,
        topMargin=0.75 * cm,
        bottomMargin=1.35 * cm,
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
                labels["timeline"], _timeline_chart(report_data, labels), styles
            ),
            Spacer(1, 0.35 * cm),
            _chart_section(
                labels["categories"], _category_chart(report_data, labels), styles
            ),
            Spacer(1, 0.35 * cm),
            _chart_section(
                labels["project_comparison"] if project else labels["comparison"],
                _project_chart(report_data, labels, project is not None),
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

    generated_at = timezone.localtime(timezone.now())
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

    use_days = (end - start).days <= 31
    revenue_totals = defaultdict(lambda: Decimal("0.00"))
    expense_totals = defaultdict(lambda: Decimal("0.00"))
    bucket_key = (
        (lambda value: value) if use_days else (lambda value: (value.year, value.month))
    )
    for row in revenues:
        revenue_totals[bucket_key(row.date)] += row.montant
    for row in expenses:
        expense_totals[bucket_key(row.date)] += row.montant

    buckets = []
    if use_days:
        current = start
        while current <= end:
            buckets.append(current)
            current += timedelta(days=1)
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

    if use_days:
        date_format = "%d/%m" if language == "fr" else "%m/%d"
        display_labels = [bucket.strftime(date_format) for bucket in buckets]
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
            fontSize=11,
            leading=14,
            textColor=colors.HexColor(NAVY),
        )
    )
    styles.add(
        ParagraphStyle(
            "Meta",
            parent=styles["Normal"],
            fontSize=7.6,
            leading=9.5,
            textColor=colors.HexColor(MUTED),
        )
    )
    styles.add(
        ParagraphStyle(
            "ReportTitle",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=19,
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
    company, scope_name, date_from, date_to, labels, language, width, styles
):
    contact_parts = [
        company.adresse,
        company.telephone,
        company.email,
        company.site_web,
    ]
    legal_parts = [
        f"ICE: {company.ICE}" if company.ICE else None,
        f"RC: {company.registre_de_commerce}" if company.registre_de_commerce else None,
        f"IF: {company.identifiant_fiscal}" if company.identifiant_fiscal else None,
        f"CNSS: {company.CNSS}" if company.CNSS else None,
    ]
    details = [part for part in contact_parts + legal_parts if part]
    company_block = Paragraph(
        f"<b>{_text(company.raison_sociale)}</b>"
        + (
            f"<br/><font color='{MUTED}'>{'<br/>'.join(_text(part) for part in details)}</font>"
            if details
            else ""
        ),
        styles["CompanyName"],
    )
    period = _period_label(date_from, date_to, labels, language)
    report_block = Paragraph(
        f"{labels['title']}<br/><font size='8' color='{MUTED}'>"
        f"{_text(labels['scope'])}: {_text(scope_name)}<br/>"
        f"{_text(labels['period'])}: {_text(period)}</font>",
        styles["ReportTitle"],
    )
    table = Table(
        [[_logo(company), company_block, report_block]],
        colWidths=[width * 0.15, width * 0.42, width * 0.43],
    )
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LINEBELOW", (0, 0), (-1, -1), 1.1, colors.HexColor(ACCENT)),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def _logo(company):
    if company.logo:
        try:
            if os.path.exists(company.logo.path):
                image = Image(company.logo.path)
                image._restrictSize(2.4 * cm, 1.7 * cm)
                return image
        except (AttributeError, OSError, ValueError):
            pass
    drawing = Drawing(64, 44)
    drawing.add(
        Rect(
            0,
            0,
            44,
            44,
            rx=8,
            ry=8,
            fillColor=colors.HexColor(ACCENT),
            strokeColor=None,
        )
    )
    drawing.add(
        String(
            22,
            17,
            "EBH",
            textAnchor="middle",
            fontName="Helvetica-Bold",
            fontSize=12,
            fillColor=colors.white,
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
            f"<font size='8' color='{MUTED}'>{_text(labels['total_revenue'])}</font><br/><font color='{GREEN}'>{_money(data['total_revenue'])} MAD</font>",
            styles["Kpi"],
        ),
        Paragraph(
            f"<font size='8' color='{MUTED}'>{_text(labels['total_expenses'])}</font><br/><font color='{RED}'>{_money(data['total_expenses'])} MAD</font>",
            styles["Kpi"],
        ),
    ]
    table = Table([cells], colWidths=[width / 2] * 2)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(SOFT_BG)),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor(BORDER)),
                ("INNERGRID", (0, 0), (-1, -1), 0.45, colors.HexColor(BORDER)),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    return table


def _chart_section(title, chart, styles):
    return KeepTogether(
        [Paragraph(title, styles["SectionTitle"]), Spacer(1, 0.08 * cm), chart]
    )


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
            strokeDashArray=[4, 3],
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
    drawing = Drawing(520, 220)
    chart = HorizontalLineChart()
    chart.x, chart.y, chart.width, chart.height = 45, 45, 450, 140
    chart.data = [tuple(data["revenue_history"]), tuple(data["expense_history"])]
    chart.categoryAxis.categoryNames = data["bucket_labels"]
    chart.categoryAxis.labels.fontName = "Helvetica"
    chart.categoryAxis.labels.fontSize = 6
    chart.categoryAxis.labels.angle = 35
    chart.categoryAxis.labels.boxAnchor = "ne"
    values = data["revenue_history"] + data["expense_history"]
    chart.valueAxis.valueMin = min([0, *values])
    chart.valueAxis.valueMax = max([1, *values]) * 1.12
    chart.valueAxis.labels.fontSize = 6.5
    chart.lines[0].strokeColor = colors.HexColor(GREEN)
    chart.lines[0].strokeWidth = 2
    chart.lines[1].strokeColor = colors.HexColor(RED)
    chart.lines[1].strokeWidth = 2
    drawing.add(chart)
    drawing.add(
        _legend(
            [
                (colors.HexColor(GREEN), labels["revenue"]),
                (colors.HexColor(RED), labels["expenses"]),
            ],
            335,
            205,
        )
    )
    return drawing


def _category_chart(data, labels):
    positive_rows = [
        (name, value) for name, value in data["category_totals"] if value > 0
    ]
    if not positive_rows:
        return _empty_chart(labels)
    visible = positive_rows[:7]
    if len(positive_rows) > 7:
        visible.append(
            ("...", sum((row[1] for row in positive_rows[7:]), Decimal("0.00")))
        )
    drawing = Drawing(520, 210)
    pie = Pie()
    pie.x, pie.y, pie.width, pie.height = 65, 28, 155, 155
    pie.data = [float(value) for _name, value in visible]
    pie.labels = None
    pie.slices.strokeColor = colors.white
    pie.slices.strokeWidth = 1
    color_pairs = []
    for index, (name, _value) in enumerate(visible):
        color = colors.HexColor(PALETTE[index % len(PALETTE)])
        pie.slices[index].fillColor = color
        color_pairs.append((color, name))
    drawing.add(pie)
    drawing.add(_legend(color_pairs, 270, 175, column_max=8))
    return drawing


def _project_chart(data, labels, single_project):
    rows = data["project_rows"]
    if not rows:
        return _empty_chart(labels)
    if not single_project:
        rows = sorted(
            rows, key=lambda row: row["revenue"] + row["expenses"], reverse=True
        )[:10]
    drawing = Drawing(520, 225)
    chart = VerticalBarChart()
    chart.x, chart.y, chart.width, chart.height = 45, 48, 450, 135
    chart.data = [
        tuple(float(row["revenue"]) for row in rows),
        tuple(float(row["expenses"]) for row in rows),
    ]
    chart.categoryAxis.categoryNames = [_short(row["project"].nom, 18) for row in rows]
    chart.categoryAxis.labels.fontName = "Helvetica"
    chart.categoryAxis.labels.fontSize = 6
    chart.categoryAxis.labels.angle = 30 if len(rows) > 3 else 0
    chart.categoryAxis.labels.boxAnchor = "ne" if len(rows) > 3 else "n"
    values = list(chart.data[0]) + list(chart.data[1])
    chart.valueAxis.valueMin = min([0, *values])
    chart.valueAxis.valueMax = max([1, *values]) * 1.12
    chart.valueAxis.labels.fontSize = 6.5
    chart.bars[0].fillColor = colors.HexColor(GREEN)
    chart.bars[1].fillColor = colors.HexColor(RED)
    chart.barSpacing = 1
    chart.groupSpacing = 8
    drawing.add(chart)
    drawing.add(
        _legend(
            [
                (colors.HexColor(GREEN), labels["revenue"]),
                (colors.HexColor(RED), labels["expenses"]),
            ],
            335,
            210,
        )
    )
    return drawing


def _legend(color_pairs, x, y, column_max=2):
    legend = Legend()
    legend.x, legend.y = x, y
    legend.fontName = "Helvetica"
    legend.fontSize = 7
    legend.dx, legend.dy, legend.deltay = 7, 7, 10
    legend.columnMaximum = column_max
    legend.colorNamePairs = color_pairs
    return legend


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


def _text(value):
    return escape(str(value or "-"))


def _short(value, length):
    value = str(value)
    return value if len(value) <= length else f"{value[: length - 3]}..."

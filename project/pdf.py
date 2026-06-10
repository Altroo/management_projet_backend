from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape

from django.db.models import DecimalField, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from depense.models import Expense
from revenu.models import Revenue

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        KeepTogether,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
except ImportError:  # pragma: no cover - handled by the API view as a validation error.
    REPORTLAB_AVAILABLE = False
else:
    REPORTLAB_AVAILABLE = True


def build_project_report_pdf(project):
    if not REPORTLAB_AVAILABLE:
        raise ImportError("ReportLab is required to generate project PDF reports.")

    margin = 0.9 * cm
    page_width, _page_height = A4
    content_width = page_width - (2 * margin)
    accent = colors.HexColor("#1d4ed8")
    navy = colors.HexColor("#0f172a")
    border = colors.HexColor("#cbd5e1")
    muted = colors.HexColor("#64748b")
    soft_bg = colors.HexColor("#f8fafc")

    styles = _styles(
        accent,
        navy,
        muted,
        colors,
        ParagraphStyle,
        getSampleStyleSheet,
        TA_CENTER,
        TA_RIGHT,
    )
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=margin,
        leftMargin=margin,
        topMargin=0.85 * cm,
        bottomMargin=1.35 * cm,
        title=f"Rapport projet - {project.nom}",
        author="E.B.H Gestion Projet",
    )

    revenues = Revenue.objects.filter(project=project).order_by("date", "id")
    expenses = (
        Expense.objects.filter(project=project)
        .select_related("category", "sous_categorie", "supplier")
        .order_by("date", "id")
    )
    schedules = project.payment_schedules.all().order_by("due_date", "id")
    real_budget_entries = project.real_budget_entries.all().order_by("date", "id")

    revenue_total = revenues.aggregate(
        total=Coalesce(Sum("montant"), 0, output_field=DecimalField())
    )["total"]
    expense_total = expenses.aggregate(
        total=Coalesce(Sum("montant"), 0, output_field=DecimalField())
    )["total"]
    service_fee_total = sum(
        (expense.frais_de_service_montant for expense in expenses if expense.frais_de_service),
        Decimal("0.00"),
    )
    expected_total = schedules.aggregate(
        total=Coalesce(Sum("expected_amount"), 0, output_field=DecimalField())
    )["total"]
    real_budget_revenue = real_budget_entries.aggregate(
        total=Coalesce(Sum("montant_client"), 0, output_field=DecimalField())
    )["total"]
    real_budget_cost = real_budget_entries.aggregate(
        total=Coalesce(Sum("montant_fournisseur"), 0, output_field=DecimalField())
    )["total"]
    real_budget_profit = real_budget_revenue - real_budget_cost
    real_budget_margin = (
        round((real_budget_profit / real_budget_revenue) * 100, 2)
        if real_budget_revenue
        else 0
    )
    budget_gap = project.budget_total - real_budget_cost
    profit = revenue_total - expense_total
    margin_pct = round((profit / revenue_total) * 100, 2) if revenue_total else 0
    budget_usage = (
        round((expense_total / project.budget_total) * 100, 2)
        if project.budget_total
        else 0
    )
    generated_at = timezone.localtime(timezone.now()).strftime("%d/%m/%Y %H:%M")

    story = [
        _build_header(
            project=project,
            generated_at=generated_at,
            content_width=content_width,
            styles=styles,
            colors=colors,
            accent=accent,
            soft_bg=soft_bg,
        ),
        Spacer(1, 0.35 * cm),
        _build_project_client_grid(
            project=project,
            content_width=content_width,
            styles=styles,
            colors=colors,
            accent=accent,
        ),
        Spacer(1, 0.35 * cm),
        _build_kpi_grid(
            [
                ("Budget initial", f"{_money(project.budget_total)} MAD"),
                ("Revenus reçus", f"{_money(revenue_total)} MAD"),
                ("Dépenses", f"{_money(expense_total)} MAD"),
                ("Bénéfice", f"{_money(profit)} MAD"),
                ("Marge", f"{margin_pct}%"),
            ],
            content_width,
            styles,
            colors,
            soft_bg,
            border,
        ),
        Spacer(1, 0.22 * cm),
        _build_kpi_grid(
            [
                ("Coût réel", f"{_money(real_budget_cost)} MAD"),
                ("Revenu par étape", f"{_money(real_budget_revenue)} MAD"),
                ("Marge réelle", f"{_money(real_budget_profit)} MAD"),
                ("Taux marge réelle", f"{real_budget_margin}%"),
                ("Écart budget", f"{_money(budget_gap)} MAD"),
            ],
            content_width,
            styles,
            colors,
            soft_bg,
            border,
        ),
        Spacer(1, 0.45 * cm),
    ]

    story.extend(
        _section(
            "Échéancier de paiements",
            _build_schedule_table(
                schedules=schedules,
                project=project,
                content_width=content_width,
                styles=styles,
                colors=colors,
                navy=navy,
                accent=accent,
                border=border,
            ),
            styles,
            accent,
            cm,
        )
    )
    story.append(Spacer(1, 0.35 * cm))
    story.extend(
        _section(
            "Budget réel par étape",
            _build_real_budget_table(
                entries=real_budget_entries,
                content_width=content_width,
                styles=styles,
                colors=colors,
                navy=navy,
                accent=accent,
                border=border,
            ),
            styles,
            accent,
            cm,
        )
    )
    story.append(Spacer(1, 0.35 * cm))
    story.extend(
        _section(
            "Revenus réels reçus",
            _build_revenue_table(revenues, content_width, styles, colors, navy, accent, border),
            styles,
            accent,
            cm,
        )
    )
    story.append(Spacer(1, 0.22 * cm))
    story.extend(
        _section(
            "Suivi complémentaire",
            _build_kpi_grid(
                [
                    ("Budget utilisé", f"{budget_usage}%"),
                    ("Échéancier prévu", f"{_money(expected_total)} MAD"),
                    ("Écart prévisionnel", f"{_money(revenue_total - expected_total)} MAD"),
                    ("Frais de service", f"{_money(service_fee_total)} MAD"),
                    ("Pièces projet", str(project.attachments.count())),
                ],
                content_width,
                styles,
                colors,
                soft_bg,
                border,
            ),
            styles,
            accent,
            cm,
        )
    )
    story.append(Spacer(1, 0.35 * cm))
    story.extend(
        _section(
            "Dépenses du projet",
            _build_expense_table(expenses, content_width, styles, colors, navy, accent, border),
            styles,
            accent,
            cm,
        )
    )

    if project.notes:
        story.extend(
            [
                Spacer(1, 0.35 * cm),
                KeepTogether(
                    [
                        Paragraph("Notes", styles["SectionTitle"]),
                        _line_table(content_width, accent, colors),
                        Spacer(1, 0.12 * cm),
                        Paragraph(_pdf_text(project.notes), styles["Body"]),
                    ]
                ),
            ]
        )

    footer = _footer("Rapport projet")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    return buffer


def _build_header(project, generated_at, content_width, styles, colors, accent, soft_bg):
    left = Paragraph(
        "E.B.H<br/>Gestion Projet<br/><font color='#64748b'>Compte rendu client</font>",
        styles["Brand"],
    )
    right = Paragraph(
        f"RAPPORT PROJET<br/><font size='8' color='#64748b'>RP-{project.id:05d} · Généré le {generated_at}</font>",
        styles["ReportTitle"],
    )
    table = Table([[left, right]], colWidths=[content_width * 0.36, content_width * 0.64])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BACKGROUND", (0, 0), (0, 0), soft_bg),
                ("LINEBELOW", (0, 0), (-1, -1), 1.1, accent),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    return table


def _build_project_client_grid(project, content_width, styles, colors, accent):
    client = project.client
    client_name = client.nom if client else project.nom_client
    client_phone = client.telephone if client else project.telephone_client
    client_email = client.email if client else project.email_client
    client_address = client.adresse if client else None

    project_rows = [
        ["Projet", project.nom],
        ["Statut", project.status],
        ["Chef de projet", project.chef_de_projet or "-"],
        ["Début", _date(project.date_debut)],
        ["Fin prévue", _date(project.date_fin)],
    ]
    client_rows = [
        ["Client", client_name or "-"],
        ["Téléphone", client_phone or "-"],
        ["Email", client_email or "-"],
        ["Adresse", client_address or "-"],
    ]
    left = _info_block("PROJET", project_rows, content_width * 0.48, styles, colors, accent)
    right = _info_block("CLIENT", client_rows, content_width * 0.48, styles, colors, accent)
    table = Table([[left, right]], colWidths=[content_width * 0.5, content_width * 0.5])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return table


def _info_block(title, rows, width, styles, colors, accent):
    content = [[Paragraph(title, styles["SectionTitle"])]]
    content.append([_line_table(width, accent, colors)])
    for label, value in rows:
        content.append(
            [
                Paragraph(
                    f"<b>{_pdf_text(label)}</b><br/>{_pdf_text(value)}",
                    styles["Meta"],
                )
            ]
        )
    table = Table(content, colWidths=[width])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return table


def _build_kpi_grid(items, content_width, styles, colors, soft_bg, border):
    cells = [
        Paragraph(f"<font color='#64748b'>{_pdf_text(label)}</font><br/><b>{_pdf_text(value)}</b>", styles["KpiValue"])
        for label, value in items
    ]
    table = Table([cells], colWidths=[content_width / len(cells)] * len(cells))
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), soft_bg),
                ("BOX", (0, 0), (-1, -1), 0.45, border),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#e5e7eb")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def _styles(
    accent,
    navy,
    muted,
    colors,
    ParagraphStyle,
    getSampleStyleSheet,
    TA_CENTER,
    TA_RIGHT,
):
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            "Brand",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=navy,
        )
    )
    styles.add(
        ParagraphStyle(
            "ReportTitle",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=accent,
            alignment=TA_RIGHT,
        )
    )
    styles.add(
        ParagraphStyle(
            "Meta",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            textColor=muted,
        )
    )
    styles.add(
        ParagraphStyle(
            "MetaRight",
            parent=styles["Meta"],
            alignment=TA_RIGHT,
        )
    )
    styles.add(
        ParagraphStyle(
            "SectionTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=13,
            textColor=navy,
        )
    )
    styles.add(
        ParagraphStyle(
            "Body",
            parent=styles["Normal"],
            fontSize=8.2,
            leading=10.5,
            textColor=colors.HexColor("#111827"),
        )
    )
    styles.add(
        ParagraphStyle(
            "Small",
            parent=styles["Normal"],
            fontSize=7.4,
            leading=9.2,
            textColor=colors.HexColor("#111827"),
        )
    )
    styles.add(
        ParagraphStyle(
            "SmallCenter",
            parent=styles["Small"],
            alignment=TA_CENTER,
        )
    )
    styles.add(
        ParagraphStyle(
            "SmallRight",
            parent=styles["Small"],
            alignment=TA_RIGHT,
        )
    )
    styles.add(
        ParagraphStyle(
            "HeaderCell",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.4,
            leading=9,
            textColor=colors.white,
        )
    )
    styles.add(
        ParagraphStyle(
            "KpiLabel",
            parent=styles["Normal"],
            fontSize=7.4,
            leading=9,
            textColor=muted,
        )
    )
    styles.add(
        ParagraphStyle(
            "KpiValue",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=12,
            textColor=navy,
        )
    )
    return styles


def _section(title, table, styles, accent, cm):
    return [
        KeepTogether(
            [
                Paragraph(title, styles["SectionTitle"]),
                Spacer(1, 0.06 * cm),
            ]
        ),
        table,
    ]


def _build_schedule_table(schedules, project, content_width, styles, colors, navy, accent, border):
    headers = ["Date prévue", "Description", "Prévu", "Cumul prévu", "Cumul encaissé", "Écart"]
    rows = [[Paragraph(f"<b>{header}</b>", styles["HeaderCell"]) for header in headers]]
    expected_cumulative = Decimal("0.00")
    if schedules:
        from revenu.models import Revenue

        for schedule in schedules:
            expected_cumulative += schedule.expected_amount
            actual_cumulative = Revenue.objects.filter(
                project=project,
                date__lte=schedule.due_date,
            ).aggregate(total=Coalesce(Sum("montant"), 0, output_field=DecimalField()))[
                "total"
            ]
            variance = actual_cumulative - expected_cumulative
            rows.append(
                [
                    Paragraph(_date(schedule.due_date), styles["Small"]),
                    Paragraph(_pdf_text(schedule.description or "-"), styles["Small"]),
                    Paragraph(_money(schedule.expected_amount), styles["SmallRight"]),
                    Paragraph(_money(expected_cumulative), styles["SmallRight"]),
                    Paragraph(_money(actual_cumulative), styles["SmallRight"]),
                    Paragraph(_money(variance), styles["SmallRight"]),
                ]
            )
    else:
        rows.append(
            [
                Paragraph("-", styles["Small"]),
                Paragraph("Aucune échéance définie.", styles["Small"]),
                "",
                "",
                "",
                "",
            ]
        )
    return _data_table(rows, [0.16, 0.28, 0.14, 0.14, 0.15, 0.13], content_width, colors, navy, accent, border)


def _build_real_budget_table(entries, content_width, styles, colors, navy, accent, border):
    headers = ["Date", "Étape", "Description", "Client", "Fournisseur", "Marge", "Taux"]
    rows = [[Paragraph(f"<b>{header}</b>", styles["HeaderCell"]) for header in headers]]
    if entries:
        for entry in entries:
            rows.append(
                [
                    Paragraph(_date(entry.date), styles["Small"]),
                    Paragraph(_pdf_text(entry.stage), styles["Small"]),
                    Paragraph(_pdf_text(entry.description or "-"), styles["Small"]),
                    Paragraph(_money(entry.montant_client), styles["SmallRight"]),
                    Paragraph(_money(entry.montant_fournisseur), styles["SmallRight"]),
                    Paragraph(_money(entry.benefice), styles["SmallRight"]),
                    Paragraph(f"{entry.marge}%", styles["SmallRight"]),
                ]
            )
    else:
        rows.append(
            [
                Paragraph("-", styles["Small"]),
                Paragraph("Aucune ligne de budget réel enregistrée.", styles["Small"]),
                "",
                "",
                "",
                "",
                "",
            ]
        )
    return _data_table(rows, [0.11, 0.18, 0.25, 0.12, 0.14, 0.12, 0.08], content_width, colors, navy, accent, border)


def _build_revenue_table(revenues, content_width, styles, colors, navy, accent, border):
    headers = ["Date", "Description", "Montant", "Notes"]
    rows = [[Paragraph(f"<b>{header}</b>", styles["HeaderCell"]) for header in headers]]
    if revenues:
        for revenue in revenues:
            rows.append(
                [
                    Paragraph(_date(revenue.date), styles["Small"]),
                    Paragraph(_pdf_text(revenue.description), styles["Small"]),
                    Paragraph(_money(revenue.montant), styles["SmallRight"]),
                    Paragraph(_pdf_text(revenue.notes or "-"), styles["Small"]),
                ]
            )
    else:
        rows.append(
            [
                Paragraph("-", styles["Small"]),
                Paragraph("Aucun revenu enregistré.", styles["Small"]),
                "",
                "",
            ]
        )
    return _data_table(rows, [0.16, 0.42, 0.18, 0.24], content_width, colors, navy, accent, border)


def _build_expense_table(expenses, content_width, styles, colors, navy, accent, border):
    headers = ["Date", "Catégorie", "Description", "Fournisseur", "Montant", "Frais"]
    rows = [[Paragraph(f"<b>{header}</b>", styles["HeaderCell"]) for header in headers]]
    if expenses:
        for expense in expenses:
            category = expense.category.name if expense.category else "-"
            if expense.sous_categorie:
                category = f"{category}<br/><font color='#64748b'>{expense.sous_categorie.name}</font>"
            supplier = expense.supplier.nom if expense.supplier else "-"
            rows.append(
                [
                    Paragraph(_date(expense.date), styles["Small"]),
                    Paragraph(category, styles["Small"]),
                    Paragraph(_pdf_text(expense.description), styles["Small"]),
                    Paragraph(_pdf_text(supplier or "-"), styles["Small"]),
                    Paragraph(_money(expense.montant), styles["SmallRight"]),
                    Paragraph(_money(expense.frais_de_service_montant), styles["SmallRight"]),
                ]
            )
    else:
        rows.append(
            [
                Paragraph("-", styles["Small"]),
                Paragraph("-", styles["Small"]),
                Paragraph("Aucune dépense enregistrée.", styles["Small"]),
                "",
                "",
                "",
            ]
        )
    return _data_table(rows, [0.12, 0.22, 0.28, 0.17, 0.12, 0.09], content_width, colors, navy, accent, border)


def _data_table(rows, weights, content_width, colors, navy, accent, border):
    col_widths = [content_width * weight for weight in weights]
    table = Table(rows, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), navy),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.25, border),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("LINEBELOW", (0, 0), (-1, 0), 1, accent),
                ("ALIGN", (-1, 1), (-1, -1), "RIGHT"),
            ]
        )
    )
    return table


def _line_table(width, accent, colors):
    table = Table([[""]], colWidths=[width])
    table.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.8, accent)]))
    return table


def _footer(title):
    def _draw(canvas, doc):
        from reportlab.lib import colors
        from reportlab.lib.units import cm

        canvas.saveState()
        width, _height = doc.pagesize
        canvas.setStrokeColor(colors.HexColor("#d1d5db"))
        canvas.setLineWidth(0.5)
        canvas.line(doc.leftMargin, 1.0 * cm, width - doc.rightMargin, 1.0 * cm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(doc.leftMargin, 0.55 * cm, "E.B.H Gestion Projet")
        canvas.drawCentredString(width / 2, 0.55 * cm, title)
        canvas.drawRightString(width - doc.rightMargin, 0.55 * cm, f"Page {canvas.getPageNumber()}")
        canvas.restoreState()

    return _draw


def _date(value):
    return value.strftime("%d/%m/%Y") if value else "-"


def _money(value):
    amount = value if value is not None else Decimal("0.00")
    return f"{amount:,.2f}".replace(",", " ").replace(".", ",")


def _pdf_text(value):
    return escape(str(value if value is not None else "-"), {"'": "&apos;", '"': "&quot;"})

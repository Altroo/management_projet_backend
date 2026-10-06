"""Allowlisted public column ordering, before pagination or list serialization."""

from decimal import Decimal
from django.db.models import (
    Case,
    CharField,
    Count,
    DecimalField,
    ExpressionWrapper,
    F,
    FloatField,
    OuterRef,
    Q,
    Subquery,
    Sum,
    TextField,
    Value,
    When,
)
from django.db.models.functions import (
    Cast,
    Coalesce,
    Concat,
    Greatest,
    Lower,
    NullIf,
    Round,
    Trim,
)


def direct(names):
    return {name: F(name) for name in names.split()}


def user_name(prefix):
    return Coalesce(
        NullIf(
            Trim(
                Concat(
                    F(f"{prefix}__first_name"), Value(" "), F(f"{prefix}__last_name")
                )
            ),
            Value(""),
        ),
        F(f"{prefix}__email"),
        output_field=CharField(),
    )


def scalar(queryset, aggregate):
    return Coalesce(
        Subquery(
            queryset.order_by()
            .values(_group=Value(1))
            .annotate(total=aggregate)
            .values("total")[:1]
        ),
        Value(0),
        output_field=DecimalField(max_digits=20, decimal_places=2),
    )


def percentage(numerator, denominator, factor=100):
    value = (
        Cast(numerator, FloatField())
        * Value(float(factor))
        / NullIf(Cast(denominator, FloatField()), Value(0.0))
    )
    return Round(Cast(value, DecimalField(max_digits=20, decimal_places=4)), 2)


def fields_for(queryset, field, params):
    model = queryset.model._meta.label_lower
    fields = {
        "accounts.customuser": direct(
            "first_name last_name email gender is_staff is_active date_joined last_login"
        )
    }
    fields.update(
        {
            "project.project": {
                **direct("nom status budget_total date_debut date_fin chef_de_projet"),
                "created_by_user_name": user_name("created_by_user"),
            },
            "project.category": {
                **direct("name date_created"),
                "created_by_user_name": user_name("created_by_user"),
            },
            "project.client": direct("nom telephone email ville"),
            "project.supplier": direct("nom contact specialite"),
            "revenu.revenue": {
                **direct("description montant date"),
                "project_name": F("project__nom"),
                "created_by_user_name": user_name("created_by_user"),
            },
            "depense.expense": {
                **direct("description montant date"),
                "project_name": F("project__nom"),
                "category_name": F("category__name"),
                "supplier_name": F("supplier__nom"),
                "created_by_user_name": user_name("created_by_user"),
            },
            "devis.quote": {
                **direct("number status description amount_ttc date"),
                "project_name": F("project__nom"),
                "category_name": F("category__name"),
                "supplier_name": F("supplier__nom"),
                "created_by_user_name": user_name("created_by_user"),
            },
        }
    )
    if model == "project.client":
        from project.models import Project
        from revenu.models import Revenue

        projects = Project.objects.filter(
            Q(client_id=OuterRef("pk")) | Q(nom_client__iexact=OuterRef("nom"))
        )
        revenues = Revenue.objects.filter(
            Q(project__client_id=OuterRef("pk"))
            | Q(project__nom_client__iexact=OuterRef("nom"))
        )
        fields[model].update(
            projects_count=scalar(projects, Count("pk", distinct=True)),
            total_encaisse=scalar(revenues, Sum("montant")),
        )
    if model == "project.supplier":
        from depense.models import Expense

        expenses = Expense.objects.filter(supplier_id=OuterRef("pk"))
        fields[model].update(
            total_paid=scalar(expenses, Sum("montant")),
            payments_count=scalar(expenses, Count("pk")),
        )
    if model == "devis.quote":
        if "spent" not in queryset.query.annotations:
            queryset = queryset.annotate(
                spent=Coalesce(
                    Sum("expenses__montant"),
                    Value(Decimal("0")),
                    output_field=DecimalField(max_digits=20, decimal_places=2),
                )
            )
        fields[model].update(
            spent=F("spent"),
            remaining=Greatest(F("amount_ttc") - F("spent"), Value(Decimal("0"))),
            consumption_percent=percentage(F("spent"), F("amount_ttc")),
        )
    return queryset, fields.get(model, {})


def apply_list_ordering(queryset, params):
    ordering = params.get("ordering", "")
    if not ordering or not hasattr(queryset, "model"):
        return queryset
    descending = ordering.startswith("-")
    field = ordering[1:] if descending else ordering
    queryset, fields = fields_for(queryset, field, params)
    expression = fields.get(field)
    if expression is None:
        return queryset
    resolved = expression.resolve_expression(queryset.query)
    if isinstance(resolved.output_field, (CharField, TextField)):
        expression = Lower(expression)
    queryset = queryset.alias(_list_ordering_value=expression)
    order = F("_list_ordering_value")
    return queryset.order_by(
        order.desc(nulls_last=True) if descending else order.asc(nulls_last=True),
        "-pk" if descending else "pk",
    )

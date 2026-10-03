from decimal import Decimal
from django.db.models import Sum
from depense.models import Expense
from revenu.models import Revenue
from .models import Quote

ZERO = Decimal("0.00")


def project_estimate_summary(project):
    """Lifetime TTC forecast; actual costs use expense amounts, without service fees."""
    quotes = Quote.objects.filter(project=project, status=Quote.Status.VALIDATED)
    expenses = Expense.objects.filter(project=project)
    estimated = quotes.aggregate(total=Sum("amount_ttc"))["total"] or ZERO
    spent = expenses.aggregate(total=Sum("montant"))["total"] or ZERO
    advances = (
        Revenue.objects.filter(project=project).aggregate(total=Sum("montant"))["total"]
        or ZERO
    )
    groups = {}
    for queryset, amount, target in (
        (quotes, "amount_ttc", "estimated"),
        (expenses, "montant", "spent"),
    ):
        for item in (
            queryset.values(
                "category_id",
                "category__name",
                "sous_categorie_id",
                "sous_categorie__name",
            )
            .annotate(total=Sum(amount))
            .order_by()
        ):
            key = (item["category_id"], item["sous_categorie_id"])
            row = groups.setdefault(
                key,
                {
                    "id": f"{key[0] or 0}-{key[1] or 0}",
                    "category": key[0],
                    "category_name": item["category__name"],
                    "sous_categorie": key[1],
                    "sous_categorie_name": item["sous_categorie__name"],
                    "estimated": ZERO,
                    "spent": ZERO,
                },
            )
            row[target] += item["total"]

    def totals(estimate, actual):
        return {
            "estimated": estimate,
            "spent": actual,
            "variance": estimate - actual,
            "remaining": max(ZERO, estimate - actual),
            "overrun": actual > estimate,
            "consumption_percent": (
                round(actual / estimate * 100, 2) if estimate else None
            ),
        }

    by_category = {}
    for row in groups.values():
        row.update(totals(row["estimated"], row["spent"]))
        category = by_category.setdefault(
            row["category"],
            {
                "id": row["category"] or 0,
                "category": row["category"],
                "category_name": row["category_name"],
                "estimated": ZERO,
                "spent": ZERO,
            },
        )
        category["estimated"] += row["estimated"]
        category["spent"] += row["spent"]
    for row in by_category.values():
        row.update(totals(row["estimated"], row["spent"]))
    return {
        **totals(estimated, spent),
        "validated_count": quotes.count(),
        "advances": advances,
        "unlinked_spent": expenses.filter(quote__isnull=True).aggregate(
            total=Sum("montant")
        )["total"]
        or ZERO,
        "by_category": sorted(
            by_category.values(), key=lambda row: row["category_name"] or ""
        ),
        "by_subcategory": sorted(
            groups.values(),
            key=lambda row: (
                row["category_name"] or "",
                row["sous_categorie_name"] or "",
            ),
        ),
    }

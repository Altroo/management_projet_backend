import django_filters
from django.db.models import Q

from .models import Expense


class ExpenseFilter(django_filters.FilterSet):
    """Filter for the Expense model."""

    search = django_filters.CharFilter(method="global_search", label="Recherche")
    project = django_filters.NumberFilter(field_name="project_id")
    category = django_filters.NumberFilter(field_name="category_id")
    sous_categorie = django_filters.NumberFilter(field_name="sous_categorie_id")
    date_after = django_filters.DateFilter(field_name="date", lookup_expr="gte")
    date_before = django_filters.DateFilter(field_name="date", lookup_expr="lte")
    montant = django_filters.NumberFilter(field_name="montant", lookup_expr="exact")
    montant__gt = django_filters.NumberFilter(field_name="montant", lookup_expr="gt")
    montant__gte = django_filters.NumberFilter(field_name="montant", lookup_expr="gte")
    montant__lt = django_filters.NumberFilter(field_name="montant", lookup_expr="lt")
    montant__lte = django_filters.NumberFilter(field_name="montant", lookup_expr="lte")
    supplier = django_filters.NumberFilter(field_name="supplier_id")
    fournisseur = django_filters.CharFilter(method="filter_fournisseur")

    class Meta:
        model = Expense
        fields = [
            "project",
            "category",
            "sous_categorie",
            "date",
            "montant",
            "supplier",
            "fournisseur",
        ]

    def global_search(self, queryset, name, value):  # noqa: ARG002
        return queryset.filter(
            Q(description__icontains=value)
            | Q(supplier__nom__icontains=value)
            | Q(project__nom__icontains=value)
            | Q(element__icontains=value)
        )

    def filter_fournisseur(self, queryset, name, value):  # noqa: ARG002
        return queryset.filter(supplier__nom__icontains=value)

import django_filters
from django.db.models import Q

from .models import Project


class ProjectFilter(django_filters.FilterSet):
    """Filter for the Project model."""

    search = django_filters.CharFilter(method="global_search", label="Recherche")
    status = django_filters.CharFilter(method="filter_status", label="Statut")
    date_debut_after = django_filters.DateFilter(
        field_name="date_debut", lookup_expr="gte"
    )
    date_debut_before = django_filters.DateFilter(
        field_name="date_debut", lookup_expr="lte"
    )
    date_fin_after = django_filters.DateFilter(field_name="date_fin", lookup_expr="gte")
    date_fin_before = django_filters.DateFilter(
        field_name="date_fin", lookup_expr="lte"
    )
    budget_total = django_filters.NumberFilter(
        field_name="budget_total", lookup_expr="exact"
    )
    budget_total__gt = django_filters.NumberFilter(
        field_name="budget_total", lookup_expr="gt"
    )
    budget_total__gte = django_filters.NumberFilter(
        field_name="budget_total", lookup_expr="gte"
    )
    budget_total__lt = django_filters.NumberFilter(
        field_name="budget_total", lookup_expr="lt"
    )
    budget_total__lte = django_filters.NumberFilter(
        field_name="budget_total", lookup_expr="lte"
    )

    class Meta:
        model = Project
        fields = [
            "status",
            "date_debut",
            "date_fin",
            "budget_total",
        ]

    def global_search(self, queryset, name, value):  # noqa: ARG002
        return queryset.filter(
            Q(nom__icontains=value)
            | Q(nom_client__icontains=value)
            | Q(chef_de_projet__icontains=value)
            | Q(email_client__icontains=value)
        )

    def filter_status(self, queryset, name, value):  # noqa: ARG002
        statuses = [s.strip() for s in value.split(",") if s.strip()]
        if statuses:
            return queryset.filter(status__in=statuses)
        return queryset

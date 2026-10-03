import django_filters
from django.db.models import Q
from .models import Quote


class NumberInFilter(django_filters.BaseInFilter, django_filters.NumberFilter):
    pass


class QuoteFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method="global_search")
    project = NumberInFilter(field_name="project_id", lookup_expr="in")
    supplier = NumberInFilter(field_name="supplier_id", lookup_expr="in")
    category = NumberInFilter(field_name="category_id", lookup_expr="in")
    sous_categorie = NumberInFilter(field_name="sous_categorie_id", lookup_expr="in")
    status = django_filters.BaseInFilter(field_name="status", lookup_expr="in")
    date_after = django_filters.DateFilter(field_name="date", lookup_expr="gte")
    date_before = django_filters.DateFilter(field_name="date", lookup_expr="lte")

    class Meta:
        model = Quote
        fields = {"amount_ttc": ["exact", "gt", "gte", "lt", "lte"]}

    def global_search(self, queryset, name, value):
        return queryset.filter(
            Q(number__icontains=value)
            | Q(description__icontains=value)
            | Q(project__nom__icontains=value)
            | Q(supplier__nom__icontains=value)
            | Q(category__name__icontains=value)
            | Q(sous_categorie__name__icontains=value)
        )

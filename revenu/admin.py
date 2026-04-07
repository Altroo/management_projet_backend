from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Revenue


@admin.register(Revenue)
class RevenueAdmin(SimpleHistoryAdmin):
    list_display = ("id", "project", "description", "montant", "date")
    list_filter = ("project",)
    search_fields = ("description",)
    ordering = ("-date",)


class HistoricalRevenueAdmin(admin.ModelAdmin):
    """Read-only admin for viewing historical Revenue records."""

    list_display = (
        "history_id",
        "id",
        "project",
        "description",
        "montant",
        "date",
        "history_type",
        "history_date",
        "history_user",
    )
    list_filter = ("history_type", "history_date")
    search_fields = ("description",)
    readonly_fields = [
        field.name
        for field in Revenue._meta.get_fields()
        if hasattr(field, "name") and not field.many_to_many and not field.one_to_many
    ] + [
        "history_id",
        "history_date",
        "history_change_reason",
        "history_type",
        "history_user",
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


admin.site.register(Revenue.history.model, HistoricalRevenueAdmin)

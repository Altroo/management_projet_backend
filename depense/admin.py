from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Expense, ExpenseAttachment


@admin.register(Expense)
class ExpenseAdmin(SimpleHistoryAdmin):
    list_display = (
        "id",
        "project",
        "description",
        "montant",
        "date",
        "category",
        "supplier",
    )
    list_filter = ("project", "category", "supplier")
    search_fields = ("description", "supplier__nom")
    ordering = ("-date",)


@admin.register(ExpenseAttachment)
class ExpenseAttachmentAdmin(admin.ModelAdmin):
    list_display = ("id", "expense", "label", "uploaded_by_user", "date_created")
    list_filter = ("expense__project",)
    search_fields = ("label", "file", "expense__description")
    ordering = ("-date_created",)


class HistoricalExpenseAdmin(admin.ModelAdmin):
    """Read-only admin for viewing historical Expense records."""

    list_display = (
        "history_id",
        "id",
        "project",
        "description",
        "montant",
        "date",
        "category",
        "history_type",
        "history_date",
        "history_user",
    )
    list_filter = ("history_type", "history_date", "category")
    search_fields = ("description", "supplier__nom")
    readonly_fields = [
        field.name
        for field in Expense._meta.get_fields()
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


admin.site.register(Expense.history.model, HistoricalExpenseAdmin)

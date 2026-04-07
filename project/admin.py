from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Category, SubCategory, Project


@admin.register(Category)
class CategoryAdmin(SimpleHistoryAdmin):
    list_display = ("id", "name", "date_created")
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(SubCategory)
class SubCategoryAdmin(SimpleHistoryAdmin):
    list_display = ("id", "name", "category", "date_created")
    list_filter = ("category",)
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(Project)
class ProjectAdmin(SimpleHistoryAdmin):
    list_display = ("id", "nom", "status", "budget_total", "date_debut", "date_fin")
    list_filter = ("status",)
    search_fields = ("nom", "nom_client")
    ordering = ("-id",)


class HistoricalCategoryAdmin(admin.ModelAdmin):
    """Read-only admin for viewing historical Category records."""

    list_display = (
        "history_id",
        "id",
        "name",
        "history_type",
        "history_date",
        "history_user",
    )
    list_filter = ("history_type", "history_date")
    search_fields = ("name",)
    readonly_fields = [
        field.name
        for field in Category._meta.get_fields()
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


class HistoricalSubCategoryAdmin(admin.ModelAdmin):
    """Read-only admin for viewing historical SubCategory records."""

    list_display = (
        "history_id",
        "id",
        "name",
        "category",
        "history_type",
        "history_date",
        "history_user",
    )
    list_filter = ("history_type", "history_date", "category")
    search_fields = ("name",)
    readonly_fields = [
        field.name
        for field in SubCategory._meta.get_fields()
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


class HistoricalProjectAdmin(admin.ModelAdmin):
    """Read-only admin for viewing historical Project records."""

    list_display = (
        "history_id",
        "id",
        "nom",
        "status",
        "budget_total",
        "date_debut",
        "date_fin",
        "history_type",
        "history_date",
        "history_user",
    )
    list_filter = ("history_type", "history_date", "status")
    search_fields = ("nom", "nom_client")
    readonly_fields = [
        field.name
        for field in Project._meta.get_fields()
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


admin.site.register(Category.history.model, HistoricalCategoryAdmin)
admin.site.register(SubCategory.history.model, HistoricalSubCategoryAdmin)
admin.site.register(Project.history.model, HistoricalProjectAdmin)

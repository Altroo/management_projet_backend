from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import (
    Category,
    Client,
    Project,
    ProjectAttachment,
    ProjectPaymentSchedule,
    ProjectRealBudgetEntry,
    SubCategory,
    Supplier,
)


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


@admin.register(Client)
class ClientAdmin(SimpleHistoryAdmin):
    list_display = ("id", "nom", "telephone", "email", "ville", "date_created")
    search_fields = ("nom", "telephone", "email", "ville", "adresse")
    ordering = ("nom",)


@admin.register(Supplier)
class SupplierAdmin(SimpleHistoryAdmin):
    list_display = ("id", "nom", "contact", "specialite", "date_created")
    search_fields = ("nom", "contact", "specialite")
    ordering = ("nom",)


@admin.register(Project)
class ProjectAdmin(SimpleHistoryAdmin):
    list_display = (
        "id",
        "nom",
        "status",
        "client",
        "budget_total",
        "date_debut",
        "date_fin",
    )
    list_filter = ("status", "client")
    search_fields = ("nom", "nom_client", "ville_client", "client__nom", "client__ville")
    ordering = ("-id",)


@admin.register(ProjectAttachment)
class ProjectAttachmentAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "label", "uploaded_by_user", "date_created")
    list_filter = ("project",)
    search_fields = ("label", "file", "project__nom")
    ordering = ("-date_created",)


@admin.register(ProjectPaymentSchedule)
class ProjectPaymentScheduleAdmin(SimpleHistoryAdmin):
    list_display = ("id", "project", "due_date", "expected_amount", "description")
    list_filter = ("project", "due_date")
    search_fields = ("project__nom", "description")
    ordering = ("due_date", "id")


@admin.register(ProjectRealBudgetEntry)
class ProjectRealBudgetEntryAdmin(SimpleHistoryAdmin):
    list_display = (
        "id",
        "project",
        "date",
        "stage",
        "montant_client",
        "montant_fournisseur",
        "benefice",
        "marge",
    )
    list_filter = ("project", "stage", "date")
    search_fields = ("project__nom", "stage", "description")
    ordering = ("-date", "-id")


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


class HistoricalClientAdmin(admin.ModelAdmin):
    """Read-only admin for viewing historical Client records."""

    list_display = (
        "history_id",
        "id",
        "nom",
        "telephone",
        "email",
        "ville",
        "history_type",
        "history_date",
        "history_user",
    )
    list_filter = ("history_type", "history_date", "ville")
    search_fields = ("nom", "telephone", "email", "ville", "adresse")
    readonly_fields = [
        field.name
        for field in Client._meta.get_fields()
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


class HistoricalSupplierAdmin(admin.ModelAdmin):
    """Read-only admin for viewing historical Supplier records."""

    list_display = (
        "history_id",
        "id",
        "nom",
        "contact",
        "specialite",
        "history_type",
        "history_date",
        "history_user",
    )
    list_filter = ("history_type", "history_date")
    search_fields = ("nom", "contact", "specialite")
    readonly_fields = [
        field.name
        for field in Supplier._meta.get_fields()
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
    search_fields = ("nom", "nom_client", "ville_client")
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


class HistoricalProjectPaymentScheduleAdmin(admin.ModelAdmin):
    """Read-only admin for viewing historical ProjectPaymentSchedule records."""

    list_display = (
        "history_id",
        "id",
        "project",
        "due_date",
        "expected_amount",
        "description",
        "history_type",
        "history_date",
        "history_user",
    )
    list_filter = ("history_type", "history_date", "project", "due_date")
    search_fields = ("project__nom", "description", "notes")
    readonly_fields = [
        field.name
        for field in ProjectPaymentSchedule._meta.get_fields()
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


class HistoricalProjectRealBudgetEntryAdmin(admin.ModelAdmin):
    """Read-only admin for viewing historical ProjectRealBudgetEntry records."""

    list_display = (
        "history_id",
        "id",
        "project",
        "date",
        "stage",
        "montant_client",
        "montant_fournisseur",
        "history_type",
        "history_date",
        "history_user",
    )
    list_filter = ("history_type", "history_date", "project", "stage", "date")
    search_fields = ("project__nom", "stage", "description", "notes")
    readonly_fields = [
        field.name
        for field in ProjectRealBudgetEntry._meta.get_fields()
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
admin.site.register(Client.history.model, HistoricalClientAdmin)
admin.site.register(Supplier.history.model, HistoricalSupplierAdmin)
admin.site.register(Project.history.model, HistoricalProjectAdmin)
admin.site.register(
    ProjectPaymentSchedule.history.model, HistoricalProjectPaymentScheduleAdmin
)
admin.site.register(
    ProjectRealBudgetEntry.history.model, HistoricalProjectRealBudgetEntryAdmin
)

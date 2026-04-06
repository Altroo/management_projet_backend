from django.contrib import admin

from .models import Expense


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "description", "montant", "date", "category", "fournisseur")
    list_filter = ("project", "category")
    search_fields = ("description", "fournisseur")
    ordering = ("-date",)

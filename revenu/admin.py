from django.contrib import admin

from .models import Revenue


@admin.register(Revenue)
class RevenueAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "description", "montant", "date")
    list_filter = ("project",)
    search_fields = ("description",)
    ordering = ("-date",)

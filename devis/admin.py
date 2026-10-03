from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from .models import Quote, QuoteAttachment


@admin.register(Quote)
class QuoteAdmin(SimpleHistoryAdmin):
    list_display = ("number", "project", "supplier", "date", "status", "amount_ttc")
    list_filter = ("status", "project", "category")
    search_fields = ("number", "description", "supplier__nom", "project__nom")
    readonly_fields = ("amount_ttc",)


admin.site.register(QuoteAttachment)

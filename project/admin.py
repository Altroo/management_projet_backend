from django.contrib import admin

from .models import Category, SubCategory, Project


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "date_created")
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(SubCategory)
class SubCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "category", "date_created")
    list_filter = ("category",)
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("id", "nom", "status", "budget_total", "date_debut", "date_fin")
    list_filter = ("status",)
    search_fields = ("nom", "nom_client")
    ordering = ("-id",)

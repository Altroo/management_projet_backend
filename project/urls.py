from django.urls import path

from .views import (
    CategoryListCreateView,
    CategoryDetailView,
    BulkDeleteCategoryView,
    SubCategoryListCreateView,
    SubCategoryDetailView,
    BulkDeleteSubCategoryView,
    ProjectListCreateView,
    ProjectDetailEditDeleteView,
    BulkDeleteProjectView,
    ProjectDashboardView,
    MultiProjectDashboardView,
)

app_name = "project"

urlpatterns = [
    # Categories
    path("categories/", CategoryListCreateView.as_view(), name="category-list-create"),
    path(
        "categories/bulk_delete/",
        BulkDeleteCategoryView.as_view(),
        name="category-bulk-delete",
    ),
    path(
        "categories/<int:pk>/",
        CategoryDetailView.as_view(),
        name="category-detail",
    ),
    # SubCategories
    path(
        "subcategories/",
        SubCategoryListCreateView.as_view(),
        name="subcategory-list-create",
    ),
    path(
        "subcategories/bulk_delete/",
        BulkDeleteSubCategoryView.as_view(),
        name="subcategory-bulk-delete",
    ),
    path(
        "subcategories/<int:pk>/",
        SubCategoryDetailView.as_view(),
        name="subcategory-detail",
    ),
    # Projects
    path("", ProjectListCreateView.as_view(), name="project-list-create"),
    path("bulk_delete/", BulkDeleteProjectView.as_view(), name="project-bulk-delete"),
    path("<int:pk>/", ProjectDetailEditDeleteView.as_view(), name="project-detail"),
    # Dashboard
    path(
        "dashboard/<int:pk>/",
        ProjectDashboardView.as_view(),
        name="project-dashboard",
    ),
    path(
        "dashboard/",
        MultiProjectDashboardView.as_view(),
        name="multi-project-dashboard",
    ),
]

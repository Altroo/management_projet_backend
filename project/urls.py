from django.urls import path

from .views import (
    CategoryListCreateView,
    CategoryDetailView,
    BulkDeleteCategoryView,
    SubCategoryListCreateView,
    SubCategoryDetailView,
    BulkDeleteSubCategoryView,
    ExpenseTaxonomyCategoryCreateView,
    ExpenseTaxonomyCategoryDetailView,
    ExpenseTaxonomyListView,
    ExpenseTaxonomySubCategoryCreateView,
    ExpenseTaxonomySubCategoryDetailView,
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
    path(
        "expense-taxonomy/",
        ExpenseTaxonomyListView.as_view(),
        name="expense-taxonomy-list",
    ),
    path(
        "expense-taxonomy/categories/",
        ExpenseTaxonomyCategoryCreateView.as_view(),
        name="expense-taxonomy-category-create",
    ),
    path(
        "expense-taxonomy/categories/<int:pk>/",
        ExpenseTaxonomyCategoryDetailView.as_view(),
        name="expense-taxonomy-category-detail",
    ),
    path(
        "expense-taxonomy/subcategories/",
        ExpenseTaxonomySubCategoryCreateView.as_view(),
        name="expense-taxonomy-subcategory-create",
    ),
    path(
        "expense-taxonomy/subcategories/<int:pk>/",
        ExpenseTaxonomySubCategoryDetailView.as_view(),
        name="expense-taxonomy-subcategory-detail",
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

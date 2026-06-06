from django.urls import path

from .views import (
    CategoryListCreateView,
    CategoryDetailView,
    BulkDeleteCategoryView,
    BulkDeleteClientView,
    BulkDeleteProjectPaymentScheduleView,
    SubCategoryListCreateView,
    SubCategoryDetailView,
    BulkDeleteSubCategoryView,
    BulkDeleteSupplierView,
    ClientDetailView,
    ClientListCreateView,
    ExpenseTaxonomyCategoryCreateView,
    ExpenseTaxonomyCategoryDetailView,
    ExpenseTaxonomyListView,
    ExpenseTaxonomySubCategoryCreateView,
    ExpenseTaxonomySubCategoryDetailView,
    ProjectAttachmentDetailView,
    ProjectAttachmentListCreateView,
    ProjectListCreateView,
    ProjectDetailEditDeleteView,
    BulkDeleteProjectView,
    ProjectDashboardView,
    MultiProjectDashboardView,
    ProjectPaymentScheduleDetailView,
    ProjectPaymentScheduleListCreateView,
    ProjectReportPDFView,
    SupplierDetailView,
    SupplierListCreateView,
    ClientDashboardView,
    ClientProjectDashboardView,
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
    # Clients
    path("clients/", ClientListCreateView.as_view(), name="client-list-create"),
    path("clients/bulk_delete/", BulkDeleteClientView.as_view(), name="client-bulk-delete"),
    path("clients/<int:pk>/", ClientDetailView.as_view(), name="client-detail"),
    # Suppliers
    path("suppliers/", SupplierListCreateView.as_view(), name="supplier-list-create"),
    path(
        "suppliers/bulk_delete/",
        BulkDeleteSupplierView.as_view(),
        name="supplier-bulk-delete",
    ),
    path("suppliers/<int:pk>/", SupplierDetailView.as_view(), name="supplier-detail"),
    # Payment schedules
    path(
        "payment-schedules/",
        ProjectPaymentScheduleListCreateView.as_view(),
        name="payment-schedule-list-create",
    ),
    path(
        "payment-schedules/bulk_delete/",
        BulkDeleteProjectPaymentScheduleView.as_view(),
        name="payment-schedule-bulk-delete",
    ),
    path(
        "payment-schedules/<int:pk>/",
        ProjectPaymentScheduleDetailView.as_view(),
        name="payment-schedule-detail",
    ),
    # Projects
    path("", ProjectListCreateView.as_view(), name="project-list-create"),
    path("bulk_delete/", BulkDeleteProjectView.as_view(), name="project-bulk-delete"),
    path(
        "<int:pk>/attachments/",
        ProjectAttachmentListCreateView.as_view(),
        name="project-attachment-list-create",
    ),
    path(
        "attachments/<int:pk>/",
        ProjectAttachmentDetailView.as_view(),
        name="project-attachment-detail",
    ),
    path("<int:pk>/report.pdf", ProjectReportPDFView.as_view(), name="project-report-pdf"),
    path("<int:pk>/", ProjectDetailEditDeleteView.as_view(), name="project-detail"),
    # Dashboard
    path(
        "dashboard/client/",
        ClientDashboardView.as_view(),
        name="client-dashboard",
    ),
    path(
        "dashboard/client/<int:pk>/",
        ClientProjectDashboardView.as_view(),
        name="client-project-dashboard",
    ),
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

import logging

from django.db.models import Sum, DecimalField
from notification.tasks import notify_project_status_change
from django.db.models.functions import Coalesce
from django.http import Http404
from django.utils.translation import gettext_lazy as _
from rest_framework import permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import can_create, can_update, can_delete
from management_projet_backend.utils import CustomPagination
from .filters import ProjectFilter
from .models import Category, SubCategory, Project
from .serializers import (
    CategorySerializer,
    ExpenseTaxonomyCategorySerializer,
    SubCategorySerializer,
    ProjectListSerializer,
    ProjectSerializer,
)

logger = logging.getLogger(__name__)


# ── Categories ─────────────────────────────────────────────────────────────────


class CategoryListCreateView(APIView):
    """GET all categories, POST create a new category."""

    permission_classes = (permissions.IsAuthenticated,)

    @staticmethod
    def get(request):
        qs = Category.objects.select_related("created_by_user").all()
        serializer = CategorySerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @staticmethod
    def post(request):
        if not can_create(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour créer une catégorie.")
            )
        serializer = CategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by_user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CategoryDetailView(APIView):
    """GET detail, PUT update, DELETE a single category."""

    permission_classes = (permissions.IsAuthenticated,)

    @staticmethod
    def _get_category(pk: int) -> Category:
        try:
            return Category.objects.select_related("created_by_user").get(pk=pk)
        except Category.DoesNotExist:
            raise Http404(_("Catégorie introuvable."))

    def get(self, request, pk: int):
        category = self._get_category(pk)
        serializer = CategorySerializer(category)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk: int):
        if not can_update(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour modifier cette catégorie.")
            )
        category = self._get_category(pk)
        serializer = CategorySerializer(category, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk: int):
        if not can_delete(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour supprimer cette catégorie.")
            )
        self._get_category(pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class BulkDeleteCategoryView(APIView):
    """DELETE multiple categories by id list."""

    permission_classes = (permissions.IsAuthenticated,)

    @staticmethod
    def delete(request):
        if not can_delete(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour supprimer des catégories.")
            )
        ids = request.data.get("ids", [])
        if not ids or not isinstance(ids, list):
            raise ValidationError({"ids": _("Une liste d'identifiants est requise.")})
        Category.objects.filter(pk__in=ids).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── SubCategories ──────────────────────────────────────────────────────────────


class SubCategoryListCreateView(APIView):
    """GET all subcategories, POST create a new subcategory."""

    permission_classes = (permissions.IsAuthenticated,)

    @staticmethod
    def get(request):
        qs = SubCategory.objects.select_related("created_by_user", "category").all()
        category_id = request.query_params.get("category")
        if category_id:
            qs = qs.filter(category_id=category_id)
        serializer = SubCategorySerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @staticmethod
    def post(request):
        if not can_create(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour créer une sous-catégorie.")
            )
        serializer = SubCategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by_user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class SubCategoryDetailView(APIView):
    """GET detail, PUT update, DELETE a single subcategory."""

    permission_classes = (permissions.IsAuthenticated,)

    @staticmethod
    def _get_subcategory(pk: int) -> SubCategory:
        try:
            return SubCategory.objects.select_related(
                "created_by_user", "category"
            ).get(pk=pk)
        except SubCategory.DoesNotExist:
            raise Http404(_("Sous-catégorie introuvable."))

    def get(self, request, pk: int):
        subcategory = self._get_subcategory(pk)
        serializer = SubCategorySerializer(subcategory)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk: int):
        if not can_update(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour modifier cette sous-catégorie.")
            )
        subcategory = self._get_subcategory(pk)
        serializer = SubCategorySerializer(subcategory, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk: int):
        if not can_delete(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour supprimer cette sous-catégorie.")
            )
        self._get_subcategory(pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class BulkDeleteSubCategoryView(APIView):
    """DELETE multiple subcategories by id list."""

    permission_classes = (permissions.IsAuthenticated,)

    @staticmethod
    def delete(request):
        if not can_delete(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour supprimer des sous-catégories.")
            )
        ids = request.data.get("ids", [])
        if not ids or not isinstance(ids, list):
            raise ValidationError({"ids": _("Une liste d'identifiants est requise.")})
        SubCategory.objects.filter(pk__in=ids).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ExpenseTaxonomyListView(APIView):
    """GET nested categories and subcategories for expense form CRUD."""

    permission_classes = (permissions.IsAuthenticated,)

    @staticmethod
    def get(request):
        queryset = Category.objects.select_related("created_by_user").prefetch_related(
            "subcategories__created_by_user"
        )
        serializer = ExpenseTaxonomyCategorySerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ExpenseTaxonomyCategoryCreateView(APIView):
    """POST create a category for expense form taxonomy management."""

    permission_classes = (permissions.IsAuthenticated,)

    @staticmethod
    def post(request):
        if not can_create(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour créer une catégorie.")
            )
        serializer = CategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by_user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ExpenseTaxonomyCategoryDetailView(APIView):
    """PUT, DELETE a category from expense form taxonomy management."""

    permission_classes = (permissions.IsAuthenticated,)

    @staticmethod
    def _get_category(pk: int) -> Category:
        try:
            return Category.objects.get(pk=pk)
        except Category.DoesNotExist:
            raise Http404(_("Catégorie introuvable."))

    def put(self, request, pk: int):
        if not can_update(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour modifier cette catégorie.")
            )
        category = self._get_category(pk)
        serializer = CategorySerializer(category, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by_user=category.created_by_user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk: int):
        if not can_delete(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour supprimer cette catégorie.")
            )
        self._get_category(pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ExpenseTaxonomySubCategoryCreateView(APIView):
    """POST create a subcategory for expense form taxonomy management."""

    permission_classes = (permissions.IsAuthenticated,)

    @staticmethod
    def post(request):
        if not can_create(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour créer une sous-catégorie.")
            )
        serializer = SubCategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by_user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ExpenseTaxonomySubCategoryDetailView(APIView):
    """PUT, DELETE a subcategory from expense form taxonomy management."""

    permission_classes = (permissions.IsAuthenticated,)

    @staticmethod
    def _get_subcategory(pk: int) -> SubCategory:
        try:
            return SubCategory.objects.select_related("category").get(pk=pk)
        except SubCategory.DoesNotExist:
            raise Http404(_("Sous-catégorie introuvable."))

    def put(self, request, pk: int):
        if not can_update(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour modifier cette sous-catégorie.")
            )
        subcategory = self._get_subcategory(pk)
        serializer = SubCategorySerializer(subcategory, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by_user=subcategory.created_by_user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk: int):
        if not can_delete(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour supprimer cette sous-catégorie.")
            )
        self._get_subcategory(pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Projects ───────────────────────────────────────────────────────────────────


class ProjectListCreateView(APIView):
    """GET paginated/full project list and POST create a new project."""

    permission_classes = (permissions.IsAuthenticated,)

    @staticmethod
    def get(request):
        pagination = request.query_params.get("pagination", "false").lower() == "true"

        base_qs = (
            Project.objects.all().select_related("created_by_user").order_by("-id")
        )
        filterset = ProjectFilter(request.GET, queryset=base_qs)
        ordered_qs = filterset.qs

        if pagination:
            paginator = CustomPagination()
            page = paginator.paginate_queryset(ordered_qs, request)
            serializer = ProjectListSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = ProjectListSerializer(ordered_qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @staticmethod
    def post(request):
        if not can_create(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour créer un projet.")
            )
        serializer = ProjectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save(created_by_user=request.user)
        response_serializer = ProjectSerializer(instance)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class ProjectDetailEditDeleteView(APIView):
    """GET, PUT, DELETE a single project by pk."""

    permission_classes = (permissions.IsAuthenticated,)

    @staticmethod
    def _get_project(pk: int) -> Project:
        try:
            return Project.objects.select_related("created_by_user").get(pk=pk)
        except Project.DoesNotExist:
            raise Http404(_("Projet introuvable."))

    def get(self, request, pk: int):
        project = self._get_project(pk)
        serializer = ProjectSerializer(project)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk: int):
        if not can_update(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour modifier ce projet.")
            )
        project = self._get_project(pk)
        old_status = project.status
        serializer = ProjectSerializer(project, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by_user=project.created_by_user)
        new_status = serializer.instance.status
        if old_status != new_status:
            notify_project_status_change(serializer.instance, old_status, new_status)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk: int):
        if not can_delete(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour supprimer ce projet.")
            )
        self._get_project(pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class BulkDeleteProjectView(APIView):
    """DELETE multiple projects by id list."""

    permission_classes = (permissions.IsAuthenticated,)

    @staticmethod
    def delete(request):
        if not can_delete(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour supprimer des projets.")
            )
        ids = request.data.get("ids", [])
        if not ids or not isinstance(ids, list):
            raise ValidationError({"ids": _("Une liste d'identifiants est requise.")})
        Project.objects.filter(pk__in=ids).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Dashboard ──────────────────────────────────────────────────────────────────


class ProjectDashboardView(APIView):
    """GET dashboard stats for a single project (APPERÇU DU PROJET)."""

    permission_classes = (permissions.IsAuthenticated,)

    @staticmethod
    def get(request, pk: int):
        try:
            project = Project.objects.get(pk=pk)
        except Project.DoesNotExist:
            raise Http404(_("Projet introuvable."))

        from revenu.models import Revenue
        from depense.models import Expense

        revenue_total = Revenue.objects.filter(project=project).aggregate(
            total=Coalesce(Sum("montant"), 0, output_field=DecimalField())
        )["total"]
        depenses_totales = Expense.objects.filter(project=project).aggregate(
            total=Coalesce(Sum("montant"), 0, output_field=DecimalField())
        )["total"]
        benefice = revenue_total - depenses_totales
        marge = round((benefice / revenue_total) * 100, 2) if revenue_total else 0

        # Top 10 categories
        top_categories = list(
            Expense.objects.filter(project=project)
            .values("category__name")
            .annotate(total=Sum("montant"))
            .order_by("-total")[:10]
        )

        # Top 10 subcategories
        top_subcategories = list(
            Expense.objects.filter(project=project, sous_categorie__isnull=False)
            .values("sous_categorie__name")
            .annotate(total=Sum("montant"))
            .order_by("-total")[:10]
        )

        # Top 10 vendors
        top_vendors = list(
            Expense.objects.filter(project=project)
            .exclude(fournisseur__isnull=True)
            .exclude(fournisseur="")
            .values("fournisseur")
            .annotate(total=Sum("montant"))
            .order_by("-total")[:10]
        )

        # Expense history
        expense_history = list(
            Expense.objects.filter(project=project)
            .values("date")
            .annotate(total=Sum("montant"))
            .order_by("date")
        )

        # Revenue history
        revenue_history = list(
            Revenue.objects.filter(project=project)
            .values("date")
            .annotate(total=Sum("montant"))
            .order_by("date")
        )

        return Response(
            {
                "project_id": project.id,
                "nom": project.nom,
                "budget_total": project.budget_total,
                "revenue_total": revenue_total,
                "depenses_totales": depenses_totales,
                "benefice": benefice,
                "marge": marge,
                "budget_utilisation": (
                    round((depenses_totales / project.budget_total) * 100, 2)
                    if project.budget_total
                    else 0
                ),
                "top_categories": top_categories,
                "top_subcategories": top_subcategories,
                "top_vendors": top_vendors,
                "expense_history": expense_history,
                "revenue_history": revenue_history,
            },
            status=status.HTTP_200_OK,
        )


class MultiProjectDashboardView(APIView):
    """GET multi-project dashboard stats (all projects overview)."""

    permission_classes = (permissions.IsAuthenticated,)

    @staticmethod
    def get(request):
        from revenu.models import Revenue
        from depense.models import Expense

        projects = Project.objects.all()

        total_budget = projects.aggregate(
            total=Coalesce(Sum("budget_total"), 0, output_field=DecimalField())
        )["total"]
        total_revenue = Revenue.objects.aggregate(
            total=Coalesce(Sum("montant"), 0, output_field=DecimalField())
        )["total"]
        total_expenses = Expense.objects.aggregate(
            total=Coalesce(Sum("montant"), 0, output_field=DecimalField())
        )["total"]
        total_profit = total_revenue - total_expenses
        total_margin = (
            round((total_profit / total_revenue) * 100, 2) if total_revenue else 0
        )
        budget_utilisation = (
            round((total_expenses / total_budget) * 100, 2) if total_budget else 0
        )

        # Per-project summary
        project_summaries = []
        for p in projects:
            p_revenue = Revenue.objects.filter(project=p).aggregate(
                total=Coalesce(Sum("montant"), 0, output_field=DecimalField())
            )["total"]
            p_expenses = Expense.objects.filter(project=p).aggregate(
                total=Coalesce(Sum("montant"), 0, output_field=DecimalField())
            )["total"]
            project_summaries.append(
                {
                    "id": p.id,
                    "nom": p.nom,
                    "budget_total": p.budget_total,
                    "revenue": p_revenue,
                    "expenses": p_expenses,
                    "profit": p_revenue - p_expenses,
                    "status": p.status,
                }
            )

        return Response(
            {
                "total_projects": projects.count(),
                "total_budget": total_budget,
                "total_revenue": total_revenue,
                "total_expenses": total_expenses,
                "total_profit": total_profit,
                "total_margin": total_margin,
                "budget_utilisation": budget_utilisation,
                "projects": project_summaries,
            },
            status=status.HTTP_200_OK,
        )

import logging
from decimal import Decimal

from django.db.models import Q, Sum, DecimalField
from notification.tasks import notify_project_status_change
from django.db.models.functions import Coalesce
from django.http import FileResponse, Http404
from django.utils.translation import gettext_lazy as _
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework import permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import can_create, can_update, can_delete
from management_projet_backend.utils import CustomPagination
from .filters import ProjectFilter
from .models import (
    Category,
    Client,
    Project,
    ProjectAttachment,
    ProjectPaymentSchedule,
    SubCategory,
    Supplier,
)
from .pdf import build_project_report_pdf
from .serializers import (
    CategorySerializer,
    ClientSerializer,
    ExpenseTaxonomyCategorySerializer,
    ProjectAttachmentSerializer,
    SubCategorySerializer,
    ProjectListSerializer,
    ProjectPaymentScheduleSerializer,
    ProjectSerializer,
    SupplierSerializer,
)

logger = logging.getLogger(__name__)


def _client_label(value):
    return value or _("Sans client")


def _paginate_or_serialize(request, queryset, serializer_class):
    pagination = request.query_params.get("pagination", "false").lower() == "true"
    if pagination:
        paginator = CustomPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = serializer_class(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)
    serializer = serializer_class(queryset, many=True, context={"request": request})
    return Response(serializer.data, status=status.HTTP_200_OK)


def _service_fee_total(expenses):
    return sum(
        (
            expense.frais_de_service_montant
            for expense in expenses
            if expense.frais_de_service
        ),
        Decimal("0.00"),
    )


def _expense_amount(expense, include_service_fees=False):
    amount = expense.montant or Decimal("0.00")
    if include_service_fees:
        amount += expense.frais_de_service_montant
    return amount


def _expense_total(expenses, include_service_fees=False):
    if not include_service_fees:
        return expenses.aggregate(
            total=Coalesce(Sum("montant"), 0, output_field=DecimalField())
        )["total"]
    return sum(
        (_expense_amount(expense, include_service_fees=True) for expense in expenses),
        Decimal("0.00"),
    )


def _group_expenses(
    expenses,
    key_getter,
    key_name,
    include_service_fees=False,
    limit=10,
    skip_empty=False,
    label_getter=None,
):
    totals = {}
    for expense in expenses:
        raw_key = key_getter(expense)
        if skip_empty and not raw_key:
            continue
        key = label_getter(raw_key) if label_getter else raw_key
        totals[key] = totals.get(key, Decimal("0.00")) + _expense_amount(
            expense, include_service_fees=include_service_fees
        )
    return [
        {key_name: key, "total": total}
        for key, total in sorted(totals.items(), key=lambda item: item[1], reverse=True)[
            :limit
        ]
    ]


def _expense_history(expenses, include_service_fees=False):
    if not include_service_fees:
        return list(
            expenses.values("date")
            .annotate(total=Sum("montant"))
            .order_by("date")
        )

    totals = {}
    for expense in expenses:
        totals[expense.date] = totals.get(expense.date, Decimal("0.00")) + _expense_amount(
            expense, include_service_fees=True
        )
    return [
        {"date": date, "total": total}
        for date, total in sorted(totals.items(), key=lambda item: item[0])
    ]


def _project_dashboard_payload(project, include_service_fees=False):
    from revenu.models import Revenue
    from depense.models import Expense

    expenses = Expense.objects.filter(project=project).select_related(
        "project", "category", "sous_categorie"
    )
    revenue_total = Revenue.objects.filter(project=project).aggregate(
        total=Coalesce(Sum("montant"), 0, output_field=DecimalField())
    )["total"]
    depenses_totales = _expense_total(
        expenses, include_service_fees=include_service_fees
    )
    benefice = revenue_total - depenses_totales
    marge = round((benefice / revenue_total) * 100, 2) if revenue_total else 0
    service_fees = _service_fee_total(expenses)

    revenue_history = list(
        Revenue.objects.filter(project=project)
        .values("date")
        .annotate(total=Sum("montant"))
        .order_by("date")
    )

    payload = {
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
        "top_categories": _group_expenses(
            expenses,
            lambda expense: expense.category.name if expense.category else None,
            "category__name",
            include_service_fees=include_service_fees,
        ),
        "top_subcategories": _group_expenses(
            expenses,
            lambda expense: (
                expense.sous_categorie.name if expense.sous_categorie else None
            ),
            "sous_categorie__name",
            include_service_fees=include_service_fees,
            skip_empty=True,
        ),
        "top_vendors": _group_expenses(
            expenses,
            lambda expense: expense.fournisseur,
            "fournisseur",
            include_service_fees=include_service_fees,
            skip_empty=True,
        ),
        "expense_history": _expense_history(
            expenses, include_service_fees=include_service_fees
        ),
        "revenue_history": revenue_history,
    }
    if not include_service_fees:
        payload["service_fees"] = service_fees
        payload["revenue_reelle"] = revenue_total + service_fees
    return payload


def _multi_project_dashboard_payload(include_service_fees=False):
    from revenu.models import Revenue
    from depense.models import Expense

    projects = Project.objects.all()
    expenses = Expense.objects.select_related("project", "category", "sous_categorie")

    total_budget = projects.aggregate(
        total=Coalesce(Sum("budget_total"), 0, output_field=DecimalField())
    )["total"]
    total_revenue = Revenue.objects.aggregate(
        total=Coalesce(Sum("montant"), 0, output_field=DecimalField())
    )["total"]
    total_expenses = _expense_total(
        expenses, include_service_fees=include_service_fees
    )
    total_profit = total_revenue - total_expenses
    total_margin = (
        round((total_profit / total_revenue) * 100, 2) if total_revenue else 0
    )
    budget_utilisation = (
        round((total_expenses / total_budget) * 100, 2) if total_budget else 0
    )
    total_service_fees = _service_fee_total(expenses)

    if include_service_fees:
        top_expense_clients = _group_expenses(
            expenses,
            lambda expense: expense.project.nom_client,
            "client",
            include_service_fees=True,
            limit=5,
            label_getter=lambda value: str(_client_label(value)),
        )
    else:
        top_expense_clients = [
            {
                "client": str(_client_label(item["project__nom_client"])),
                "total": item["total"],
            }
            for item in Expense.objects.values("project__nom_client")
            .annotate(total=Sum("montant"))
            .order_by("-total")[:5]
        ]

    top_revenue_clients = [
        {
            "client": str(_client_label(item["project__nom_client"])),
            "total": item["total"],
        }
        for item in Revenue.objects.values("project__nom_client")
        .annotate(total=Sum("montant"))
        .order_by("-total")[:5]
    ]

    project_summaries = []
    for project in projects:
        p_revenue = Revenue.objects.filter(project=project).aggregate(
            total=Coalesce(Sum("montant"), 0, output_field=DecimalField())
        )["total"]
        p_expenses_qs = Expense.objects.filter(project=project).select_related(
            "project", "category", "sous_categorie"
        )
        p_expenses = _expense_total(
            p_expenses_qs, include_service_fees=include_service_fees
        )
        project_summaries.append(
            {
                "id": project.id,
                "nom": project.nom,
                "budget_total": project.budget_total,
                "revenue": p_revenue,
                "expenses": p_expenses,
                "profit": p_revenue - p_expenses,
                "status": project.status,
            }
        )

    payload = {
        "total_projects": projects.count(),
        "total_budget": total_budget,
        "total_revenue": total_revenue,
        "total_expenses": total_expenses,
        "total_profit": total_profit,
        "total_margin": total_margin,
        "budget_utilisation": budget_utilisation,
        "top_expense_clients": top_expense_clients,
        "top_revenue_clients": top_revenue_clients,
        "top_categories": _group_expenses(
            expenses,
            lambda expense: expense.category.name if expense.category else None,
            "category__name",
            include_service_fees=include_service_fees,
        ),
        "top_subcategories": _group_expenses(
            expenses,
            lambda expense: (
                expense.sous_categorie.name if expense.sous_categorie else None
            ),
            "sous_categorie__name",
            include_service_fees=include_service_fees,
            skip_empty=True,
        ),
        "top_vendors": _group_expenses(
            expenses,
            lambda expense: expense.fournisseur,
            "fournisseur",
            include_service_fees=include_service_fees,
            skip_empty=True,
        ),
        "expense_history": _expense_history(
            expenses, include_service_fees=include_service_fees
        ),
        "revenue_history": list(
            Revenue.objects.values("date")
            .annotate(total=Sum("montant"))
            .order_by("date")
        ),
        "projects": project_summaries,
    }
    if not include_service_fees:
        payload["total_service_fees"] = total_service_fees
        payload["total_revenue_reelle"] = total_revenue + total_service_fees
    return payload


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
            Project.objects.all()
            .select_related("created_by_user", "client")
            .order_by("-id")
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
            return Project.objects.select_related("created_by_user", "client").get(pk=pk)
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


# ── Clients ───────────────────────────────────────────────────────────────────


class ClientListCreateView(APIView):
    """GET clients directory, POST create a reusable client."""

    permission_classes = (permissions.IsAuthenticated,)

    @staticmethod
    def get(request):
        queryset = Client.objects.select_related("created_by_user").all()
        search = request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(nom__icontains=search)
                | Q(telephone__icontains=search)
                | Q(email__icontains=search)
                | Q(adresse__icontains=search)
            )
        return _paginate_or_serialize(request, queryset, ClientSerializer)

    @staticmethod
    def post(request):
        if not can_create(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour créer un client.")
            )
        serializer = ClientSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by_user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ClientDetailView(APIView):
    """GET, PUT, DELETE a client."""

    permission_classes = (permissions.IsAuthenticated,)

    @staticmethod
    def _get_client(pk: int) -> Client:
        try:
            return Client.objects.select_related("created_by_user").get(pk=pk)
        except Client.DoesNotExist:
            raise Http404(_("Client introuvable."))

    def get(self, request, pk: int):
        serializer = ClientSerializer(self._get_client(pk), context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk: int):
        if not can_update(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour modifier ce client.")
            )
        instance = self._get_client(pk)
        serializer = ClientSerializer(
            instance, data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by_user=instance.created_by_user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk: int):
        if not can_delete(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour supprimer ce client.")
            )
        self._get_client(pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class BulkDeleteClientView(APIView):
    """DELETE multiple clients by id list."""

    permission_classes = (permissions.IsAuthenticated,)

    @staticmethod
    def delete(request):
        if not can_delete(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour supprimer des clients.")
            )
        ids = request.data.get("ids", [])
        if not ids or not isinstance(ids, list):
            raise ValidationError({"ids": _("Une liste d'identifiants est requise.")})
        Client.objects.filter(pk__in=ids).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Suppliers ─────────────────────────────────────────────────────────────────


class SupplierListCreateView(APIView):
    """GET suppliers directory, POST create a reusable supplier."""

    permission_classes = (permissions.IsAuthenticated,)

    @staticmethod
    def get(request):
        queryset = Supplier.objects.select_related("created_by_user").all()
        search = request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(nom__icontains=search)
                | Q(contact__icontains=search)
                | Q(specialite__icontains=search)
            )
        return _paginate_or_serialize(request, queryset, SupplierSerializer)

    @staticmethod
    def post(request):
        if not can_create(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour créer un fournisseur.")
            )
        serializer = SupplierSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by_user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class SupplierDetailView(APIView):
    """GET, PUT, DELETE a supplier."""

    permission_classes = (permissions.IsAuthenticated,)

    @staticmethod
    def _get_supplier(pk: int) -> Supplier:
        try:
            return Supplier.objects.select_related("created_by_user").get(pk=pk)
        except Supplier.DoesNotExist:
            raise Http404(_("Fournisseur introuvable."))

    def get(self, request, pk: int):
        serializer = SupplierSerializer(
            self._get_supplier(pk), context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk: int):
        if not can_update(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour modifier ce fournisseur.")
            )
        instance = self._get_supplier(pk)
        serializer = SupplierSerializer(
            instance, data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by_user=instance.created_by_user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk: int):
        if not can_delete(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour supprimer ce fournisseur.")
            )
        self._get_supplier(pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class BulkDeleteSupplierView(APIView):
    """DELETE multiple suppliers by id list."""

    permission_classes = (permissions.IsAuthenticated,)

    @staticmethod
    def delete(request):
        if not can_delete(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour supprimer des fournisseurs.")
            )
        ids = request.data.get("ids", [])
        if not ids or not isinstance(ids, list):
            raise ValidationError({"ids": _("Une liste d'identifiants est requise.")})
        Supplier.objects.filter(pk__in=ids).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Attachments and Payment Schedules ─────────────────────────────────────────


class ProjectAttachmentListCreateView(APIView):
    """GET/POST attachments for a project."""

    permission_classes = (permissions.IsAuthenticated,)
    parser_classes = (MultiPartParser, FormParser)

    @staticmethod
    def _get_project(pk: int) -> Project:
        try:
            return Project.objects.get(pk=pk)
        except Project.DoesNotExist:
            raise Http404(_("Projet introuvable."))

    def get(self, request, pk: int):
        self._get_project(pk)
        queryset = ProjectAttachment.objects.filter(project_id=pk).select_related(
            "uploaded_by_user"
        )
        serializer = ProjectAttachmentSerializer(
            queryset, many=True, context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, pk: int):
        if not can_create(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour ajouter une pièce jointe.")
            )
        project = self._get_project(pk)
        serializer = ProjectAttachmentSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(project=project, uploaded_by_user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ProjectAttachmentDetailView(APIView):
    """DELETE a project attachment."""

    permission_classes = (permissions.IsAuthenticated,)

    @staticmethod
    def _get_attachment(pk: int) -> ProjectAttachment:
        try:
            return ProjectAttachment.objects.get(pk=pk)
        except ProjectAttachment.DoesNotExist:
            raise Http404(_("Pièce jointe introuvable."))

    def delete(self, request, pk: int):
        if not can_delete(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour supprimer cette pièce jointe.")
            )
        attachment = self._get_attachment(pk)
        attachment.file.delete(save=False)
        attachment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProjectPaymentScheduleListCreateView(APIView):
    """GET/POST project payment schedule entries."""

    permission_classes = (permissions.IsAuthenticated,)

    @staticmethod
    def get(request):
        queryset = ProjectPaymentSchedule.objects.select_related(
            "project", "created_by_user"
        ).all()
        project_id = request.query_params.get("project")
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        return _paginate_or_serialize(request, queryset, ProjectPaymentScheduleSerializer)

    @staticmethod
    def post(request):
        if not can_create(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour créer une échéance.")
            )
        serializer = ProjectPaymentScheduleSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by_user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ProjectPaymentScheduleDetailView(APIView):
    """GET, PUT, DELETE a project payment schedule entry."""

    permission_classes = (permissions.IsAuthenticated,)

    @staticmethod
    def _get_schedule(pk: int) -> ProjectPaymentSchedule:
        try:
            return ProjectPaymentSchedule.objects.select_related(
                "project", "created_by_user"
            ).get(pk=pk)
        except ProjectPaymentSchedule.DoesNotExist:
            raise Http404(_("Échéance introuvable."))

    def get(self, request, pk: int):
        serializer = ProjectPaymentScheduleSerializer(
            self._get_schedule(pk), context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk: int):
        if not can_update(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour modifier cette échéance.")
            )
        instance = self._get_schedule(pk)
        serializer = ProjectPaymentScheduleSerializer(
            instance, data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by_user=instance.created_by_user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk: int):
        if not can_delete(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour supprimer cette échéance.")
            )
        self._get_schedule(pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class BulkDeleteProjectPaymentScheduleView(APIView):
    """DELETE multiple payment schedule entries by id list."""

    permission_classes = (permissions.IsAuthenticated,)

    @staticmethod
    def delete(request):
        if not can_delete(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour supprimer des échéances.")
            )
        ids = request.data.get("ids", [])
        if not ids or not isinstance(ids, list):
            raise ValidationError({"ids": _("Une liste d'identifiants est requise.")})
        ProjectPaymentSchedule.objects.filter(pk__in=ids).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProjectReportPDFView(APIView):
    """Generate a project PDF report."""

    permission_classes = (permissions.IsAuthenticated,)

    @staticmethod
    def get(request, pk: int):
        try:
            project = Project.objects.select_related("client").get(pk=pk)
        except Project.DoesNotExist:
            raise Http404(_("Projet introuvable."))

        try:
            pdf_buffer = build_project_report_pdf(project)
        except ImportError:
            raise ValidationError(
                {
                    "report": _(
                        "La génération PDF nécessite la dépendance ReportLab."
                    )
                }
            )
        return FileResponse(
            pdf_buffer,
            as_attachment=True,
            filename=f"rapport-projet-{project.id}.pdf",
            content_type="application/pdf",
        )


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

        return Response(
            _project_dashboard_payload(project),
            status=status.HTTP_200_OK,
        )


class ClientProjectDashboardView(APIView):
    """GET client-facing dashboard stats for a single project."""

    permission_classes = (permissions.IsAuthenticated,)

    @staticmethod
    def get(request, pk: int):
        try:
            project = Project.objects.get(pk=pk)
        except Project.DoesNotExist:
            raise Http404(_("Projet introuvable."))

        return Response(
            _project_dashboard_payload(project, include_service_fees=True),
            status=status.HTTP_200_OK,
        )


class MultiProjectDashboardView(APIView):
    """GET multi-project dashboard stats (all projects overview)."""

    permission_classes = (permissions.IsAuthenticated,)

    @staticmethod
    def get(request):
        return Response(
            _multi_project_dashboard_payload(),
            status=status.HTTP_200_OK,
        )


class ClientDashboardView(APIView):
    """GET client-facing dashboard stats with service fees folded into costs."""

    permission_classes = (permissions.IsAuthenticated,)

    @staticmethod
    def get(request):
        return Response(
            _multi_project_dashboard_payload(include_service_fees=True),
            status=status.HTTP_200_OK,
        )

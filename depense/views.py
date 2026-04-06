import logging

from django.http import Http404
from django.utils.translation import gettext_lazy as _
from rest_framework import permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import can_create, can_update, can_delete
from .filters import ExpenseFilter
from .models import Expense
from .serializers import ExpenseSerializer

logger = logging.getLogger(__name__)


class ExpenseListCreateView(APIView):
    """GET all expenses (optionally filtered), POST create a new expense."""

    permission_classes = (permissions.IsAuthenticated,)

    @staticmethod
    def get(request):
        qs = Expense.objects.select_related(
            "project", "category", "sous_categorie", "created_by_user"
        ).all()
        filterset = ExpenseFilter(request.GET, queryset=qs)
        serializer = ExpenseSerializer(filterset.qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @staticmethod
    def post(request):
        if not can_create(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour créer une dépense.")
            )
        serializer = ExpenseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by_user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ExpenseDetailView(APIView):
    """GET detail, PUT update, DELETE a single expense."""

    permission_classes = (permissions.IsAuthenticated,)

    @staticmethod
    def _get_expense(pk: int) -> Expense:
        try:
            return Expense.objects.select_related(
                "project", "category", "sous_categorie", "created_by_user"
            ).get(pk=pk)
        except Expense.DoesNotExist:
            raise Http404(_("Dépense introuvable."))

    def get(self, request, pk: int):
        expense = self._get_expense(pk)
        serializer = ExpenseSerializer(expense)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk: int):
        if not can_update(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour modifier cette dépense.")
            )
        expense = self._get_expense(pk)
        serializer = ExpenseSerializer(expense, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk: int):
        if not can_delete(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour supprimer cette dépense.")
            )
        self._get_expense(pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class BulkDeleteExpenseView(APIView):
    """DELETE multiple expenses by id list."""

    permission_classes = (permissions.IsAuthenticated,)

    @staticmethod
    def delete(request):
        if not can_delete(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour supprimer des dépenses.")
            )
        ids = request.data.get("ids", [])
        if not ids or not isinstance(ids, list):
            raise ValidationError(
                {"ids": _("Une liste d'identifiants est requise.")}
            )
        Expense.objects.filter(pk__in=ids).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

import logging

from django.http import Http404
from django.utils.translation import gettext_lazy as _
from rest_framework import permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import can_create, can_update, can_delete
from .filters import RevenueFilter
from .models import Revenue, RevenueAttachment
from .serializers import RevenueAttachmentSerializer, RevenueSerializer

logger = logging.getLogger(__name__)


class RevenueListCreateView(APIView):
    """GET all revenues (optionally filtered), POST create a new revenue."""

    permission_classes = (permissions.IsAuthenticated,)

    @staticmethod
    def get(request):
        qs = Revenue.objects.select_related("project", "created_by_user").all()
        filterset = RevenueFilter(request.GET, queryset=qs)
        serializer = RevenueSerializer(filterset.qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @staticmethod
    def post(request):
        if not can_create(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour créer un revenu.")
            )
        serializer = RevenueSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by_user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class RevenueDetailView(APIView):
    """GET detail, PUT update, DELETE a single revenue."""

    permission_classes = (permissions.IsAuthenticated,)

    @staticmethod
    def _get_revenue(pk: int) -> Revenue:
        try:
            return Revenue.objects.select_related("project", "created_by_user").get(
                pk=pk
            )
        except Revenue.DoesNotExist:
            raise Http404(_("Revenu introuvable."))

    def get(self, request, pk: int):
        revenue = self._get_revenue(pk)
        serializer = RevenueSerializer(revenue)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk: int):
        if not can_update(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour modifier ce revenu.")
            )
        revenue = self._get_revenue(pk)
        serializer = RevenueSerializer(revenue, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk: int):
        if not can_delete(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour supprimer ce revenu.")
            )
        self._get_revenue(pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class BulkDeleteRevenueView(APIView):
    """DELETE multiple revenues by id list."""

    permission_classes = (permissions.IsAuthenticated,)

    @staticmethod
    def delete(request):
        if not can_delete(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour supprimer des revenus.")
            )
        ids = request.data.get("ids", [])
        if not ids or not isinstance(ids, list):
            raise ValidationError({"ids": _("Une liste d'identifiants est requise.")})
        Revenue.objects.filter(pk__in=ids).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class RevenueAttachmentListCreateView(APIView):
    """GET/POST attachments for a revenue."""

    permission_classes = (permissions.IsAuthenticated,)
    parser_classes = (MultiPartParser, FormParser)

    @staticmethod
    def _get_revenue(pk: int) -> Revenue:
        try:
            return Revenue.objects.get(pk=pk)
        except Revenue.DoesNotExist:
            raise Http404(_("Revenu introuvable."))

    def get(self, request, pk: int):
        self._get_revenue(pk)
        queryset = RevenueAttachment.objects.filter(revenue_id=pk).select_related(
            "uploaded_by_user"
        )
        serializer = RevenueAttachmentSerializer(
            queryset, many=True, context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, pk: int):
        if not can_create(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour ajouter une pièce jointe.")
            )
        revenue = self._get_revenue(pk)
        serializer = RevenueAttachmentSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(revenue=revenue, uploaded_by_user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class RevenueAttachmentDetailView(APIView):
    """DELETE a revenue attachment."""

    permission_classes = (permissions.IsAuthenticated,)

    @staticmethod
    def _get_attachment(pk: int) -> RevenueAttachment:
        try:
            return RevenueAttachment.objects.get(pk=pk)
        except RevenueAttachment.DoesNotExist:
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

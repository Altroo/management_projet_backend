from management_projet_backend.ordering import apply_list_ordering
import logging

from django.http import Http404
from django.db import transaction
from django.db.models import Sum, DecimalField, Value
from django.db.models.functions import Coalesce
from decimal import Decimal
from django.utils.translation import gettext_lazy as _
from rest_framework import permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import can_create, can_update, can_delete, can_view
from .filters import QuoteFilter
from .models import Quote, QuoteAttachment
from .serializers import QuoteAttachmentSerializer, QuoteSerializer

logger = logging.getLogger(__name__)


class QuoteAccess(permissions.IsAuthenticated):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and (
            request.method not in permissions.SAFE_METHODS or can_view(request.user)
        )


def quote_queryset():
    return Quote.objects.select_related(
        "project", "category", "sous_categorie", "supplier", "created_by_user"
    ).annotate(
        spent=Coalesce(
            Sum("expenses__montant"),
            Value(Decimal("0.00")),
            output_field=DecimalField(max_digits=18, decimal_places=2),
        )
    )


class QuoteListCreateView(APIView):
    """GET all quotes (optionally filtered), POST create a new quote."""

    permission_classes = (QuoteAccess,)

    @staticmethod
    def get(request):
        qs = quote_queryset()
        filterset = QuoteFilter(request.GET, queryset=qs)
        if not filterset.is_valid():
            raise ValidationError(filterset.errors)
        serializer = QuoteSerializer(apply_list_ordering(filterset.qs, request.query_params), many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @staticmethod
    def post(request):
        if not can_create(request.user):
            raise PermissionDenied(_("Vous n'avez pas les droits pour créer un devis."))
        serializer = QuoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by_user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class QuoteDetailView(APIView):
    """GET detail, PUT update, DELETE a single quote."""

    permission_classes = (QuoteAccess,)

    @staticmethod
    def _get_quote(pk: int) -> Quote:
        try:
            return quote_queryset().get(pk=pk)
        except Quote.DoesNotExist:
            raise Http404(_("Devis introuvable."))

    def get(self, request, pk: int):
        quote = self._get_quote(pk)
        serializer = QuoteSerializer(quote)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @transaction.atomic
    def put(self, request, pk: int):
        if not can_update(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour modifier ce devis.")
            )
        quote = Quote.objects.select_for_update().get(pk=self._get_quote(pk).pk)
        serializer = QuoteSerializer(quote, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            QuoteSerializer(self._get_quote(pk)).data, status=status.HTTP_200_OK
        )

    @transaction.atomic
    def delete(self, request, pk: int):
        if not can_delete(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour supprimer ce devis.")
            )
        quote = Quote.objects.select_for_update().get(pk=self._get_quote(pk).pk)
        if quote.expenses.exists():
            raise ValidationError(
                {
                    "quote": "Ce devis est lié à des dépenses et ne peut pas être supprimé."
                }
            )
        quote.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class BulkDeleteQuoteView(APIView):
    """DELETE multiple quotes by id list."""

    permission_classes = (QuoteAccess,)

    @staticmethod
    @transaction.atomic
    def delete(request):
        if not can_delete(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour supprimer des devis.")
            )
        ids = request.data.get("ids", [])
        if not ids or not isinstance(ids, list):
            raise ValidationError({"ids": _("Une liste d'identifiants est requise.")})
        if any(
            not isinstance(pk, int) or isinstance(pk, bool) or pk <= 0 for pk in ids
        ):
            raise ValidationError({"ids": "Identifiants invalides."})
        list(Quote.objects.select_for_update().filter(pk__in=ids).order_by("pk"))
        if Quote.objects.filter(pk__in=ids, expenses__isnull=False).exists():
            raise ValidationError(
                {"ids": "Un devis sélectionné est lié à des dépenses."}
            )
        Quote.objects.filter(pk__in=ids).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class QuoteAttachmentListCreateView(APIView):
    """GET/POST attachments for a quote."""

    permission_classes = (QuoteAccess,)
    parser_classes = (MultiPartParser, FormParser)

    @staticmethod
    def _get_quote(pk: int) -> Quote:
        try:
            return Quote.objects.get(pk=pk)
        except Quote.DoesNotExist:
            raise Http404(_("Devis introuvable."))

    def get(self, request, pk: int):
        self._get_quote(pk)
        queryset = QuoteAttachment.objects.filter(quote_id=pk).select_related(
            "uploaded_by_user"
        )
        serializer = QuoteAttachmentSerializer(
            queryset, many=True, context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, pk: int):
        if not can_create(request.user):
            raise PermissionDenied(
                _("Vous n'avez pas les droits pour ajouter une pièce jointe.")
            )
        quote = self._get_quote(pk)
        serializer = QuoteAttachmentSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(quote=quote, uploaded_by_user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class QuoteAttachmentDetailView(APIView):
    """DELETE a quote attachment."""

    permission_classes = (QuoteAccess,)

    @staticmethod
    def _get_attachment(pk: int) -> QuoteAttachment:
        try:
            return QuoteAttachment.objects.get(pk=pk)
        except QuoteAttachment.DoesNotExist:
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

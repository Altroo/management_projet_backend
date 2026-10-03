from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from simple_history.models import HistoricalRecords
from account.models import CustomUser
from project.models import Project, Supplier, Category, SubCategory


def quote_attachment_upload_to(instance, filename):
    return f"quote_attachments/{instance.quote_id}/{uuid4().hex}{Path(filename).suffix}"


class Quote(models.Model):
    class Status(models.TextChoices):
        RECEIVED = "received", _("Reçu")
        VALIDATED = "validated", _("Validé")
        REJECTED = "rejected", _("Refusé")

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="quotes"
    )
    supplier = models.ForeignKey(
        Supplier, on_delete=models.PROTECT, related_name="quotes"
    )
    number = models.CharField(max_length=100)
    date = models.DateField(db_index=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quotes",
    )
    sous_categorie = models.ForeignKey(
        SubCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quotes",
    )
    description = models.TextField()
    amount_ht = models.DecimalField(
        max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    amount_tva = models.DecimalField(
        max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    amount_ttc = models.DecimalField(max_digits=14, decimal_places=2, editable=False)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.RECEIVED, db_index=True
    )
    created_by_user = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quotes_created",
    )
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ("-date", "-id")
        verbose_name = _("Devis")
        verbose_name_plural = _("Devis")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount_ht__gt=0, amount_tva__gte=0),
                name="quote_positive_amounts",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    amount_ttc=models.F("amount_ht") + models.F("amount_tva")
                ),
                name="quote_ttc_matches",
            ),
        ]

    def save(self, *args, **kwargs):
        self.amount_ttc = Decimal(self.amount_ht) + Decimal(self.amount_tva)
        if kwargs.get("update_fields"):
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {"amount_ttc"}
        super().save(*args, **kwargs)

    def __str__(self):
        return self.number


class QuoteAttachment(models.Model):
    """Pièce jointe liée à un devis."""

    quote = models.ForeignKey(
        Quote,
        on_delete=models.CASCADE,
        related_name="attachments",
        verbose_name=_("Devis"),
    )
    file = models.FileField(
        upload_to=quote_attachment_upload_to,
        verbose_name=_("Fichier"),
    )
    label = models.CharField(
        max_length=200, blank=True, null=True, verbose_name=_("Libellé")
    )
    uploaded_by_user = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quote_attachments_uploaded",
        verbose_name=_("Ajouté par"),
    )
    date_created = models.DateTimeField(
        auto_now_add=True, verbose_name=_("Date création")
    )

    class Meta:
        verbose_name = _("Pièce jointe devis")
        verbose_name_plural = _("Pièces jointes devis")
        ordering = ("-date_created", "-id")

    def __str__(self) -> str:
        return self.label or Path(self.file.name).name

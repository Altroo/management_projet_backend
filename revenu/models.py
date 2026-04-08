from django.db import models
from django.utils.translation import gettext_lazy as _
from simple_history.models import HistoricalRecords

from account.models import CustomUser
from project.models import Project


class Revenue(models.Model):
    """Entrée de revenu liée à un projet."""

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="revenues",
        verbose_name=_("Projet"),
    )
    date = models.DateField(
        verbose_name=_("Date"),
        db_index=True,
    )
    description = models.CharField(
        max_length=300,
        verbose_name=_("Description"),
        help_text=_("Description du revenu"),
    )
    montant = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name=_("Montant (Dhs)"),
    )
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Notes"),
    )
    created_by_user = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="revenues_created",
        verbose_name=_("Créé par"),
    )
    date_created = models.DateTimeField(
        auto_now_add=True, verbose_name=_("Date création")
    )
    date_updated = models.DateTimeField(
        auto_now=True, verbose_name=_("Date modification")
    )
    history = HistoricalRecords(
        verbose_name=_("Historique Revenu"),
        verbose_name_plural=_("Historiques Revenus"),
    )

    class Meta:
        verbose_name = _("Revenu")
        verbose_name_plural = _("Revenus")
        ordering = ("-date", "-id")

    def __str__(self) -> str:
        return f"{self.description} - {self.montant} Dhs"

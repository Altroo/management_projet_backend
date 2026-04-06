from django.db import models
from django.utils.translation import gettext_lazy as _
from simple_history.models import HistoricalRecords

from account.models import CustomUser
from project.models import Category, SubCategory, Project


class Expense(models.Model):
    """Entrée de dépense liée à un projet."""

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="expenses",
        verbose_name=_("Projet"),
    )
    date = models.DateField(
        verbose_name=_("Date"),
        db_index=True,
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expenses",
        verbose_name=_("Catégorie"),
    )
    sous_categorie = models.ForeignKey(
        SubCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expenses",
        verbose_name=_("Sous-catégorie"),
    )
    element = models.CharField(
        max_length=300,
        blank=True,
        null=True,
        verbose_name=_("Élément de dépenses"),
    )
    description = models.CharField(
        max_length=300,
        verbose_name=_("Description"),
        help_text=_("Description de la dépense"),
    )
    montant = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name=_("Montant total (Dhs)"),
    )
    fournisseur = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name=_("Fournisseur"),
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
        related_name="expenses_created",
        verbose_name=_("Créé par"),
    )
    date_created = models.DateTimeField(auto_now_add=True, verbose_name=_("Date création"))
    date_updated = models.DateTimeField(auto_now=True, verbose_name=_("Date modification"))
    history = HistoricalRecords(
        verbose_name=_("Historique Dépense"),
        verbose_name_plural=_("Historiques Dépenses"),
    )

    class Meta:
        verbose_name = _("Dépense")
        verbose_name_plural = _("Dépenses")
        ordering = ("-date", "-id")

    def __str__(self) -> str:
        return f"{self.description} - {self.montant} Dhs"

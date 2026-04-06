from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from simple_history.models import HistoricalRecords

from account.models import CustomUser


class Category(models.Model):
    """Catégorie de dépense (ex: Matériaux, Main d'œuvre, etc.)."""

    name = models.CharField(
        max_length=200,
        unique=True,
        verbose_name=_("Nom"),
        help_text=_("Nom de la catégorie"),
    )
    created_by_user = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="categories_created",
        verbose_name=_("Créé par"),
    )
    date_created = models.DateTimeField(auto_now_add=True, verbose_name=_("Date création"))
    date_updated = models.DateTimeField(auto_now=True, verbose_name=_("Date modification"))
    history = HistoricalRecords(
        verbose_name=_("Historique Catégorie"),
        verbose_name_plural=_("Historiques Catégories"),
    )

    class Meta:
        verbose_name = _("Catégorie")
        verbose_name_plural = _("Catégories")
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class SubCategory(models.Model):
    """Sous-catégorie de dépense, liée à une catégorie parente."""

    name = models.CharField(
        max_length=200,
        verbose_name=_("Nom"),
        help_text=_("Nom de la sous-catégorie"),
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="subcategories",
        verbose_name=_("Catégorie"),
    )
    created_by_user = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subcategories_created",
        verbose_name=_("Créé par"),
    )
    date_created = models.DateTimeField(auto_now_add=True, verbose_name=_("Date création"))
    date_updated = models.DateTimeField(auto_now=True, verbose_name=_("Date modification"))
    history = HistoricalRecords(
        verbose_name=_("Historique Sous-Catégorie"),
        verbose_name_plural=_("Historiques Sous-Catégories"),
    )

    class Meta:
        verbose_name = _("Sous-catégorie")
        verbose_name_plural = _("Sous-catégories")
        ordering = ("name",)
        unique_together = ("name", "category")

    def __str__(self) -> str:
        return self.name


class Project(models.Model):
    """Projet de gestion avec budget, dates et informations client."""

    STATUS_CHOICES = [
        ("Complété", _("Complété")),
        ("En cours", _("En cours")),
        ("Pas commencé", _("Pas commencé")),
        ("En attente", _("En attente")),
    ]

    nom = models.CharField(
        max_length=300,
        verbose_name=_("Nom du projet"),
        help_text=_("Nom du projet"),
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Description"),
        help_text=_("Description du projet"),
    )
    budget_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        verbose_name=_("Budget total (Dhs)"),
        help_text=_("Budget total alloué au projet"),
    )
    date_debut = models.DateField(
        verbose_name=_("Date de début"),
        help_text=_("Date de début du projet"),
    )
    date_fin = models.DateField(
        verbose_name=_("Date de fin"),
        help_text=_("Date de fin prévue du projet"),
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="Pas commencé",
        verbose_name=_("Statut"),
        db_index=True,
    )
    chef_de_projet = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name=_("Chef de projet"),
    )
    nom_client = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name=_("Nom du client"),
    )
    telephone_client = models.CharField(
        max_length=30,
        blank=True,
        null=True,
        verbose_name=_("Téléphone du client"),
    )
    email_client = models.EmailField(
        blank=True,
        null=True,
        verbose_name=_("Email du client"),
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
        related_name="projects_created",
        verbose_name=_("Créé par"),
    )
    date_created = models.DateTimeField(auto_now_add=True, verbose_name=_("Date création"))
    date_updated = models.DateTimeField(auto_now=True, verbose_name=_("Date modification"))
    history = HistoricalRecords(
        verbose_name=_("Historique Projet"),
        verbose_name_plural=_("Historiques Projets"),
    )

    class Meta:
        verbose_name = _("Projet")
        verbose_name_plural = _("Projets")
        ordering = ("-id",)

    def __str__(self) -> str:
        return self.nom

    @property
    def jours_restants(self) -> int:
        """Nombre de jours restants avant la date de fin."""
        delta = self.date_fin - timezone.now().date()
        return max(delta.days, 0)

    @property
    def revenue_total(self):
        """Somme de tous les revenus liés à ce projet."""
        from revenu.models import Revenue

        total = Revenue.objects.filter(project=self).aggregate(
            total=models.Sum("montant")
        )["total"]
        return total or 0

    @property
    def depenses_totales(self):
        """Somme de toutes les dépenses liées à ce projet."""
        from depense.models import Expense

        total = Expense.objects.filter(project=self).aggregate(
            total=models.Sum("montant")
        )["total"]
        return total or 0

    @property
    def benefice(self):
        """Bénéfice net = revenu total - dépenses totales."""
        return self.revenue_total - self.depenses_totales

    @property
    def marge(self):
        """Marge = bénéfice / revenu total (en %)."""
        rev = self.revenue_total
        if rev == 0:
            return 0
        return round((self.benefice / rev) * 100, 2)

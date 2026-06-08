from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from uuid import uuid4

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from simple_history.models import HistoricalRecords

from account.models import CustomUser


def project_attachment_upload_to(instance, filename):
    suffix = Path(filename).suffix
    return f"project_attachments/{instance.project_id}/{uuid4().hex}{suffix}"


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
    date_created = models.DateTimeField(
        auto_now_add=True, verbose_name=_("Date création")
    )
    date_updated = models.DateTimeField(
        auto_now=True, verbose_name=_("Date modification")
    )
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
    date_created = models.DateTimeField(
        auto_now_add=True, verbose_name=_("Date création")
    )
    date_updated = models.DateTimeField(
        auto_now=True, verbose_name=_("Date modification")
    )
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


class Client(models.Model):
    """Annuaire client réutilisable."""

    nom = models.CharField(max_length=200, unique=True, verbose_name=_("Nom"))
    telephone = models.CharField(
        max_length=30, blank=True, null=True, verbose_name=_("Téléphone")
    )
    email = models.EmailField(blank=True, null=True, verbose_name=_("Email"))
    adresse = models.TextField(blank=True, null=True, verbose_name=_("Adresse"))
    created_by_user = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clients_created",
        verbose_name=_("Créé par"),
    )
    date_created = models.DateTimeField(
        auto_now_add=True, verbose_name=_("Date création")
    )
    date_updated = models.DateTimeField(
        auto_now=True, verbose_name=_("Date modification")
    )
    history = HistoricalRecords(
        verbose_name=_("Historique Client"),
        verbose_name_plural=_("Historiques Clients"),
    )

    class Meta:
        verbose_name = _("Client")
        verbose_name_plural = _("Clients")
        ordering = ("nom",)

    def __str__(self) -> str:
        return self.nom


class Supplier(models.Model):
    """Annuaire fournisseur réutilisable."""

    nom = models.CharField(max_length=200, unique=True, verbose_name=_("Nom"))
    contact = models.CharField(
        max_length=200, blank=True, null=True, verbose_name=_("Contact")
    )
    specialite = models.CharField(
        max_length=200, blank=True, null=True, verbose_name=_("Spécialité")
    )
    created_by_user = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="suppliers_created",
        verbose_name=_("Créé par"),
    )
    date_created = models.DateTimeField(
        auto_now_add=True, verbose_name=_("Date création")
    )
    date_updated = models.DateTimeField(
        auto_now=True, verbose_name=_("Date modification")
    )
    history = HistoricalRecords(
        verbose_name=_("Historique Fournisseur"),
        verbose_name_plural=_("Historiques Fournisseurs"),
    )

    class Meta:
        verbose_name = _("Fournisseur")
        verbose_name_plural = _("Fournisseurs")
        ordering = ("nom",)

    def __str__(self) -> str:
        return self.nom


class Project(models.Model):
    """Projet de gestion avec budget, dates et informations client."""

    STATUS_CHOICES = [
        ("Complété", _("Complété")),
        ("En cours", _("En cours")),
        ("Pas commencé", _("Pas commencé")),
        ("En attente", _("En attente")),
        ("En pause", _("En pause")),
        ("Annulé", _("Annulé")),
        ("En attente de démarrage", _("En attente de démarrage")),
        ("Livré", _("Livré")),
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
        max_length=60,
        default="Pas commencé",
        verbose_name=_("Statut"),
        db_index=True,
    )
    client = models.ForeignKey(
        Client,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="projects",
        verbose_name=_("Client"),
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
    date_created = models.DateTimeField(
        auto_now_add=True, verbose_name=_("Date création")
    )
    date_updated = models.DateTimeField(
        auto_now=True, verbose_name=_("Date modification")
    )
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


class ProjectAttachment(models.Model):
    """Pièce jointe liée à un projet."""

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="attachments",
        verbose_name=_("Projet"),
    )
    file = models.FileField(
        upload_to=project_attachment_upload_to,
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
        related_name="project_attachments_uploaded",
        verbose_name=_("Ajouté par"),
    )
    date_created = models.DateTimeField(
        auto_now_add=True, verbose_name=_("Date création")
    )

    class Meta:
        verbose_name = _("Pièce jointe projet")
        verbose_name_plural = _("Pièces jointes projets")
        ordering = ("-date_created", "-id")

    def __str__(self) -> str:
        return self.label or Path(self.file.name).name


class ProjectPaymentSchedule(models.Model):
    """Échéance prévisionnelle d'encaissement liée à un projet."""

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="payment_schedules",
        verbose_name=_("Projet"),
    )
    due_date = models.DateField(verbose_name=_("Date prévue"), db_index=True)
    expected_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name=_("Montant prévu (Dhs)"),
    )
    description = models.CharField(
        max_length=300,
        blank=True,
        null=True,
        verbose_name=_("Description"),
    )
    notes = models.TextField(blank=True, null=True, verbose_name=_("Notes"))
    created_by_user = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_schedules_created",
        verbose_name=_("Créé par"),
    )
    date_created = models.DateTimeField(
        auto_now_add=True, verbose_name=_("Date création")
    )
    date_updated = models.DateTimeField(
        auto_now=True, verbose_name=_("Date modification")
    )
    history = HistoricalRecords(
        verbose_name=_("Historique Échéance Paiement"),
        verbose_name_plural=_("Historiques Échéances Paiements"),
    )

    class Meta:
        verbose_name = _("Échéance de paiement")
        verbose_name_plural = _("Échéances de paiements")
        ordering = ("due_date", "id")

    def __str__(self) -> str:
        return f"{self.project} - {self.due_date} - {self.expected_amount} Dhs"


class ProjectRealBudgetEntry(models.Model):
    """Opération réelle facturée au client et payée au fournisseur par étape."""

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="real_budget_entries",
        verbose_name=_("Projet"),
    )
    date = models.DateField(
        default=timezone.localdate,
        verbose_name=_("Date"),
        db_index=True,
    )
    stage = models.CharField(
        max_length=200,
        verbose_name=_("Étape du projet"),
        db_index=True,
    )
    description = models.CharField(
        max_length=300,
        blank=True,
        null=True,
        verbose_name=_("Description"),
    )
    montant_client = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name=_("Montant facturé au client (Dhs)"),
    )
    montant_fournisseur = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name=_("Montant payé au fournisseur (Dhs)"),
    )
    notes = models.TextField(blank=True, null=True, verbose_name=_("Notes"))
    created_by_user = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="real_budget_entries_created",
        verbose_name=_("Créé par"),
    )
    date_created = models.DateTimeField(
        auto_now_add=True, verbose_name=_("Date création")
    )
    date_updated = models.DateTimeField(
        auto_now=True, verbose_name=_("Date modification")
    )
    history = HistoricalRecords(
        verbose_name=_("Historique Budget réel"),
        verbose_name_plural=_("Historiques Budgets réels"),
    )

    class Meta:
        verbose_name = _("Budget réel projet")
        verbose_name_plural = _("Budgets réels projets")
        ordering = ("-date", "-id")

    def __str__(self) -> str:
        return f"{self.project} - {self.stage} - {self.benefice} Dhs"

    @property
    def benefice(self):
        return (self.montant_client or Decimal("0.00")) - (
            self.montant_fournisseur or Decimal("0.00")
        )

    @property
    def marge(self):
        if not self.montant_client:
            return Decimal("0.00")
        return ((self.benefice / self.montant_client) * Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

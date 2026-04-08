from django.db import models
from django.utils.translation import gettext_lazy as _
from simple_history.models import HistoricalRecords

from django.conf import settings


class NotificationPreference(models.Model):
    """User-specific notification preferences for project management events."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preference",
        verbose_name=_("Utilisateur"),
    )
    notify_budget_overrun = models.BooleanField(
        default=True,
        verbose_name=_("Notifier le dépassement de budget"),
    )
    notify_budget_threshold = models.BooleanField(
        default=True,
        verbose_name=_("Notifier les seuils de budget"),
    )
    notify_deadline_approaching = models.BooleanField(
        default=True,
        verbose_name=_("Notifier les délais approchants"),
    )
    notify_project_overdue = models.BooleanField(
        default=True,
        verbose_name=_("Notifier les projets en retard"),
    )
    notify_status_change = models.BooleanField(
        default=True,
        verbose_name=_("Notifier les changements de statut"),
    )
    budget_threshold_percent = models.PositiveIntegerField(
        default=80,
        verbose_name=_("Seuil d'alerte budget (%)"),
        help_text=_("Envoyer une alerte quand les dépenses atteignent ce % du budget"),
    )
    deadline_alert_days = models.PositiveIntegerField(
        default=7,
        verbose_name=_("Alerter X jours avant la date de fin"),
    )
    date_created = models.DateTimeField(
        auto_now_add=True, verbose_name=_("Date création")
    )
    date_updated = models.DateTimeField(
        auto_now=True, verbose_name=_("Date modification")
    )
    history = HistoricalRecords(
        verbose_name=_("Historique Préférence Notification"),
        verbose_name_plural=_("Historiques Préférences Notifications"),
    )

    class Meta:
        verbose_name = _("Préférence de notification")
        verbose_name_plural = _("Préférences de notification")

    def __str__(self) -> str:
        return f"Notifications — {self.user.email}"


class Notification(models.Model):
    """A notification sent to a user about a project management event."""

    NOTIFICATION_TYPES = [
        ("budget_overrun", _("Dépassement de budget")),
        ("budget_threshold", _("Seuil de budget atteint")),
        ("deadline_approaching", _("Délai approchant")),
        ("project_overdue", _("Projet en retard")),
        ("status_change", _("Changement de statut")),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name=_("Utilisateur"),
    )
    title = models.CharField(max_length=255, verbose_name=_("Titre"))
    message = models.TextField(verbose_name=_("Message"))
    notification_type = models.CharField(
        max_length=30,
        choices=NOTIFICATION_TYPES,
        verbose_name=_("Type"),
    )
    object_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("ID du projet lié"),
    )
    is_read = models.BooleanField(default=False, verbose_name=_("Lu"))
    date_created = models.DateTimeField(
        auto_now_add=True, verbose_name=_("Date création"), db_index=True
    )
    history = HistoricalRecords(
        verbose_name=_("Historique Notification"),
        verbose_name_plural=_("Historiques Notifications"),
    )

    class Meta:
        verbose_name = _("Notification")
        verbose_name_plural = _("Notifications")
        ordering = ("-date_created",)

    def __str__(self) -> str:
        return f"{self.title} — {self.user.email}"

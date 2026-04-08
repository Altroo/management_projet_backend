import json
import logging
from datetime import date, timedelta
from decimal import Decimal

from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model
from django.db.models import F, Sum
from django.utils.timezone import now

from notification.models import Notification, NotificationPreference
from project.models import Project

logger = logging.getLogger(__name__)
User = get_user_model()


def _broadcast(user_id: int, notification: Notification) -> None:
    """Send a WebSocket notification to a specific user's channel group."""
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    try:
        async_to_sync(channel_layer.group_send)(
            str(user_id),
            {
                "type": "receive_group_message",
                "message": {
                    "type": "NOTIFICATION",
                    "id": notification.pk,
                    "title": notification.title,
                    "message": notification.message,
                    "notification_type": notification.notification_type,
                    "object_id": notification.object_id,
                    "is_read": notification.is_read,
                    "date_created": notification.date_created.isoformat(),
                },
            },
        )
    except Exception as exc:
        logger.warning("WebSocket broadcast failed for user %s: %s", user_id, exc)


def _create_and_broadcast(
    user: User,
    title: str,
    message: str,
    notification_type: str,
    object_id: int | None = None,
) -> None:
    notification = Notification.objects.create(
        user=user,
        title=title,
        message=message,
        notification_type=notification_type,
        object_id=object_id,
    )
    _broadcast(user.pk, notification)


@shared_task(name="notification.check_project_notifications")
def check_project_notifications() -> None:
    """Periodic task: check all project-related notification conditions."""
    today = date.today()
    # Annotate projects with total expenses
    projects = Project.objects.annotate(
        total_depenses=Sum("expenses__montant")
    ).select_related()

    for pref in NotificationPreference.objects.select_related("user").iterator():
        user = pref.user

        # Determine which projects are relevant for this user
        if user.is_staff:
            user_projects = projects
        else:
            user_projects = projects.filter(membres=user)

        for project in user_projects:
            budget = project.budget_total or Decimal("0.00")
            depenses = project.total_depenses or Decimal("0.00")

            # Budget overrun
            if pref.notify_budget_overrun and budget > 0 and depenses > budget:
                already_sent = Notification.objects.filter(
                    user=user,
                    notification_type="budget_overrun",
                    object_id=project.pk,
                    date_created__date=today,
                    is_read=False,
                ).exists()
                if not already_sent:
                    _create_and_broadcast(
                        user,
                        title=f"Dépassement de budget — {project.nom}",
                        message=(
                            f'Le projet "{project.nom}" a dépassé son budget. '
                            f"Dépenses : {depenses} Dhs / Budget : {budget} Dhs."
                        ),
                        notification_type="budget_overrun",
                        object_id=project.pk,
                    )

            # Budget threshold
            if pref.notify_budget_threshold and budget > 0:
                threshold = Decimal(str(pref.budget_threshold_percent)) / Decimal("100")
                if depenses >= budget * threshold and depenses < budget:
                    already_sent = Notification.objects.filter(
                        user=user,
                        notification_type="budget_threshold",
                        object_id=project.pk,
                        date_created__date=today,
                        is_read=False,
                    ).exists()
                    if not already_sent:
                        _create_and_broadcast(
                            user,
                            title=f"Seuil de budget atteint — {project.nom}",
                            message=(
                                f'Le projet "{project.nom}" a atteint '
                                f"{pref.budget_threshold_percent}% de son budget. "
                                f"Dépenses : {depenses} Dhs / Budget : {budget} Dhs."
                            ),
                            notification_type="budget_threshold",
                            object_id=project.pk,
                        )

            # Skip deadline/overdue checks for completed projects
            if project.status in ("Complété",):
                continue

            # Deadline approaching
            if pref.notify_deadline_approaching and project.date_fin:
                alert_date = today + timedelta(days=pref.deadline_alert_days)
                if today <= project.date_fin <= alert_date:
                    already_sent = Notification.objects.filter(
                        user=user,
                        notification_type="deadline_approaching",
                        object_id=project.pk,
                        date_created__date=today,
                        is_read=False,
                    ).exists()
                    if not already_sent:
                        days_left = (project.date_fin - today).days
                        _create_and_broadcast(
                            user,
                            title=f"Délai approchant — {project.nom}",
                            message=(
                                f'Le projet "{project.nom}" se termine dans '
                                f"{days_left} jour(s) (le {project.date_fin})."
                            ),
                            notification_type="deadline_approaching",
                            object_id=project.pk,
                        )

            # Project overdue
            if pref.notify_project_overdue and project.date_fin:
                if project.date_fin < today and project.status == "En cours":
                    already_sent = Notification.objects.filter(
                        user=user,
                        notification_type="project_overdue",
                        object_id=project.pk,
                        date_created__date=today,
                        is_read=False,
                    ).exists()
                    if not already_sent:
                        days_late = (today - project.date_fin).days
                        _create_and_broadcast(
                            user,
                            title=f"Projet en retard — {project.nom}",
                            message=(
                                f'Le projet "{project.nom}" est en retard de '
                                f"{days_late} jour(s) (échéance : {project.date_fin})."
                            ),
                            notification_type="project_overdue",
                            object_id=project.pk,
                        )


def notify_project_status_change(
    project: Project, old_status: str, new_status: str
) -> None:
    """Called synchronously when a project status changes."""
    users = User.objects.filter(is_staff=True)
    for user in users:
        pref = NotificationPreference.objects.filter(user=user).first()
        if pref and not pref.notify_status_change:
            continue
        _create_and_broadcast(
            user,
            title=f"Statut mis à jour — {project.nom}",
            message=(
                f'Le statut du projet "{project.nom}" est passé '
                f'de "{old_status}" à "{new_status}".'
            ),
            notification_type="status_change",
            object_id=project.pk,
        )

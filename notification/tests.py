from datetime import date, timedelta
from unittest.mock import patch

import pytest

from account.models import CustomUser
from depense.models import Expense
from notification.models import Notification, NotificationPreference
from notification.tasks import check_project_notifications, notify_project_status_change
from project.models import Project

pytestmark = pytest.mark.django_db


def make_user(email, **kwargs):
    defaults = {"password": "securepass123"}
    defaults.update(kwargs)
    return CustomUser.objects.create_user(email=email, **defaults)


def make_project(created_by=None, **kwargs):
    defaults = {
        "nom": "Projet Notification",
        "budget_total": "1000.00",
        "date_debut": date.today() - timedelta(days=10),
        "date_fin": date.today() + timedelta(days=3),
        "status": "En cours",
        "chef_de_projet": "Chef Test",
        "nom_client": "Client Test",
    }
    defaults.update(kwargs)
    return Project.objects.create(created_by_user=created_by, **defaults)


def test_periodic_task_creates_missing_preferences_and_notifies_staff():
    user = make_user("boss@example.com", is_staff=True)
    NotificationPreference.objects.filter(user=user).delete()
    project = make_project(created_by=user, budget_total="1000.00")
    Expense.objects.create(
        project=project,
        date=date.today(),
        description="Dépense élevée",
        montant="1200.00",
        created_by_user=user,
    )

    with patch("notification.tasks._broadcast") as broadcast:
        check_project_notifications()

    assert NotificationPreference.objects.filter(user=user).exists()
    notification = Notification.objects.get(
        user=user,
        notification_type="budget_overrun",
        object_id=project.pk,
    )
    assert "Dépassement de budget" in notification.title
    broadcast.assert_called()


def test_periodic_task_uses_existing_project_fields_for_non_staff_users():
    user = make_user("readonly@example.com", is_staff=False, can_view=False)
    other_user = make_user("other@example.com", is_staff=False, can_view=False)
    own_project = make_project(created_by=user, nom="Projet utilisateur")
    other_project = make_project(created_by=other_user, nom="Projet autre")

    with patch("notification.tasks._broadcast"):
        check_project_notifications()

    assert Notification.objects.filter(
        user=user,
        notification_type="deadline_approaching",
        object_id=own_project.pk,
    ).exists()
    assert not Notification.objects.filter(user=user, object_id=other_project.pk).exists()


def test_status_change_notification_creates_missing_staff_preference():
    user = make_user("status-boss@example.com", is_staff=True)
    NotificationPreference.objects.filter(user=user).delete()
    project = make_project(created_by=user)

    with patch("notification.tasks._broadcast"):
        notify_project_status_change(project, "Pas commencé", "En cours")

    assert NotificationPreference.objects.filter(user=user).exists()
    assert Notification.objects.filter(
        user=user,
        notification_type="status_change",
        object_id=project.pk,
    ).exists()

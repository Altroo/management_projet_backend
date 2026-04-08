from rest_framework import serializers

from notification.models import Notification, NotificationPreference


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = [
            "id",
            "notify_budget_overrun",
            "notify_budget_threshold",
            "notify_deadline_approaching",
            "notify_project_overdue",
            "notify_status_change",
            "budget_threshold_percent",
            "deadline_alert_days",
            "date_created",
            "date_updated",
        ]
        read_only_fields = ["id", "date_created", "date_updated"]


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "title",
            "message",
            "notification_type",
            "object_id",
            "is_read",
            "date_created",
        ]
        read_only_fields = [
            "id",
            "title",
            "message",
            "notification_type",
            "object_id",
            "date_created",
        ]

from rest_framework import serializers

from .models import Revenue


class RevenueSerializer(serializers.ModelSerializer):
    """Serializer for Revenue CRUD."""

    project_name = serializers.CharField(source="project.nom", read_only=True)
    created_by_user_name = serializers.SerializerMethodField()

    @staticmethod
    def get_created_by_user_name(obj):
        if obj.created_by_user:
            name = f"{obj.created_by_user.first_name} {obj.created_by_user.last_name}".strip()
            return name or obj.created_by_user.email
        return None

    class Meta:
        model = Revenue
        fields = [
            "id",
            "project",
            "project_name",
            "date",
            "description",
            "montant",
            "notes",
            "created_by_user",
            "created_by_user_name",
            "date_created",
            "date_updated",
        ]
        read_only_fields = [
            "id",
            "project_name",
            "created_by_user",
            "created_by_user_name",
            "date_created",
            "date_updated",
        ]

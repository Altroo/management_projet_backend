from rest_framework import serializers

from .models import Expense


class ExpenseSerializer(serializers.ModelSerializer):
    """Serializer for Expense CRUD."""

    project_name = serializers.CharField(source="project.nom", read_only=True)
    category_name = serializers.CharField(
        source="category.name", read_only=True, default=None
    )
    sous_categorie_name = serializers.CharField(
        source="sous_categorie.name", read_only=True, default=None
    )
    created_by_user_name = serializers.SerializerMethodField()

    @staticmethod
    def get_created_by_user_name(obj):
        if obj.created_by_user:
            name = f"{obj.created_by_user.first_name} {obj.created_by_user.last_name}".strip()
            return name or obj.created_by_user.email
        return None

    class Meta:
        model = Expense
        fields = [
            "id",
            "project",
            "project_name",
            "date",
            "category",
            "category_name",
            "sous_categorie",
            "sous_categorie_name",
            "element",
            "description",
            "montant",
            "fournisseur",
            "notes",
            "created_by_user",
            "created_by_user_name",
            "date_created",
            "date_updated",
        ]
        read_only_fields = [
            "id",
            "project_name",
            "category_name",
            "sous_categorie_name",
            "created_by_user",
            "created_by_user_name",
            "date_created",
            "date_updated",
        ]

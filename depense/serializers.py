from decimal import Decimal

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
    frais_de_service_montant = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )

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
            "frais_de_service",
            "frais_de_service_valeur",
            "frais_de_service_type",
            "frais_de_service_montant",
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
            "frais_de_service_montant",
            "created_by_user",
            "created_by_user_name",
            "date_created",
            "date_updated",
        ]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        frais_de_service = attrs.get(
            "frais_de_service",
            getattr(self.instance, "frais_de_service", False),
        )
        value = attrs.get(
            "frais_de_service_valeur",
            getattr(self.instance, "frais_de_service_valeur", None),
        )
        fee_type = attrs.get(
            "frais_de_service_type",
            getattr(
                self.instance,
                "frais_de_service_type",
                Expense.SERVICE_FEE_TYPE_FIXED,
            ),
        )

        if not frais_de_service:
            attrs["frais_de_service_valeur"] = None
            attrs["frais_de_service_type"] = Expense.SERVICE_FEE_TYPE_FIXED
            return attrs

        if value is None:
            raise serializers.ValidationError(
                {"frais_de_service_valeur": "Ce champ est obligatoire."}
            )
        if value <= Decimal("0"):
            raise serializers.ValidationError(
                {"frais_de_service_valeur": "La valeur doit être supérieure à 0."}
            )
        if (
            fee_type == Expense.SERVICE_FEE_TYPE_PERCENTAGE
            and value > Decimal("100")
        ):
            raise serializers.ValidationError(
                {
                    "frais_de_service_valeur": (
                        "Le pourcentage doit être inférieur ou égal à 100."
                    )
                }
            )
        return attrs

from decimal import Decimal

from rest_framework import serializers

from .models import Expense, ExpenseAttachment


def _created_by_user_name(user):
    if user:
        name = f"{user.first_name} {user.last_name}".strip()
        return name or user.email
    return None


def _file_name(file_field):
    if not file_field:
        return None
    return file_field.name.rsplit("/", 1)[-1]


def _file_url(request, file_field):
    if not file_field:
        return None
    if request:
        return request.build_absolute_uri(file_field.url)
    return file_field.url


class ExpenseSerializer(serializers.ModelSerializer):
    """Serializer for Expense CRUD."""

    project_name = serializers.CharField(source="project.nom", read_only=True)
    category_name = serializers.CharField(
        source="category.name", read_only=True, default=None
    )
    sous_categorie_name = serializers.CharField(
        source="sous_categorie.name", read_only=True, default=None
    )
    supplier_name = serializers.CharField(source="supplier.nom", read_only=True, default=None)
    created_by_user_name = serializers.SerializerMethodField()
    frais_de_service_montant = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )

    @staticmethod
    def get_created_by_user_name(obj):
        return _created_by_user_name(obj.created_by_user)

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
            "supplier",
            "supplier_name",
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
            "supplier_name",
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


class ExpenseAttachmentSerializer(serializers.ModelSerializer):
    """Serializer for expense attachments."""

    file_url = serializers.SerializerMethodField()
    filename = serializers.SerializerMethodField()
    file_size = serializers.SerializerMethodField()
    uploaded_by_user_name = serializers.SerializerMethodField()

    def get_file_url(self, obj):
        return _file_url(self.context.get("request"), obj.file)

    @staticmethod
    def get_filename(obj):
        return _file_name(obj.file)

    @staticmethod
    def get_file_size(obj):
        if obj.file:
            try:
                return obj.file.size
            except OSError:
                return None
        return None

    @staticmethod
    def get_uploaded_by_user_name(obj):
        return _created_by_user_name(obj.uploaded_by_user)

    class Meta:
        model = ExpenseAttachment
        fields = [
            "id",
            "expense",
            "file",
            "file_url",
            "filename",
            "file_size",
            "label",
            "uploaded_by_user",
            "uploaded_by_user_name",
            "date_created",
        ]
        read_only_fields = [
            "id",
            "expense",
            "file_url",
            "filename",
            "file_size",
            "uploaded_by_user",
            "uploaded_by_user_name",
            "date_created",
        ]

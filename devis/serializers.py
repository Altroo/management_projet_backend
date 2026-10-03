from decimal import Decimal
from pathlib import Path
from rest_framework import serializers
from depense.serializers import _created_by_user_name, _file_name, _file_url
from .models import Quote, QuoteAttachment


class QuoteSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.nom", read_only=True)
    supplier_name = serializers.CharField(source="supplier.nom", read_only=True)
    category_name = serializers.CharField(
        source="category.name", read_only=True, default=None
    )
    sous_categorie_name = serializers.CharField(
        source="sous_categorie.name", read_only=True, default=None
    )
    created_by_user_name = serializers.SerializerMethodField()
    spent = serializers.DecimalField(
        max_digits=18, decimal_places=2, read_only=True, default=Decimal("0.00")
    )
    remaining = serializers.SerializerMethodField()
    variance = serializers.SerializerMethodField()
    consumption_percent = serializers.SerializerMethodField()
    overrun = serializers.SerializerMethodField()

    class Meta:
        model = Quote
        fields = [
            "id",
            "project",
            "project_name",
            "supplier",
            "supplier_name",
            "number",
            "date",
            "category",
            "category_name",
            "sous_categorie",
            "sous_categorie_name",
            "description",
            "amount_ht",
            "amount_tva",
            "amount_ttc",
            "status",
            "spent",
            "remaining",
            "variance",
            "consumption_percent",
            "overrun",
            "created_by_user",
            "created_by_user_name",
            "date_created",
            "date_updated",
        ]
        read_only_fields = [
            "amount_ttc",
            "created_by_user",
            "date_created",
            "date_updated",
        ]

    def get_created_by_user_name(self, obj):
        return _created_by_user_name(obj.created_by_user)

    def get_variance(self, obj):
        return str(obj.amount_ttc - getattr(obj, "spent", Decimal("0.00")))

    def get_remaining(self, obj):
        return str(max(Decimal("0.00"), Decimal(self.get_variance(obj))))

    def get_consumption_percent(self, obj):
        return (
            str(
                (getattr(obj, "spent", Decimal("0")) / obj.amount_ttc * 100).quantize(
                    Decimal("0.01")
                )
            )
            if obj.amount_ttc
            else None
        )

    def get_overrun(self, obj):
        return Decimal(self.get_variance(obj)) < 0

    def validate(self, attrs):
        def value(key):
            return attrs.get(key, getattr(self.instance, key, None))

        category, subcategory = value("category"), value("sous_categorie")
        if subcategory and (not category or subcategory.category_id != category.pk):
            raise serializers.ValidationError(
                {
                    "sous_categorie": "La sous-catégorie doit appartenir à la catégorie choisie."
                }
            )
        if value("amount_ht") + (value("amount_tva") or Decimal("0")) > Decimal(
            "999999999999.99"
        ):
            raise serializers.ValidationError(
                {"amount_ht": "Le montant TTC dépasse la limite autorisée."}
            )
        if self.instance and self.instance.expenses.exists():
            for field in ("project", "supplier", "category", "sous_categorie"):
                if value(field) != getattr(self.instance, field):
                    raise serializers.ValidationError(
                        {
                            field: "Ce devis est lié à des dépenses. Détachez-les avant de modifier ce champ."
                        }
                    )
            if value("status") != Quote.Status.VALIDATED:
                raise serializers.ValidationError(
                    {"status": "Un devis lié à des dépenses doit rester validé."}
                )
        return attrs


class QuoteAttachmentSerializer(serializers.ModelSerializer):
    """Serializer for quote attachments."""

    file_url = serializers.SerializerMethodField()
    filename = serializers.SerializerMethodField()
    file_size = serializers.SerializerMethodField()
    uploaded_by_user_name = serializers.SerializerMethodField()

    def validate_file(self, file):
        if Path(file.name).suffix.lower() not in {
            ".pdf",
            ".jpg",
            ".jpeg",
            ".png",
            ".webp",
            ".heic",
        }:
            raise serializers.ValidationError(
                "Formats acceptés : PDF, JPG, PNG, WEBP ou HEIC."
            )
        if file.size > 250 * 1024 * 1024:
            raise serializers.ValidationError("Le fichier ne doit pas dépasser 250 Mo.")
        return file

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
        model = QuoteAttachment
        fields = [
            "id",
            "quote",
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
            "quote",
            "file_url",
            "filename",
            "file_size",
            "uploaded_by_user",
            "uploaded_by_user_name",
            "date_created",
        ]

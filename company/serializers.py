from PIL import Image, UnidentifiedImageError
from rest_framework import serializers

from .models import CompanyProfile


class CompanyProfileSerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()
    remove_logo = serializers.BooleanField(
        default=False, required=False, write_only=True
    )

    class Meta:
        model = CompanyProfile
        fields = (
            "id",
            "raison_sociale",
            "logo",
            "logo_url",
            "remove_logo",
            "adresse",
            "telephone",
            "email",
            "site_web",
            "ICE",
            "registre_de_commerce",
            "identifiant_fiscal",
            "CNSS",
            "date_created",
            "date_updated",
        )
        read_only_fields = ("id", "logo_url", "date_created", "date_updated")
        extra_kwargs = {
            "logo": {"write_only": True, "required": False, "allow_null": True}
        }

    def get_logo_url(self, obj):
        if not obj.logo:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.logo.url) if request else obj.logo.url

    @staticmethod
    def validate_raison_sociale(value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("La raison sociale est obligatoire.")
        return value

    @staticmethod
    def validate_logo(value):
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("Le logo ne doit pas dépasser 10 Mo.")
        try:
            value.seek(0)
            Image.open(value).verify()
            value.seek(0)
        except (
            Image.DecompressionBombError,
            UnidentifiedImageError,
            OSError,
            ValueError,
        ):
            raise serializers.ValidationError("Le fichier doit être une image valide.")
        return value

    def update(self, instance, validated_data):
        remove_logo = validated_data.pop("remove_logo", False)
        previous_logo = instance.logo if instance.logo else None

        if remove_logo:
            validated_data["logo"] = None

        updated = super().update(instance, validated_data)
        logo_replaced = "logo" in validated_data and previous_logo
        if (remove_logo or logo_replaced) and previous_logo:
            previous_logo.delete(save=False)
        return updated

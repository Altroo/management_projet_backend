from PIL import Image, UnidentifiedImageError
from rest_framework import serializers

from .models import CompanyProfile


class CompanyProfileSerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()
    logo_cropped_url = serializers.SerializerMethodField()
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
            "logo_cropped",
            "logo_cropped_url",
            "remove_logo",
            "adresse",
            "telephone",
            "email",
            "site_web",
            "ICE",
            "registre_de_commerce",
            "numero_du_compte",
            "identifiant_fiscal",
            "CNSS",
            "date_created",
            "date_updated",
        )
        read_only_fields = (
            "id",
            "logo_url",
            "logo_cropped_url",
            "date_created",
            "date_updated",
        )
        extra_kwargs = {
            "logo": {"write_only": True, "required": False, "allow_null": True},
            "logo_cropped": {
                "write_only": True,
                "required": False,
                "allow_null": True,
            },
        }

    def get_logo_url(self, obj):
        if not obj.logo:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.logo.url) if request else obj.logo.url

    def get_logo_cropped_url(self, obj):
        if not obj.logo_cropped:
            return None
        request = self.context.get("request")
        return (
            request.build_absolute_uri(obj.logo_cropped.url)
            if request
            else obj.logo_cropped.url
        )

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

    validate_logo_cropped = validate_logo

    def update(self, instance, validated_data):
        remove_logo = validated_data.pop("remove_logo", False)
        previous_logo = instance.logo if instance.logo else None
        previous_cropped_logo = instance.logo_cropped if instance.logo_cropped else None

        if remove_logo:
            validated_data["logo"] = None
            validated_data["logo_cropped"] = None

        updated = super().update(instance, validated_data)
        logo_replaced = "logo" in validated_data and previous_logo
        cropped_logo_replaced = (
            "logo_cropped" in validated_data and previous_cropped_logo
        )
        if (remove_logo or logo_replaced) and previous_logo:
            previous_logo.storage.delete(previous_logo.name)
        if (remove_logo or cropped_logo_replaced) and previous_cropped_logo:
            previous_cropped_logo.storage.delete(previous_cropped_logo.name)
        return updated

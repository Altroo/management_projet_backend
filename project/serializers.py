from rest_framework import serializers

from .models import Category, SubCategory, Project


class CategorySerializer(serializers.ModelSerializer):
    """Serializer for Category CRUD."""

    created_by_user_name = serializers.SerializerMethodField()

    @staticmethod
    def get_created_by_user_name(obj):
        if obj.created_by_user:
            name = f"{obj.created_by_user.first_name} {obj.created_by_user.last_name}".strip()
            return name or obj.created_by_user.email
        return None

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "created_by_user",
            "created_by_user_name",
            "date_created",
            "date_updated",
        ]
        read_only_fields = [
            "id",
            "created_by_user",
            "created_by_user_name",
            "date_created",
            "date_updated",
        ]


class SubCategorySerializer(serializers.ModelSerializer):
    """Serializer for SubCategory CRUD."""

    category_name = serializers.CharField(source="category.name", read_only=True)
    created_by_user_name = serializers.SerializerMethodField()

    @staticmethod
    def get_created_by_user_name(obj):
        if obj.created_by_user:
            name = f"{obj.created_by_user.first_name} {obj.created_by_user.last_name}".strip()
            return name or obj.created_by_user.email
        return None

    class Meta:
        model = SubCategory
        fields = [
            "id",
            "name",
            "category",
            "category_name",
            "created_by_user",
            "created_by_user_name",
            "date_created",
            "date_updated",
        ]
        read_only_fields = [
            "id",
            "category_name",
            "created_by_user",
            "created_by_user_name",
            "date_created",
            "date_updated",
        ]


class ProjectListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for project list view."""

    created_by_user_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    jours_restants = serializers.IntegerField(read_only=True)
    revenue_total = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    depenses_totales = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    benefice = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    marge = serializers.DecimalField(
        max_digits=7, decimal_places=2, read_only=True
    )

    @staticmethod
    def get_created_by_user_name(obj):
        if obj.created_by_user:
            name = f"{obj.created_by_user.first_name} {obj.created_by_user.last_name}".strip()
            return name or obj.created_by_user.email
        return None

    class Meta:
        model = Project
        fields = [
            "id",
            "nom",
            "description",
            "budget_total",
            "date_debut",
            "date_fin",
            "status",
            "status_display",
            "chef_de_projet",
            "nom_client",
            "telephone_client",
            "email_client",
            "notes",
            "jours_restants",
            "revenue_total",
            "depenses_totales",
            "benefice",
            "marge",
            "created_by_user",
            "created_by_user_name",
            "date_created",
            "date_updated",
        ]


class ProjectSerializer(serializers.ModelSerializer):
    """Full serializer for Project CRUD."""

    created_by_user_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    jours_restants = serializers.IntegerField(read_only=True)
    revenue_total = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    depenses_totales = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    benefice = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    marge = serializers.DecimalField(
        max_digits=7, decimal_places=2, read_only=True
    )

    @staticmethod
    def get_created_by_user_name(obj):
        if obj.created_by_user:
            name = f"{obj.created_by_user.first_name} {obj.created_by_user.last_name}".strip()
            return name or obj.created_by_user.email
        return None

    class Meta:
        model = Project
        fields = [
            "id",
            "nom",
            "description",
            "budget_total",
            "date_debut",
            "date_fin",
            "status",
            "status_display",
            "chef_de_projet",
            "nom_client",
            "telephone_client",
            "email_client",
            "notes",
            "jours_restants",
            "revenue_total",
            "depenses_totales",
            "benefice",
            "marge",
            "created_by_user",
            "created_by_user_name",
            "date_created",
            "date_updated",
        ]
        read_only_fields = [
            "id",
            "status_display",
            "jours_restants",
            "revenue_total",
            "depenses_totales",
            "benefice",
            "marge",
            "created_by_user",
            "created_by_user_name",
            "date_created",
            "date_updated",
        ]

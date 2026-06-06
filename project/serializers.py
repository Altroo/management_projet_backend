from rest_framework import serializers

from .models import (
    Category,
    Client,
    Project,
    ProjectAttachment,
    ProjectPaymentSchedule,
    SubCategory,
    Supplier,
)


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


class CategorySerializer(serializers.ModelSerializer):
    """Serializer for Category CRUD."""

    created_by_user_name = serializers.SerializerMethodField()

    @staticmethod
    def get_created_by_user_name(obj):
        return _created_by_user_name(obj.created_by_user)

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
        return _created_by_user_name(obj.created_by_user)

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


class ExpenseTaxonomyCategorySerializer(serializers.ModelSerializer):
    """Serializer for nested expense taxonomy used by expense form CRUD."""

    subcategories = SubCategorySerializer(many=True, read_only=True)
    created_by_user_name = serializers.SerializerMethodField()

    @staticmethod
    def get_created_by_user_name(obj):
        return _created_by_user_name(obj.created_by_user)

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "created_by_user",
            "created_by_user_name",
            "date_created",
            "date_updated",
            "subcategories",
        ]
        read_only_fields = [
            "id",
            "created_by_user",
            "created_by_user_name",
            "date_created",
            "date_updated",
            "subcategories",
        ]


class ClientProjectHistorySerializer(serializers.ModelSerializer):
    """Compact project summary for client detail history."""

    revenue_total = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    depenses_totales = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    benefice = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = Project
        fields = [
            "id",
            "nom",
            "status",
            "budget_total",
            "date_debut",
            "date_fin",
            "revenue_total",
            "depenses_totales",
            "benefice",
        ]


class ClientSerializer(serializers.ModelSerializer):
    """Serializer for reusable clients."""

    created_by_user_name = serializers.SerializerMethodField()
    total_encaisse = serializers.SerializerMethodField()
    projects_count = serializers.SerializerMethodField()
    projects = serializers.SerializerMethodField()

    @staticmethod
    def get_created_by_user_name(obj):
        return _created_by_user_name(obj.created_by_user)

    @staticmethod
    def _projects_qs(obj):
        from django.db.models import Q

        return (
            Project.objects.filter(Q(client=obj) | Q(nom_client__iexact=obj.nom))
            .select_related("client")
            .distinct()
            .order_by("-id")
        )

    def get_total_encaisse(self, obj):
        from django.db.models import DecimalField, Sum, Q
        from django.db.models.functions import Coalesce
        from revenu.models import Revenue

        return Revenue.objects.filter(
            Q(project__client=obj) | Q(project__nom_client__iexact=obj.nom)
        ).aggregate(total=Coalesce(Sum("montant"), 0, output_field=DecimalField()))[
            "total"
        ]

    def get_projects_count(self, obj):
        return self._projects_qs(obj).count()

    def get_projects(self, obj):
        return ClientProjectHistorySerializer(self._projects_qs(obj), many=True).data

    class Meta:
        model = Client
        fields = [
            "id",
            "nom",
            "telephone",
            "email",
            "adresse",
            "total_encaisse",
            "projects_count",
            "projects",
            "created_by_user",
            "created_by_user_name",
            "date_created",
            "date_updated",
        ]
        read_only_fields = [
            "id",
            "total_encaisse",
            "projects_count",
            "projects",
            "created_by_user",
            "created_by_user_name",
            "date_created",
            "date_updated",
        ]


class SupplierSerializer(serializers.ModelSerializer):
    """Serializer for reusable suppliers and their payment history."""

    created_by_user_name = serializers.SerializerMethodField()
    total_paid = serializers.SerializerMethodField()
    payments_count = serializers.SerializerMethodField()
    payments = serializers.SerializerMethodField()

    @staticmethod
    def get_created_by_user_name(obj):
        return _created_by_user_name(obj.created_by_user)

    @staticmethod
    def _payments_qs(obj):
        from django.db.models import Q
        from depense.models import Expense

        return (
            Expense.objects.filter(Q(supplier=obj) | Q(fournisseur__iexact=obj.nom))
            .select_related("project")
            .distinct()
            .order_by("-date", "-id")
        )

    def get_total_paid(self, obj):
        from django.db.models import DecimalField, Sum, Q
        from django.db.models.functions import Coalesce
        from depense.models import Expense

        return Expense.objects.filter(
            Q(supplier=obj) | Q(fournisseur__iexact=obj.nom)
        ).aggregate(total=Coalesce(Sum("montant"), 0, output_field=DecimalField()))[
            "total"
        ]

    def get_payments_count(self, obj):
        return self._payments_qs(obj).count()

    def get_payments(self, obj):
        return [
            {
                "id": expense.id,
                "project": expense.project_id,
                "project_name": expense.project.nom,
                "date": expense.date,
                "description": expense.description,
                "montant": expense.montant,
            }
            for expense in self._payments_qs(obj)[:50]
        ]

    class Meta:
        model = Supplier
        fields = [
            "id",
            "nom",
            "contact",
            "specialite",
            "total_paid",
            "payments_count",
            "payments",
            "created_by_user",
            "created_by_user_name",
            "date_created",
            "date_updated",
        ]
        read_only_fields = [
            "id",
            "total_paid",
            "payments_count",
            "payments",
            "created_by_user",
            "created_by_user_name",
            "date_created",
            "date_updated",
        ]

class ProjectListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for project list view."""

    created_by_user_name = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    client_name = serializers.CharField(source="client.nom", read_only=True, default=None)
    jours_restants = serializers.IntegerField(read_only=True)
    revenue_total = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    depenses_totales = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    benefice = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    marge = serializers.DecimalField(max_digits=7, decimal_places=2, read_only=True)

    @staticmethod
    def get_created_by_user_name(obj):
        return _created_by_user_name(obj.created_by_user)

    @staticmethod
    def get_status_display(obj):
        return obj.status

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
            "client",
            "client_name",
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
    status_display = serializers.SerializerMethodField()
    client_name = serializers.CharField(source="client.nom", read_only=True, default=None)
    client_address = serializers.CharField(
        source="client.adresse", read_only=True, default=None
    )
    jours_restants = serializers.IntegerField(read_only=True)
    revenue_total = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    depenses_totales = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    benefice = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    marge = serializers.DecimalField(max_digits=7, decimal_places=2, read_only=True)

    @staticmethod
    def get_created_by_user_name(obj):
        return _created_by_user_name(obj.created_by_user)

    @staticmethod
    def get_status_display(obj):
        return obj.status

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
            "client",
            "client_name",
            "client_address",
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
            "client_name",
            "client_address",
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

    def validate(self, attrs):
        attrs = super().validate(attrs)
        client = attrs.get("client", getattr(self.instance, "client", None))
        if client:
            if not attrs.get("nom_client"):
                attrs["nom_client"] = client.nom
            if not attrs.get("telephone_client") and client.telephone:
                attrs["telephone_client"] = client.telephone
            if not attrs.get("email_client") and client.email:
                attrs["email_client"] = client.email
        return attrs


class ProjectAttachmentSerializer(serializers.ModelSerializer):
    """Serializer for project attachments."""

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
        model = ProjectAttachment
        fields = [
            "id",
            "project",
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
            "project",
            "file_url",
            "filename",
            "file_size",
            "uploaded_by_user",
            "uploaded_by_user_name",
            "date_created",
        ]


class ProjectPaymentScheduleSerializer(serializers.ModelSerializer):
    """Serializer for planned project payment schedule rows."""

    project_name = serializers.CharField(source="project.nom", read_only=True)
    created_by_user_name = serializers.SerializerMethodField()
    actual_amount = serializers.SerializerMethodField()
    expected_cumulative = serializers.SerializerMethodField()
    actual_cumulative = serializers.SerializerMethodField()
    variance = serializers.SerializerMethodField()

    @staticmethod
    def get_created_by_user_name(obj):
        return _created_by_user_name(obj.created_by_user)

    @staticmethod
    def _actual_cumulative(obj):
        from django.db.models import DecimalField, Sum
        from django.db.models.functions import Coalesce
        from revenu.models import Revenue

        return Revenue.objects.filter(
            project=obj.project,
            date__lte=obj.due_date,
        ).aggregate(total=Coalesce(Sum("montant"), 0, output_field=DecimalField()))[
            "total"
        ]

    @staticmethod
    def _expected_cumulative(obj):
        from django.db.models import DecimalField, Sum
        from django.db.models.functions import Coalesce

        return ProjectPaymentSchedule.objects.filter(
            project=obj.project,
            due_date__lte=obj.due_date,
        ).aggregate(
            total=Coalesce(Sum("expected_amount"), 0, output_field=DecimalField())
        )[
            "total"
        ]

    def get_actual_amount(self, obj):
        from django.db.models import DecimalField, Sum
        from django.db.models.functions import Coalesce
        from revenu.models import Revenue

        return Revenue.objects.filter(
            project=obj.project,
            date=obj.due_date,
        ).aggregate(total=Coalesce(Sum("montant"), 0, output_field=DecimalField()))[
            "total"
        ]

    def get_expected_cumulative(self, obj):
        return self._expected_cumulative(obj)

    def get_actual_cumulative(self, obj):
        return self._actual_cumulative(obj)

    def get_variance(self, obj):
        return self._actual_cumulative(obj) - self._expected_cumulative(obj)

    class Meta:
        model = ProjectPaymentSchedule
        fields = [
            "id",
            "project",
            "project_name",
            "due_date",
            "expected_amount",
            "description",
            "notes",
            "actual_amount",
            "expected_cumulative",
            "actual_cumulative",
            "variance",
            "created_by_user",
            "created_by_user_name",
            "date_created",
            "date_updated",
        ]
        read_only_fields = [
            "id",
            "project_name",
            "actual_amount",
            "expected_cumulative",
            "actual_cumulative",
            "variance",
            "created_by_user",
            "created_by_user_name",
            "date_created",
            "date_updated",
        ]

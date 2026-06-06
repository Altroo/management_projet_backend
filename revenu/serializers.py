from rest_framework import serializers

from .models import Revenue, RevenueAttachment


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


class RevenueSerializer(serializers.ModelSerializer):
    """Serializer for Revenue CRUD."""

    project_name = serializers.CharField(source="project.nom", read_only=True)
    created_by_user_name = serializers.SerializerMethodField()

    @staticmethod
    def get_created_by_user_name(obj):
        return _created_by_user_name(obj.created_by_user)

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


class RevenueAttachmentSerializer(serializers.ModelSerializer):
    """Serializer for revenue attachments."""

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
        model = RevenueAttachment
        fields = [
            "id",
            "revenue",
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
            "revenue",
            "file_url",
            "filename",
            "file_size",
            "uploaded_by_user",
            "uploaded_by_user_name",
            "date_created",
        ]

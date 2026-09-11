import company.models
from django.db import migrations, models


def seed_company_profile(apps, schema_editor):
    CompanyProfile = apps.get_model("company", "CompanyProfile")
    CompanyProfile.objects.get_or_create(
        singleton_key=True,
        defaults={"raison_sociale": "E.B.H Gestion Projet"},
    )


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="CompanyProfile",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "singleton_key",
                    models.BooleanField(default=True, editable=False, unique=True),
                ),
                (
                    "raison_sociale",
                    models.CharField(
                        default="E.B.H Gestion Projet",
                        max_length=255,
                        verbose_name="Raison sociale",
                    ),
                ),
                (
                    "logo",
                    models.ImageField(
                        blank=True,
                        max_length=1000,
                        null=True,
                        upload_to=company.models.company_logo_upload_to,
                        verbose_name="Logo",
                    ),
                ),
                (
                    "adresse",
                    models.TextField(blank=True, null=True, verbose_name="Adresse"),
                ),
                (
                    "telephone",
                    models.CharField(
                        blank=True, max_length=30, null=True, verbose_name="Téléphone"
                    ),
                ),
                (
                    "email",
                    models.EmailField(
                        blank=True, max_length=254, null=True, verbose_name="E-mail"
                    ),
                ),
                (
                    "site_web",
                    models.URLField(blank=True, null=True, verbose_name="Site web"),
                ),
                (
                    "ICE",
                    models.CharField(
                        blank=True, max_length=100, null=True, verbose_name="ICE"
                    ),
                ),
                (
                    "registre_de_commerce",
                    models.CharField(
                        blank=True,
                        max_length=100,
                        null=True,
                        verbose_name="Registre de commerce",
                    ),
                ),
                (
                    "identifiant_fiscal",
                    models.CharField(
                        blank=True,
                        max_length=100,
                        null=True,
                        verbose_name="Identifiant fiscal",
                    ),
                ),
                (
                    "CNSS",
                    models.CharField(
                        blank=True, max_length=100, null=True, verbose_name="CNSS"
                    ),
                ),
                ("date_created", models.DateTimeField(auto_now_add=True)),
                ("date_updated", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Profil société",
                "verbose_name_plural": "Profil société",
            },
        ),
        migrations.RunPython(seed_company_profile, migrations.RunPython.noop),
    ]

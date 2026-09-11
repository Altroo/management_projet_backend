import company.models
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("company", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="companyprofile",
            name="logo_cropped",
            field=models.ImageField(
                blank=True,
                max_length=1000,
                null=True,
                upload_to=company.models.company_logo_upload_to,
                verbose_name="Logo recadré",
            ),
        ),
        migrations.AddField(
            model_name="companyprofile",
            name="numero_du_compte",
            field=models.CharField(
                blank=True,
                max_length=100,
                null=True,
                verbose_name="Numéro du compte",
            ),
        ),
    ]

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("project", "0003_seed_statuses_and_clients"),
    ]

    operations = [
        migrations.DeleteModel(name="HistoricalProjectStatus"),
        migrations.DeleteModel(name="ProjectStatus"),
    ]

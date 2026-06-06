from django.db import migrations


PROJECT_STATUSES = [
    ("Complété", "success", 10),
    ("En cours", "info", 20),
    ("Pas commencé", "default", 30),
    ("En attente", "warning", 40),
    ("En pause", "warning", 50),
    ("Annulé", "error", 60),
    ("En attente de démarrage", "info", 70),
    ("Livré", "success", 80),
]


def seed_statuses_and_clients(apps, schema_editor):
    Project = apps.get_model("project", "Project")
    ProjectStatus = apps.get_model("project", "ProjectStatus")
    Client = apps.get_model("project", "Client")

    for name, color, ordering in PROJECT_STATUSES:
        status, created = ProjectStatus.objects.get_or_create(
            name=name,
            defaults={
                "color": color,
                "ordering": ordering,
                "is_active": True,
            },
        )
        if not created:
            changed = False
            if not status.color:
                status.color = color
                changed = True
            if status.ordering == 0:
                status.ordering = ordering
                changed = True
            if not status.is_active:
                status.is_active = True
                changed = True
            if changed:
                status.save(update_fields=["color", "ordering", "is_active"])

    projects = Project.objects.exclude(nom_client__isnull=True).exclude(nom_client="")
    for project in projects.iterator():
        client_name = (project.nom_client or "").strip()
        if not client_name:
            continue

        client, _ = Client.objects.get_or_create(
            nom=client_name,
            defaults={
                "telephone": project.telephone_client or None,
                "email": project.email_client or None,
            },
        )

        changed_client = False
        if not client.telephone and project.telephone_client:
            client.telephone = project.telephone_client
            changed_client = True
        if not client.email and project.email_client:
            client.email = project.email_client
            changed_client = True
        if changed_client:
            client.save(update_fields=["telephone", "email"])

        if project.client_id is None:
            project.client_id = client.id
            project.save(update_fields=["client"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("project", "0002_alter_historicalproject_status_alter_project_status_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_statuses_and_clients, noop_reverse),
    ]

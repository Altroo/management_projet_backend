"""Source snapshots shared by save hooks, backfill and financial reports."""
from django.apps import apps
from .pdf_translation import source, ensure_sources

NAMESPACE = "management_projet"
REGISTRY = (
    ("project.Project", ("description", "notes")),
    ("project.Category", ("name",)),
    ("project.SubCategory", ("name",)),
    ("revenu.Revenue", ("description", "notes")),
    ("depense.Expense", ("element", "description", "notes")),
    ("project.ProjectPaymentSchedule", ("description", "notes")),
)


def specifications(values, names=None):
    if names is None:
        from .service import AiAssistantService
        names = AiAssistantService._known_names()
    return list({spec.fingerprint: spec for value in values
                 if (spec := source(value, names)) is not None}.values())


def instance_sources(instance, names=None):
    fields = next(fields for label, fields in REGISTRY
                  if instance._meta.label_lower == label.lower())
    return specifications([getattr(instance, field) for field in fields], names)


def prepare_saved(sender, instance, raw=False, update_fields=None, **kwargs):
    from .pdf_translation import translation_enabled
    if raw or not translation_enabled():
        return
    fields = next(fields for label, fields in REGISTRY
                  if sender._meta.label_lower == label.lower())
    if update_fields is None or set(fields).intersection(update_fields):
        ensure_sources(NAMESPACE, instance_sources(instance))


def connect():
    from django.db.models.signals import post_save
    for label, fields in REGISTRY:
        post_save.connect(prepare_saved, sender=apps.get_model(label),
                          dispatch_uid="prepare_pdf_" + label)

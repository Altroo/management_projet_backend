from datetime import date, timedelta
from unittest.mock import patch
import pytest
from django.core.cache import cache
from django.utils import timezone
from ai_assistant.models import PdfTextTranslation
from ai_assistant.pdf_translation import ensure_sources, load_pdf_translations, source, validate_saved_translation
from ai_assistant.tasks import translate_pending_pdf_texts, backfill_pdf_translations, quota_key
from ai_assistant.service import AiAssistantService
from ai_assistant.exceptions import PdfTranslationPending, PdfTranslationDeferred, InvalidModelResponse
from ai_assistant.pdf_sources import instance_sources, NAMESPACE
from project.test_reports import make_project

pytestmark = pytest.mark.django_db

@pytest.fixture(autouse=True)
def preparation_settings(settings):
    settings.AI_PDF_TRANSLATION_ENABLED = True
    settings.AI_GROQ_APPLICATIONS = ("management_projet",)
    settings.CELERY_TASK_ALWAYS_EAGER = False
    cache.clear()
    with patch("ai_assistant.pdf_translation.dispatch_pending") as dispatch, patch.object(translate_pending_pdf_texts, "apply_async"):
        yield dispatch


def test_new_or_edited_pdf_text_never_uses_an_old_cached_value():
    spec = source("Livrer avant midi")
    ensure_sources("casa_di_lusso", [spec], ["en"], dispatch=False)
    with pytest.raises(PdfTranslationPending):
        load_pdf_translations("casa_di_lusso", [spec], "en")
    PdfTextTranslation.objects.update(
        status="ready", translated_text="Deliver before noon"
    )
    with patch.object(AiAssistantService, "translate_many") as model:
        assert (
            load_pdf_translations("casa_di_lusso", [spec], "en")[spec.text]
            == "Deliver before noon"
        )
    model.assert_not_called()
    with pytest.raises(PdfTranslationPending):
        load_pdf_translations("casa_di_lusso", [source("Livrer après midi")], "en")
    with pytest.raises(PdfTranslationPending):
        load_pdf_translations("blueline", [spec], "en")


def test_worker_persists_valid_text_and_rejects_broken_layout():
    spec = source("• Livrer 120*120cm.\n• Marbre non compris.")
    ensure_sources("casa_di_lusso", [spec], ["en"], dispatch=False)
    with patch.object(
        AiAssistantService,
        "translate_many",
        return_value={spec.text: "• Deliver 120*120cm.\n• Marble not included."},
    ) as client:
        translate_pending_pdf_texts()
    assert PdfTextTranslation.objects.get().status == "ready"
    assert client.call_args.kwargs["context"] == "project"
    row = PdfTextTranslation.objects.get()
    for broken in [
        "Deliver 120*120cm. Marble not included.",
        "• Deliver 120x120cm.\n• Marble not included.",
        "• Deliver 120*120cm.\n• Marble included.",
    ]:
        with pytest.raises(InvalidModelResponse):
            validate_saved_translation(row, broken)


def test_quota_deadlines_do_not_extend_and_foreground_can_use_reserved_capacity():
    from rest_framework.exceptions import Throttled

    ensure_sources(
        "casa_di_lusso",
        [source("Chaise en bois")],
        ["en"],
        priority=100,
        dispatch=False,
    )
    with patch.object(
        AiAssistantService, "translate_many", side_effect=Throttled(wait=60)
    ):
        translate_pending_pdf_texts()
    deadline = cache.get(quota_key(100))
    ensure_sources(
        "casa_di_lusso", [source("Table en bois")], ["en"], priority=100, dispatch=False
    )
    for _ in range(10):
        translate_pending_pdf_texts()
    assert cache.get(quota_key(100)) == deadline
    ensure_sources(
        "casa_di_lusso", [source("Lampe en bois")], ["en"], priority=0, dispatch=False
    )
    with patch.object(
        AiAssistantService,
        "translate_many",
        return_value={"Lampe en bois": "Wooden lamp"},
    ):
        translate_pending_pdf_texts()
    assert PdfTextTranslation.objects.get(source_text="Lampe en bois").status == "ready"
    assert not PdfTextTranslation.objects.exclude(attempts=0).exists()


def test_quota_deferred_pdf_does_not_wait_for_sync_translation():
    spec = source("Livrer avant midi")
    ensure_sources("casa_di_lusso", [spec], ["en"], priority=0, dispatch=False)
    PdfTextTranslation.objects.update(
        last_error="ai_rate_limited", available_at=timezone.now() - timedelta(seconds=1)
    )
    with pytest.raises(PdfTranslationDeferred):
        load_pdf_translations("casa_di_lusso", [spec], "en")



def test_save_is_durable_and_async(django_capture_on_commit_callbacks, preparation_settings):
    with patch.object(AiAssistantService, "translate_many") as model, django_capture_on_commit_callbacks(execute=True):
        project = make_project()
        project.notes = "• Marbre non compris.\n  • Pose 120*120cm."
        project.save(update_fields=["notes"])
        assert PdfTextTranslation.objects.filter(source_text=project.notes).count() == 2
        preparation_settings.assert_not_called()
    preparation_settings.assert_called_once()
    model.assert_not_called()
    project.refresh_from_db()
    assert "Marbre non compris" in project.notes


def test_save_rollback_removes_translation_rows(django_capture_on_commit_callbacks, preparation_settings):
    from django.db import transaction
    with django_capture_on_commit_callbacks(execute=True):
        with pytest.raises(ValueError), transaction.atomic():
            project = make_project()
            project.notes = "Notes annulées"
            project.save(update_fields=["notes"])
            raise ValueError("rollback")
    assert not PdfTextTranslation.objects.exists()
    preparation_settings.assert_not_called()


def test_backfill_is_bounded_idempotent(settings):
    settings.AI_PDF_TRANSLATION_ENABLED = False
    project = make_project()
    project.notes = "Contenu historique"
    project.save(update_fields=["notes"])
    settings.AI_PDF_TRANSLATION_ENABLED = True
    with patch.object(backfill_pdf_translations, "apply_async") as next_job, patch.object(translate_pending_pdf_texts, "delay"):
        assert backfill_pdf_translations()["scanned"] == 1
        backfill_pdf_translations()
    assert PdfTextTranslation.objects.count() == 2
    assert set(PdfTextTranslation.objects.values_list("priority", flat=True)) == {100}
    assert next_job.call_args.kwargs["kwargs"]["model_index"] == 1


def test_pdf_cache_render_preserves_lines_without_model_requests(settings):
    from project.pdf import build_financial_report_pdf, _text
    project = make_project()
    project.notes = "• Marbre non compris.\n  • Pose 120*120cm."
    project.save(update_fields=["notes"])
    for row in PdfTextTranslation.objects.all():
        row.translated_text = row.source_text if row.language == "fr" else "• Marble not included.\n  • Install 120*120cm."
        row.status = "ready"
        row.save()
    with patch.object(AiAssistantService, "translate_many") as model:
        assert build_financial_report_pdf(project=project, language="en").read(5) == b"%PDF-"
    model.assert_not_called()
    assert _text("• A & B\n  • <Suite>") == "• A &amp; B<br/>&#160;&#160;• &lt;Suite&gt;"
    project.refresh_from_db()
    assert "Marbre" in project.notes


def test_estimate_categories_use_stored_translation():
    from project.pdf import _estimate_comparison, _styles
    project = make_project()
    summary = {"advances": 0, "unlinked_spent": 0, "validated_count": 1, "by_category": [{"category_name": "Plomberie", "estimated": 100, "spent": 10, "variance": -90, "remaining": 90, "overrun": False}], "estimated": 100, "spent": 10, "variance": -90, "remaining": 90, "overrun": False}
    with patch("devis.services.project_estimate_summary", return_value=summary), patch("project.pdf.load_pdf_translations", return_value={"Plomberie": "Plumbing"}) as lookup:
        _estimate_comparison(project, "en", 520, _styles())
    assert summary["by_category"][0]["category_name"] == "Plumbing"
    assert lookup.call_args.args[1][0].text == "Plomberie"


def test_pending_endpoint_returns_queue_status():
    from project.test_reports import make_user
    from django.urls import reverse
    project = make_project()
    project.notes = "En attente de traduction"
    project.save(update_fields=["notes"])
    with patch.object(AiAssistantService, "translate_many") as model:
        response = make_user().get(reverse("project:financial-report-pdf-en"), {"project_id": project.pk})
    assert response.status_code == 409
    assert "pdf_translation_pending" in str(response.data)
    model.assert_not_called()



def test_french_pdf_uses_original_source_before_reading_translation_rows():
    value = "Location STORE N° 42"
    with patch.object(PdfTextTranslation.objects, "filter") as lookup:
        assert load_pdf_translations("casa_di_lusso", [source(value)], "fr") == {value: value}

    lookup.assert_not_called()

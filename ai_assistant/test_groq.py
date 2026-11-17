import json
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.core.cache import caches
from django.test import override_settings

from .exceptions import InvalidModelResponse, ModelUnavailable
from .groq_budget import GroqBudget, GroqQuotaDeferred
from .groq_integrity import Document
from .groq_provider import GroqTextService, enabled_for, split_text


@pytest.fixture(autouse=True)
def groq_settings(settings):
    settings.GROQ_API_KEY = "test-groq-key-not-a-real-credential"
    settings.GROQ_MODEL = "openai/gpt-oss-120b"
    settings.GROQ_TIMEOUT_SECONDS = 30
    settings.GROQ_MAX_COMPLETION_TOKENS = 3200
    settings.GROQ_RPM = 28
    settings.GROQ_RPD = 900
    settings.GROQ_TPM = 7000
    settings.GROQ_TPD = 180000
    settings.GROQ_BACKGROUND_SHARE = 0.8
    settings.AI_GROQ_APPLICATIONS = {"facturation"}
    caches["ai_assistant"].clear()


def response(document, en, nl=None, source="fr", id="0"):
    ids = [line["id"] for line in document.model_lines]
    return {
        "id": id,
        "source_language": source,
        "translations": {
            "fr": [],
            "en": [{"id": key, "text": text} for key, text in zip(ids, en)],
            "nl": [
                {"id": key, "text": text}
                for key, text in zip(ids, nl if nl is not None else en)
            ],
        },
    }


class FakeClient:
    def __init__(self, *values):
        self.values = list(values)
        self.calls = []

    def complete(self, jobs, **kwargs):
        self.calls.append((jobs, kwargs))
        value = self.values.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def test_layout_markers_blank_lines_and_crlf_are_preserved():
    source = "  • Livrer 278*120cm.\r\n\r\n\t2. Marbre non compris.\r\n"
    document = Document(source)
    first = document.model_lines[0]["text"].split()[-1]
    assert "278*120cm" not in json.dumps(document.model_lines)
    result = document.restore(
        [
            {"id": "0", "text": "Deliver " + first},
            {"id": "2", "text": "Marble not included."},
        ],
        "en",
        "translate",
    )
    assert result == "  • Deliver 278*120cm.\r\n\r\n\t2. Marble not included.\r\n"


@pytest.mark.parametrize(
    "target",
    [
        "Tiles ZXQVAL00000X cm.",
        "Tiles ZXQVAL00000Xcm.",
        "Tiles 120x120cm.",
        "Tiles ZXQVAL00000X and ZXQVAL00000X.",
        "Tiles ZXQVAL00001X.",
    ],
)
def test_dimensions_cannot_be_reformatted_duplicated_or_given_an_invented_unit(target):
    doc = Document("Carreaux 120*120.")
    with pytest.raises(InvalidModelResponse):
        doc.restore([{"id": "0", "text": target}], "en", "translate")


def test_quantities_cannot_swallow_line_breaks():
    doc = Document("1. Livrer 50 %\n2. Régler 50 %")
    assert len(doc.model_lines) == 2
    assert all(
        "\n" not in value for line in doc.lines for value in line.replacements.values()
    )


@pytest.mark.parametrize(
    "target",
    [
        [{"id": "0", "text": "One paragraph."}],
        [{"id": "0", "text": "First.\nSecond."}, {"id": "1", "text": "Second."}],
        [{"id": "0", "text": "First."}, {"id": "0", "text": "Second."}],
    ],
)
def test_missing_merged_or_duplicate_lines_are_rejected(target):
    doc = Document("Première ligne.\nDeuxième ligne.")
    with pytest.raises(InvalidModelResponse):
        doc.restore(target, "en", "translate")


def test_owner_responsibility_error_is_rejected():
    doc = Document("Isolation: fournitures à la charge du maître d'ouvrage.")
    with pytest.raises(InvalidModelResponse):
        doc.restore(
            [{"id": "0", "text": "Insulation: supplies to the contractor."}],
            "en",
            "translate",
        )
    assert "project owner" in doc.restore(
        [{"id": "0", "text": "Insulation: materials at the project owner's expense."}],
        "en",
        "translate",
    )


@pytest.mark.parametrize("action", ["fix_grammar", "professionalize"])
def test_edit_actions_cannot_reverse_responsibility_or_remove_exclusions(action):
    owner = Document("Fournitures à la charge du maître d'ouvrage.")
    with pytest.raises(InvalidModelResponse):
        owner.restore(
            [{"id": "0", "text": "Fournitures à la charge de l'entrepreneur."}],
            "fr",
            action,
        )
    exclusion = Document("Marbre non compris.")
    with pytest.raises(InvalidModelResponse):
        exclusion.restore([{"id": "0", "text": "Marble included."}], "en", action)


@pytest.mark.parametrize(
    "source,target",
    [
        ("Quantité selon métrage réel des travaux.", "Quantity according to film."),
        ("Travaux de masticage.", "Masticating work."),
        ("Avec trop plein.", "With too full."),
        ("Bonde non incluse.", "Bond not included."),
    ],
)
def test_known_technical_mistranslations_are_rejected(source, target):
    with pytest.raises(InvalidModelResponse):
        Document(source).restore([{"id": "0", "text": target}], "en", "translate")


def test_masked_cache_reuses_translation_without_leaking_company_or_values():
    first = Document("Livrer 120*120cm pour Maison Atlas.", {"Maison Atlas"})
    generated = response(
        first,
        ["Deliver ZXQVAL00000X for ZXQVAL00001X."],
        ["Lever ZXQVAL00000X voor ZXQVAL00001X."],
    )
    client = FakeClient({"items": [generated]})
    service = GroqTextService(client)
    a = service.translate_many(
        [first.text],
        target_language="en",
        application="facturation",
        protected_terms=["Maison Atlas"],
    )
    second = "Livrer 278*120cm pour Maison Boréal."
    b = service.translate_many(
        [second],
        target_language="nl",
        application="facturation",
        protected_terms=["Maison Boréal"],
    )
    assert a[first.text] == "Deliver 120*120cm for Maison Atlas."
    assert b[second] == "Lever 278*120cm voor Maison Boréal."
    assert len(client.calls) == 1
    payload = json.dumps(client.calls)
    assert "Maison Atlas" not in payload and "120*120cm" not in payload


def test_source_language_is_returned_verbatim():
    doc = Document("Livrer avant midi.\n")
    client = FakeClient(
        {"items": [response(doc, ["Deliver before noon."], ["Lever voor de middag."])]}
    )
    result = GroqTextService(client).translate_many(
        [doc.text], target_language="fr", application="facturation"
    )
    assert result[doc.text] == doc.text


def test_invalid_response_is_retried_but_never_cached():
    doc = Document("Carreaux 120*120cm.")
    bad = response(doc, ["Tiles 120x120cm."])
    client = FakeClient({"items": [bad]}, {"items": [bad]})
    with pytest.raises(InvalidModelResponse):
        GroqTextService(client).translate_many(
            [doc.text], target_language="en", application="facturation"
        )
    assert len(client.calls) == 2
    assert client.calls[1][1]["correction"]


def test_rate_limit_is_not_retried_synchronously():
    client = FakeClient(GroqQuotaDeferred(wait=3600))
    with pytest.raises(GroqQuotaDeferred) as exc:
        GroqTextService(client).translate_many(
            ["Livrer avant midi."],
            target_language="en",
            application="facturation",
            background=True,
        )
    assert exc.value.wait == 3600 and len(client.calls) == 1


def test_opaque_and_unit_only_fields_do_not_call_the_provider():
    client = FakeClient()
    texts = ["m²", "ABC-123", "1 676,80 EUR", "A" * 2200]
    assert GroqTextService(client).translate_many(
        texts, target_language="en", application="facturation"
    ) == {value: value for value in texts}
    assert not client.calls


def test_split_text_preserves_every_character_and_stays_bounded():
    text = ("Première phrase. Deuxième phrase.\n" * 150) + "Fin."
    parts = split_text(text, 1800)
    assert "".join(parts) == text
    assert all(len(part) <= 1800 for part in parts)


def test_only_enabled_application_uses_groq():
    assert enabled_for("facturation")
    assert not enabled_for("management_projet")


@pytest.fixture
def redis_client(tmp_path):
    import subprocess, tempfile, redis
    from redis.backoff import NoBackoff
    from redis.retry import Retry

    directory = tempfile.TemporaryDirectory(prefix="groq-redis-", dir="/tmp")
    socket = directory.name + "/redis.sock"
    process = subprocess.Popen(
        [
            "redis-server",
            "--port",
            "0",
            "--unixsocket",
            socket,
            "--save",
            "",
            "--appendonly",
            "no",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    client = redis.Redis(
        unix_socket_path=socket,
        socket_connect_timeout=0.1,
        socket_timeout=0.5,
        retry=Retry(NoBackoff(), 0),
    )
    try:
        for _ in range(100):
            try:
                if client.ping():
                    break
            except redis.RedisError:
                time.sleep(0.02)
        else:
            raise RuntimeError("test Redis did not start")
        yield client
    finally:
        client.close()
        process.terminate()
        process.wait(timeout=5)
        directory.cleanup()


def test_global_quota_is_atomic_across_parallel_requests(settings, redis_client):
    settings.GROQ_RPM = 2
    budget = GroqBudget(redis_client, clock=lambda now=time.time(): now)

    def reserve(_):
        try:
            budget.reserve(100)
            return True
        except GroqQuotaDeferred:
            return False

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(reserve, range(10)))
    assert sum(results) == 2


def test_daily_budget_reserves_capacity_for_interactive_requests(
    settings, redis_client
):
    settings.GROQ_TPD = 1000
    budget = GroqBudget(redis_client, clock=lambda now=time.time(): now)
    reservation = budget.reserve(700, background=True)
    budget.settle(reservation, 700)
    with pytest.raises(GroqQuotaDeferred):
        budget.reserve(150, background=True)
    assert budget.reserve(150, background=False)


def test_actual_usage_refunds_unused_reservation_only_once(redis_client):
    budget = GroqBudget(redis_client, clock=lambda now=time.time(): now)
    reservation = budget.reserve(1000)
    budget.settle(reservation, 200)
    budget.settle(reservation, 200)
    assert int(redis_client.hget(reservation.day_key, "tokens")) == 200


def test_provider_retry_after_is_shared_between_apps(redis_client):
    a = GroqBudget(redis_client, clock=lambda now=time.time(): now)
    b = GroqBudget(redis_client, clock=lambda now=time.time(): now)
    a.block(3600)
    with pytest.raises(GroqQuotaDeferred) as exc:
        b.reserve(100)
    assert exc.value.wait == 3600


@pytest.mark.parametrize(
    "source,target,language",
    [
        ("Marbre non compris.", "Marbre compris.", "fr"),
        ("Pose au toiture-terrasse.", "Installatie in de daktuin.", "nl"),
        ("Robinetterie monotrou.", "Eenpitskraan.", "nl"),
    ],
)
def test_new_reported_semantic_failures_are_rejected(source, target, language):
    with pytest.raises(InvalidModelResponse):
        Document(source).restore([{"id": "0", "text": target}], language, "translate")


def test_selected_application_without_key_fails_closed(settings):
    from .groq_provider import GroqClient
    from .exceptions import AssistantDisabled

    settings.GROQ_API_KEY = ""
    assert enabled_for("facturation")
    with pytest.raises(AssistantDisabled):
        GroqClient()


def test_value_hints_distinguish_dimensions_without_exposing_values():
    document = Document("Carreau 278*120cm à 1676,80 EUR.")
    hints = document.model_lines[0]["value_hints"]
    assert any("dimension" in hint for hint in hints.values())
    assert "278" not in json.dumps(hints) and "1676" not in json.dumps(hints)


def test_http_client_constrains_batch_size_and_keeps_credentials_out_of_payload(
    settings,
):
    from .groq_provider import GroqClient
    from unittest.mock import MagicMock

    budget = MagicMock()
    result = {
        "usage": {"total_tokens": 10},
        "choices": [{"finish_reason": "stop", "message": {"content": '{"items":[]}'}}],
    }
    response = MagicMock()
    response.__enter__.return_value.read.return_value = json.dumps(result).encode()
    with patch(
        "ai_assistant.groq_provider.request.urlopen", return_value=response
    ) as post:
        GroqClient(budget).complete([{"id": "a"}, {"id": "b"}])
    request = post.call_args.args[0]
    payload = json.loads(request.data)
    assert settings.GROQ_API_KEY not in request.data.decode()
    schema = payload["response_format"]["json_schema"]["schema"]["properties"]["items"]
    assert schema["minItems"] == schema["maxItems"] == 2
    assert schema["items"]["properties"]["id"]["enum"] == ["a", "b"]
    budget.settle.assert_called_once()


def test_gateway_throttle_keeps_retry_header_after_custom_exception_handler():
    from rest_framework.test import APIRequestFactory
    from .views import InternalAssistantView

    class DeferredView(InternalAssistantView):
        authentication_classes = []
        permission_classes = []
        throttle_classes = []

        def get(self, request):
            raise GroqQuotaDeferred(wait=86400)

    response = DeferredView.as_view()(APIRequestFactory().get("/"))
    assert response.status_code == 429
    assert response["Retry-After"] == "86400"
    assert response.data["retry_after"] == 86400


def test_normal_article_batches_share_one_bounded_provider_request():
    class BatchClient:
        calls = []

        def complete(self, jobs, **kwargs):
            self.calls.append(jobs)
            return {
                "items": [
                    {
                        "id": job["id"],
                        "source_language": "fr",
                        "translations": {
                            "fr": [],
                            "en": [
                                {
                                    "id": line["id"],
                                    "text": "Wooden chair with natural finish.",
                                }
                                for line in job["lines"]
                            ],
                            "nl": [
                                {
                                    "id": line["id"],
                                    "text": "Houten stoel met natuurlijke afwerking.",
                                }
                                for line in job["lines"]
                            ],
                        },
                    }
                    for job in jobs
                ]
            }

    client = BatchClient()
    texts = [
        "Chaise en chêne massif avec finition naturelle pour salle de réunion et espace de travail, avec dossier et assise confortables. "
        + chr(65 + index)
        for index in range(15)
    ]
    result = GroqTextService(client).translate_many(
        texts, target_language="en", application="facturation"
    )
    assert len(result) == 15
    assert len(client.calls) == 1
    assert len(client.calls[0]) == 15


def test_trade_standard_identifier_is_preserved_as_one_value():
    document = Document("Emballages conformes ISPM 15.")
    assert document.lines[0].replacements == {"ZXQVAL00000X": "ISPM 15"}
    assert (
        document.restore(
            [{"id": "0", "text": "Verpakkingen conform ZXQVAL00000X."}],
            "nl",
            "translate",
        )
        == "Verpakkingen conform ISPM 15."
    )


@pytest.mark.parametrize(
    "source,target",
    [
        ("Origine préférentielle UE.", "Voorkeurseu-herkomst."),
        ("N° scellé : code.", "N° verzegeld: code."),
    ],
)
def test_trade_document_meaning_errors_are_rejected(source, target):
    with pytest.raises(InvalidModelResponse):
        Document(source).restore([{"id": "0", "text": target}], "nl", "translate")


def test_document_number_label_is_not_a_temperature_value():
    document = Document("N° scellé : ML-IT2243469")
    assert list(document.lines[0].replacements.values()) == ["ML-IT2243469"]
    assert (
        document.restore(
            [{"id": "0", "text": "Zegelnummer: ZXQVAL00000X"}], "nl", "translate"
        )
        == "Zegelnummer: ML-IT2243469"
    )


def test_owner_and_contractor_can_both_appear_when_present_in_source():
    from .groq_integrity import validate_meaning
    validate_meaning('The project owner appoints the contractor.','The project owner appoints the contractor.','en')
    validate_meaning('De opdrachtgever stelt de aannemer aan.','The project owner appoints the contractor.','en')


def test_long_text_prefers_sentence_boundaries_and_protects_names():
    text = "Texte court. " + "Un long nom officiel " + "suite " * 15
    chunks = split_text(text, 40, ["Un long nom officiel"])
    assert "".join(chunks) == text
    assert any("Un long nom officiel" in part for part in chunks)
    assert split_text("Longue phrase achevée. Et une autre phrase assez longue.", 30)[0] == "Longue phrase achevée. "

import hashlib
import hmac
import json
import time
from unittest.mock import patch

import pytest
from django.core.cache import caches
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from account.models import CustomUser
from project.models import Project

from .exceptions import InvalidModelResponse, ModelTimeout, ModelUnavailable
from .protection import protect_text
from .service import AiAssistantService
from .throttles import AiAssistantRateThrottle

pytestmark = pytest.mark.django_db


class QueueClient:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def complete(self, **kwargs):
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


@pytest.fixture(autouse=True)
def clear_ai_cache():
    caches["default"].clear()
    caches["ai_assistant"].clear()


@pytest.fixture
def user():
    return CustomUser.objects.create_user(
        email="ai-user@test.com", password="securepass123"
    )


def authenticated_client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_protected_values_must_be_returned_exactly_once():
    protected = protect_text(
        "Contacter Maison Atlas (REF-2048) via atlas@example.com ou "
        "https://atlas.test/devis/2048 le 17/09/2026 pour 1 250 MAD.",
        {"Maison Atlas"},
    )

    assert "Maison Atlas" not in protected.text
    assert "atlas@example.com" not in protected.text
    assert "REF-2048" not in protected.text
    assert "https://atlas.test/devis/2048" not in protected.text
    assert "1 250 MAD" not in protected.text
    assert protected.restore(protected.text) == (
        "Contacter Maison Atlas (REF-2048) via atlas@example.com ou "
        "https://atlas.test/devis/2048 le 17/09/2026 pour 1 250 MAD."
    )
    with pytest.raises(InvalidModelResponse):
        protected.restore(protected.text.replace("__PROTECTED_0000__", ""))


def test_service_retries_malformed_json_and_caches_valid_response():
    client = QueueClient(
        "not json",
        json.dumps(
            {"suggested_text": "Texte corrigé", "detected_language": "fr"}
        ),
    )
    service = AiAssistantService(client=client)
    with patch.object(service, "_known_names", return_value=set()):
        first = service.assist(
            action="fix_grammar",
            text="Texte corrige",
            source_language="fr",
            context="project",
        )
        second = service.assist(
            action="fix_grammar",
            text="Texte corrige",
            source_language="fr",
            context="project",
        )

    assert first["suggested_text"] == "Texte corrigé"
    assert first["cached"] is False
    assert second["cached"] is True
    assert len(client.calls) == 2


def test_service_rejects_changed_placeholder_after_one_retry():
    client = QueueClient(
        json.dumps({"suggested_text": "Nom supprimé", "detected_language": "fr"}),
        json.dumps({"suggested_text": "Nom supprimé", "detected_language": "fr"}),
    )
    service = AiAssistantService(client=client)
    with patch.object(service, "_known_names", return_value={"Maison Atlas"}):
        with pytest.raises(InvalidModelResponse):
            service.assist(
                action="professionalize",
                text="Maison Atlas confirme le devis.",
                source_language="fr",
                context="project",
            )
    assert len(client.calls) == 2


def test_service_retries_non_object_structured_output_then_rejects_it():
    client = QueueClient("[]", "[]")
    service = AiAssistantService(client=client)
    with patch.object(service, "_known_names", return_value=set()):
        with pytest.raises(InvalidModelResponse):
            service.assist(
                action="fix_grammar",
                text="Texte corrige",
                source_language="fr",
                context="project",
            )
    assert len(client.calls) == 2


def test_service_propagates_timeout_without_returning_original_text():
    service = AiAssistantService(client=QueueClient(ModelTimeout()))
    with patch.object(service, "_known_names", return_value=set()):
        with pytest.raises(ModelTimeout):
            service.assist(
                action="translate",
                text="Bonjour",
                source_language="fr",
                target_language="en",
                context="other",
            )


def test_cache_is_isolated_by_calling_application():
    response = json.dumps(
        {"suggested_text": "Professional text", "detected_language": "en"}
    )
    client = QueueClient(response, response)
    service = AiAssistantService(client=client)
    service.assist(
        action="professionalize",
        text="Some text",
        source_language="en",
        context="other",
        application="facturation",
    )
    service.assist(
        action="professionalize",
        text="Some text",
        source_language="en",
        context="other",
        application="reservation",
    )
    assert len(client.calls) == 2


def test_assist_endpoint_requires_authentication():
    response = APIClient().post(
        reverse("ai_assistant:assist"),
        {"action": "fix_grammar", "text": "Bonjour", "context": "other"},
        format="json",
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@override_settings(AI_ASSISTANT_ENABLED=False)
def test_assist_endpoint_returns_503_when_disabled(user):
    response = authenticated_client(user).post(
        reverse("ai_assistant:assist"),
        {"action": "fix_grammar", "text": "Bonjour", "context": "other"},
        format="json",
    )
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


@override_settings(AI_ASSISTANT_ENABLED=True, AI_ASSISTANT_USER_IDS=set())
def test_assist_endpoint_validates_request_and_does_not_write_business_data(user):
    before_projects = Project.objects.count()
    result = {
        "suggested_text": "Texte corrigé",
        "detected_language": "fr",
        "model": "qwen3.8-27b-q5_k_m",
        "cached": False,
        "processing_ms": 42,
    }
    with patch("ai_assistant.views.AiAssistantService.assist", return_value=result):
        response = authenticated_client(user).post(
            reverse("ai_assistant:assist"),
            {
                "action": "fix_grammar",
                "text": "Texte corrige",
                "source_language": "fr",
                "context": "project",
            },
            format="json",
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["original_text"] == "Texte corrige"
    assert response.data["suggested_text"] == "Texte corrigé"
    assert Project.objects.count() == before_projects


@override_settings(AI_ASSISTANT_ENABLED=True, AI_ASSISTANT_USER_IDS=set())
def test_translation_requires_target_and_request_is_limited_to_5000_characters(user):
    client = authenticated_client(user)
    missing_target = client.post(
        reverse("ai_assistant:assist"),
        {"action": "translate", "text": "Bonjour", "context": "other"},
        format="json",
    )
    too_long = client.post(
        reverse("ai_assistant:assist"),
        {"action": "fix_grammar", "text": "a" * 5001, "context": "other"},
        format="json",
    )
    assert missing_target.status_code == status.HTTP_400_BAD_REQUEST
    assert too_long.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.parametrize(
    ("model_error", "expected_status"),
    [(ModelUnavailable(), 503), (ModelTimeout(), 504)],
)
@override_settings(AI_ASSISTANT_ENABLED=True, AI_ASSISTANT_USER_IDS=set())
def test_assist_endpoint_surfaces_model_failures(user, model_error, expected_status):
    with patch("ai_assistant.views.AiAssistantService.assist", side_effect=model_error):
        response = authenticated_client(user).post(
            reverse("ai_assistant:assist"),
            {"action": "fix_grammar", "text": "Bonjour", "context": "other"},
            format="json",
        )
    assert response.status_code == expected_status
    assert "suggested_text" not in response.data


@override_settings(AI_ASSISTANT_ENABLED=True, AI_ASSISTANT_USER_IDS=set())
def test_assist_endpoint_is_rate_limited_per_user(user):
    result = {
        "suggested_text": "Bonjour.",
        "detected_language": "fr",
        "model": "qwen3.8-27b-q5_k_m",
        "cached": False,
        "processing_ms": 10,
    }
    with (
        patch.object(AiAssistantRateThrottle, "rate", "1/minute", create=True),
        patch("ai_assistant.views.AiAssistantService.assist", return_value=result),
    ):
        client = authenticated_client(user)
        first = client.post(
            reverse("ai_assistant:assist"),
            {"action": "fix_grammar", "text": "Bonjour", "context": "other"},
            format="json",
        )
        second = client.post(
            reverse("ai_assistant:assist"),
            {"action": "fix_grammar", "text": "Bonsoir", "context": "other"},
            format="json",
        )
    assert first.status_code == status.HTTP_200_OK
    assert second.status_code == status.HTTP_429_TOO_MANY_REQUESTS


def signed_service_headers(body, *, service="facturation", secret="test-secret", request_id=None):
    timestamp = str(int(time.time()))
    request_id = request_id or "request-identifier-0001"
    body_digest = hashlib.sha256(body).hexdigest()
    canonical = f"{timestamp}\n{service}\n{request_id}\n{body_digest}"
    signature = hmac.new(
        secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return {
        "HTTP_X_AI_SERVICE": service,
        "HTTP_X_AI_TIMESTAMP": timestamp,
        "HTTP_X_AI_REQUEST_ID": request_id,
        "HTTP_X_AI_SIGNATURE": signature,
    }


@override_settings(
    AI_ASSISTANT_ENABLED=True,
    AI_ASSISTANT_SERVICE_KEYS={"facturation": "test-secret"},
)
def test_internal_endpoint_accepts_signed_peer_request_and_rejects_replay():
    payload = {
        "action": "translate",
        "text": "Livraison pour Casa Atlas",
        "source_language": "fr",
        "target_language": "en",
        "context": "supplier",
        "protected_terms": ["Casa Atlas"],
    }
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = signed_service_headers(body)
    result = {
        "suggested_text": "Delivery for Casa Atlas",
        "detected_language": "fr",
        "model": "qwen3.8-27b-q5_k_m",
        "cached": False,
        "processing_ms": 50,
    }
    with patch("ai_assistant.views.AiAssistantService.assist", return_value=result) as assist:
        response = APIClient().generic(
            "POST",
            reverse("ai_assistant:internal-assist"),
            data=body,
            content_type="application/json",
            **headers,
        )
        replay = APIClient().generic(
            "POST",
            reverse("ai_assistant:internal-assist"),
            data=body,
            content_type="application/json",
            **headers,
        )

    assert response.status_code == status.HTTP_200_OK
    assert replay.status_code == status.HTTP_401_UNAUTHORIZED
    assert assist.call_args.kwargs["application"] == "facturation"
    assert assist.call_args.kwargs["protected_terms"] == ["Casa Atlas"]

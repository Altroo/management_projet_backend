import hashlib
import hmac
import time
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import caches
from rest_framework import authentication
from rest_framework.exceptions import AuthenticationFailed


@dataclass(frozen=True)
class ServicePrincipal:
    service_name: str

    @property
    def is_authenticated(self):
        return True

    @property
    def pk(self):
        return self.service_name


class ServiceHMACAuthentication(authentication.BaseAuthentication):
    """Authenticate private cross-application calls without sharing user tokens."""

    max_clock_skew_seconds = 300

    def authenticate_header(self, request):
        return "HMAC-SHA256"

    def authenticate(self, request):
        service_name = request.headers.get("X-AI-Service", "").strip()
        timestamp_value = request.headers.get("X-AI-Timestamp", "").strip()
        request_id = request.headers.get("X-AI-Request-ID", "").strip()
        signature = request.headers.get("X-AI-Signature", "").strip()
        secret = settings.AI_ASSISTANT_SERVICE_KEYS.get(service_name)
        if not all((service_name, timestamp_value, request_id, signature, secret)):
            raise AuthenticationFailed("Invalid AI service credentials.")
        try:
            timestamp = int(timestamp_value)
        except ValueError as exc:
            raise AuthenticationFailed("Invalid AI service timestamp.") from exc
        if abs(int(time.time()) - timestamp) > self.max_clock_skew_seconds:
            raise AuthenticationFailed("Expired AI service request.")
        if len(request_id) < 16 or len(request_id) > 128:
            raise AuthenticationFailed("Invalid AI service request identifier.")

        body_digest = hashlib.sha256(request.body).hexdigest()
        canonical = f"{timestamp_value}\n{service_name}\n{request_id}\n{body_digest}"
        expected = hmac.new(
            secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise AuthenticationFailed("Invalid AI service signature.")

        replay_key = hashlib.sha256(
            f"{service_name}:{request_id}".encode("utf-8")
        ).hexdigest()
        if not caches["ai_assistant"].add(
            f"ai-service-replay:{replay_key}", True, self.max_clock_skew_seconds
        ):
            raise AuthenticationFailed("Replayed AI service request.")
        return ServicePrincipal(service_name), service_name

import json
import socket
from urllib import error, request

from django.conf import settings

from .exceptions import InvalidModelResponse, ModelTimeout, ModelUnavailable


class LlamaCppClient:
    """Small OpenAI-compatible client for the private llama.cpp service."""

    def complete(self, *, messages, response_schema, temperature, top_p, max_tokens):
        payload = {
            "model": settings.AI_MODEL_ID,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "stream": False,
            "chat_template_kwargs": {
                "enable_thinking": False,
                "preserve_thinking": False,
            },
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "assistant_response",
                    "strict": True,
                    "schema": response_schema,
                },
            },
        }
        http_request = request.Request(
            f"{settings.AI_MODEL_BASE_URL.rstrip('/')}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(
                http_request, timeout=settings.AI_MODEL_TIMEOUT_SECONDS
            ) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except (TimeoutError, socket.timeout) as exc:
            raise ModelTimeout() from exc
        except error.HTTPError as exc:
            if exc.code in (408, 504):
                raise ModelTimeout() from exc
            raise ModelUnavailable() from exc
        except (error.URLError, ConnectionError, OSError) as exc:
            raise ModelUnavailable() from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise InvalidModelResponse() from exc

        try:
            content = response_payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise InvalidModelResponse() from exc
        if not isinstance(content, str):
            raise InvalidModelResponse()
        return content.strip()

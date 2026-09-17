import hashlib
import json
import logging
import re
import time

from django.conf import settings
from django.core.cache import caches

from account.models import CustomUser
from company.models import CompanyProfile
from project.models import Client, Project, Supplier

from .client import LlamaCppClient, OpusTranslationClient
from .exceptions import InvalidModelResponse, ModelTimeout, ModelUnavailable
from .protection import protect_text

logger = logging.getLogger(__name__)

PROMPT_VERSION = "11"

FRENCH_LANGUAGE_HINTS = frozenset(
    {
        "achat",
        "acompte",
        "avance",
        "au",
        "aux",
        "avec",
        "client",
        "commande",
        "dans",
        "de",
        "des",
        "dépense",
        "du",
        "et",
        "facture",
        "fournisseur",
        "fourniture",
        "gros",
        "installation",
        "la",
        "le",
        "les",
        "main",
        "matériaux",
        "mobilier",
        "montant",
        "oeuvre",
        "paiement",
        "plomberie",
        "pose",
        "pour",
        "projet",
        "règlement",
        "sanitaire",
        "sous",
        "technique",
        "travaux",
        "vente",
    }
)
ENGLISH_LANGUAGE_HINTS = frozenset(
    {
        "advance",
        "and",
        "client",
        "coordination",
        "expense",
        "finishing",
        "follow",
        "for",
        "from",
        "furniture",
        "installation",
        "interior",
        "materials",
        "of",
        "on",
        "payment",
        "project",
        "purchase",
        "revenue",
        "selection",
        "supplier",
        "supply",
        "technical",
        "the",
        "to",
        "work",
    }
)

SINGLE_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "suggested_text": {"type": "string"},
        "detected_language": {"type": "string", "enum": ["fr", "en"]},
    },
    "required": ["suggested_text", "detected_language"],
    "additionalProperties": False,
}

BATCH_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "suggested_text": {"type": "string"},
                },
                "required": ["id", "suggested_text"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}


def _parse_json(content):
    try:
        return json.loads(content)
    except (TypeError, json.JSONDecodeError) as exc:
        raise InvalidModelResponse() from exc


class AiAssistantService:
    cache_ttl = 60 * 60 * 24 * 30

    def __init__(self, client=None, translation_client=None):
        self.client = client or LlamaCppClient()
        self.translation_client = translation_client or OpusTranslationClient()
        self.cache = caches["ai_assistant"]

    @staticmethod
    def _detect_supported_language(value):
        lowered = value.lower()
        if re.search(r"[àâçéèêëîïôùûüÿœæ]", lowered):
            return "fr"
        words = set(re.findall(r"[a-z]+", lowered))
        french_score = len(words & FRENCH_LANGUAGE_HINTS)
        english_score = len(words & ENGLISH_LANGUAGE_HINTS)
        if french_score > english_score:
            return "fr"
        if english_score > french_score:
            return "en"
        return None

    @staticmethod
    def _split_opus_fragments(protected):
        placeholders = tuple(protected.replacements)
        if not placeholders:
            return [protected.text], [("translation", 0, "", "")]

        pattern = re.compile(
            "(" + "|".join(map(re.escape, placeholders)) + ")"
        )
        fragments = []
        plan = []
        for part in pattern.split(protected.text):
            if not part:
                continue
            if part in protected.replacements:
                plan.append(("literal", part, "", ""))
                continue
            leading = part[: len(part) - len(part.lstrip())]
            trailing = part[len(part.rstrip()) :]
            value = part.strip()
            if not value or not re.search(r"[A-Za-zÀ-ÿ]", value):
                plan.append(("literal", part, "", ""))
                continue
            plan.append(("translation", len(fragments), leading, trailing))
            fragments.append(value)
        return fragments, plan

    @staticmethod
    def _restore_opus_fragments(protected, plan, translations):
        parts = []
        for kind, value, leading, trailing in plan:
            if kind == "literal":
                parts.append(value)
                continue
            try:
                translated = translations[value]
            except (IndexError, TypeError) as exc:
                raise InvalidModelResponse() from exc
            if not translated.strip():
                raise InvalidModelResponse()
            parts.append(f"{leading}{translated.strip()}{trailing}")
        return protected.restore("".join(parts))

    def _translate_opus_fragments(self, fragments, target_language):
        translations = []
        for offset in range(0, len(fragments), 100):
            batch = fragments[offset : offset + 100]
            result = self.translation_client.translate(
                texts=batch, target_language=target_language
            )
            if len(result) != len(batch):
                raise InvalidModelResponse()
            translations.extend(result)
        return translations

    @staticmethod
    def _model_id(action):
        if action in {"translate", "translate_batch"} and settings.AI_TRANSLATION_SPECIALIST_ENABLED:
            return settings.AI_TRANSLATION_MODEL_ID
        return settings.AI_MODEL_ID

    @staticmethod
    def _cache_key(
        *,
        application,
        action,
        text,
        source_language,
        target_language,
        context,
        protection_hash,
    ):
        material = json.dumps(
            {
                "prompt_version": PROMPT_VERSION,
                "model": AiAssistantService._model_id(action),
                "application": application,
                "action": action,
                "source_language": source_language,
                "target_language": target_language,
                "context": context,
                "protection_hash": protection_hash,
                "text": text,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return f"ai-assist:{hashlib.sha256(material.encode('utf-8')).hexdigest()}"

    @staticmethod
    def _protection_hash(protected):
        material = "\0".join(protected.replacements.values())
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @staticmethod
    def _known_names():
        values = set()
        values.update(Project.objects.values_list("nom", flat=True))
        values.update(Project.objects.exclude(nom_client="").values_list("nom_client", flat=True))
        values.update(
            Project.objects.exclude(chef_de_projet="").values_list(
                "chef_de_projet", flat=True
            )
        )
        values.update(Client.objects.values_list("nom", flat=True))
        values.update(Supplier.objects.values_list("nom", flat=True))
        values.update(CompanyProfile.objects.values_list("raison_sociale", flat=True))
        for first_name, last_name in CustomUser.objects.values_list(
            "first_name", "last_name"
        ):
            full_name = f"{first_name} {last_name}".strip()
            if full_name:
                values.add(full_name)
        return {value for value in values if value}

    @staticmethod
    def _instruction(
        action, source_language, target_language, context, application
    ):
        language_rule = (
            "Translate faithfully into "
            f"{'French' if target_language == 'fr' else 'English'} using natural, "
            "idiomatic business language. Preserve each sentence's grammatical function: "
            "instructions and imperatives must remain instructions and imperatives."
            if action == "translate"
            else "Keep the source language unchanged."
        )
        action_rule = {
            "translate": "Translate only; do not summarize or add information.",
            "fix_grammar": "Correct grammar, spelling, punctuation, and agreement without changing meaning.",
            "professionalize": "Rewrite in a concise professional tone without inventing facts.",
        }[action]
        return (
            "You edit internal business text. "
            f"Application: {application}. Context: {context}. "
            f"Declared source language: {source_language}. "
            f"{action_rule} {language_rule} "
            "Every token shaped like ZXQMARKER0000, XACME0000X, DATEX0000, "
            "MADCURR0000, or 987650000 is immutable: "
            "copy it exactly once, "
            "unchanged and in the appropriate semantic position. Return JSON only."
        )

    def assist(
        self,
        *,
        action,
        text,
        source_language,
        target_language=None,
        context,
        application="management_projet",
        protected_terms=(),
    ):
        started = time.monotonic()
        model_id = self._model_id(action)
        known_names = set(protected_terms)
        if application == "management_projet":
            known_names.update(self._known_names())
        protected = protect_text(text, known_names)
        cache_key = self._cache_key(
            application=application,
            action=action,
            text=text,
            source_language=source_language,
            target_language=target_language,
            context=context,
            protection_hash=self._protection_hash(protected),
        )
        cached_value = self.cache.get(cache_key)
        if cached_value:
            result = {
                **cached_value,
                "model": model_id,
                "cached": True,
                "processing_ms": round((time.monotonic() - started) * 1000),
            }
            self._log(
                application, action, len(text), result["processing_ms"], True, None
            )
            return result

        if action == "translate" and settings.AI_TRANSLATION_SPECIALIST_ENABLED:
            opus_fragments, opus_plan = self._split_opus_fragments(protected)
            last_error = None
            for _attempt in range(2):
                try:
                    translations = self._translate_opus_fragments(
                        opus_fragments, target_language
                    )
                    suggested_text = self._restore_opus_fragments(
                        protected, opus_plan, translations
                    )
                    detected_language = (
                        source_language
                        if source_language in ("fr", "en")
                        else ("fr" if target_language == "en" else "en")
                    )
                    stored = {
                        "suggested_text": suggested_text,
                        "detected_language": detected_language,
                    }
                    self.cache.set(cache_key, stored, self.cache_ttl)
                    processing_ms = round((time.monotonic() - started) * 1000)
                    self._log(
                        application, action, len(text), processing_ms, False, None
                    )
                    return {
                        **stored,
                        "model": model_id,
                        "cached": False,
                        "processing_ms": processing_ms,
                    }
                except InvalidModelResponse as exc:
                    last_error = exc
                except (ModelUnavailable, ModelTimeout) as exc:
                    processing_ms = round((time.monotonic() - started) * 1000)
                    self._log(
                        application, action, len(text), processing_ms, False, exc
                    )
                    raise
            processing_ms = round((time.monotonic() - started) * 1000)
            self._log(
                application, action, len(text), processing_ms, False, last_error
            )
            raise last_error or InvalidModelResponse()

        temperature = 0.35 if action == "professionalize" else 0.0
        last_error = None
        for _attempt in range(2):
            try:
                content = self.client.complete(
                    messages=[
                        {
                            "role": "system",
                            "content": self._instruction(
                                action,
                                source_language,
                                target_language,
                                context,
                                application,
                            ),
                        },
                        {"role": "user", "content": protected.text},
                    ],
                    response_schema=SINGLE_RESPONSE_SCHEMA,
                    temperature=temperature,
                    top_p=0.9 if action == "professionalize" else 1.0,
                    max_tokens=2048,
                )
                payload = _parse_json(content)
                if not isinstance(payload, dict) or set(payload) != {
                    "suggested_text",
                    "detected_language",
                }:
                    raise InvalidModelResponse()
                if not isinstance(payload["suggested_text"], str):
                    raise InvalidModelResponse()
                if payload["detected_language"] not in ("fr", "en"):
                    raise InvalidModelResponse()
                suggested_text = protected.restore(payload["suggested_text"])
                if not suggested_text.strip():
                    raise InvalidModelResponse()
                detected_language = (
                    source_language
                    if source_language in ("fr", "en")
                    else payload["detected_language"]
                )
                stored = {
                    "suggested_text": suggested_text,
                    "detected_language": detected_language,
                }
                self.cache.set(cache_key, stored, self.cache_ttl)
                processing_ms = round((time.monotonic() - started) * 1000)
                self._log(application, action, len(text), processing_ms, False, None)
                return {
                    **stored,
                    "model": model_id,
                    "cached": False,
                    "processing_ms": processing_ms,
                }
            except InvalidModelResponse as exc:
                last_error = exc
            except (ModelUnavailable, ModelTimeout) as exc:
                processing_ms = round((time.monotonic() - started) * 1000)
                self._log(application, action, len(text), processing_ms, False, exc)
                raise
        processing_ms = round((time.monotonic() - started) * 1000)
        self._log(application, action, len(text), processing_ms, False, last_error)
        raise last_error or InvalidModelResponse()

    def translate_many(
        self,
        texts,
        *,
        target_language,
        context="other",
        application="management_projet",
        protected_terms=(),
        polish=False,
    ):
        started = time.monotonic()
        unique_texts = list(
            dict.fromkeys(text.strip() for text in texts if text and text.strip())
        )
        if not unique_texts:
            return {}

        translated = {}
        missing = []
        known_names = set(protected_terms)
        if application == "management_projet":
            known_names.update(self._known_names())
        for text in unique_texts:
            if self._detect_supported_language(text) == target_language:
                translated[text] = text
                continue
            protected = protect_text(text, known_names)
            cache_key = self._cache_key(
                application=application,
                action="translate",
                text=text,
                source_language="auto",
                target_language=target_language,
                context=context,
                protection_hash=self._protection_hash(protected),
            )
            cached_value = self.cache.get(cache_key)
            if cached_value:
                translated[text] = cached_value["suggested_text"]
            else:
                missing.append((text, cache_key, protected))

        try:
            for chunk in self._chunks(missing):
                if settings.AI_TRANSLATION_SPECIALIST_ENABLED:
                    self._translate_chunk_with_opus(
                        chunk, target_language, translated
                    )
                else:
                    self._translate_chunk_with_qwen(
                        chunk,
                        target_language,
                        context,
                        translated,
                        application,
                    )
        except (InvalidModelResponse, ModelUnavailable, ModelTimeout) as exc:
            self._log(
                application,
                "translate_batch",
                sum(map(len, unique_texts)),
                round((time.monotonic() - started) * 1000),
                False,
                exc,
            )
            raise
        self._log(
            application,
            "translate_batch",
            sum(map(len, unique_texts)),
            round((time.monotonic() - started) * 1000),
            not missing,
            None,
        )
        if polish and target_language == "en":
            return {
                source: self._polish_english_translation(suggestion)
                for source, suggestion in translated.items()
            }
        return translated

    @staticmethod
    def _chunks(items, max_items=15, max_chars=6000):
        chunk = []
        char_count = 0
        for item in items:
            item_length = len(item[0])
            if chunk and (len(chunk) >= max_items or char_count + item_length > max_chars):
                yield chunk
                chunk = []
                char_count = 0
            chunk.append(item)
            char_count += item_length
        if chunk:
            yield chunk

    def _translate_chunk_with_opus(self, chunk, target_language, translated):
        protected_items = [protected for _text, _key, protected in chunk]
        opus_items = [self._split_opus_fragments(item) for item in protected_items]
        opus_fragments = [
            fragment
            for fragments, _plan in opus_items
            for fragment in fragments
        ]
        last_error = None
        for _attempt in range(2):
            try:
                suggestions = self._translate_opus_fragments(
                    opus_fragments, target_language
                )
                restored = []
                suggestion_offset = 0
                for protected, (fragments, plan) in zip(
                    protected_items, opus_items
                ):
                    item_suggestions = suggestions[
                        suggestion_offset : suggestion_offset + len(fragments)
                    ]
                    restored.append(
                        self._restore_opus_fragments(
                            protected, plan, item_suggestions
                        )
                    )
                    suggestion_offset += len(fragments)
                if suggestion_offset != len(suggestions):
                    raise InvalidModelResponse()
                for (source, cache_key, _protected), suggestion in zip(
                    chunk, restored
                ):
                    value = {
                        "suggested_text": suggestion,
                        "detected_language": "fr" if target_language == "en" else "en",
                    }
                    self.cache.set(cache_key, value, self.cache_ttl)
                    translated[source] = suggestion
                return
            except InvalidModelResponse as exc:
                last_error = exc
        raise last_error or InvalidModelResponse()

    def _translate_chunk_with_qwen(
        self,
        chunk,
        target_language,
        context,
        translated,
        application,
    ):
        protected_items = [protected for _text, _key, protected in chunk]
        request_items = [
            {"id": str(index), "text": protected.text}
            for index, protected in enumerate(protected_items)
        ]
        last_error = None
        for _attempt in range(2):
            try:
                content = self.client.complete(
                    messages=[
                        {
                            "role": "system",
                            "content": self._instruction(
                                "translate",
                                "auto",
                                target_language,
                                context,
                                application,
                            )
                            + " Use polished professional construction and accounting terminology, "
                            "not literal word-for-word phrasing. Use these terms where applicable: "
                            "acompte or avance = advance payment or deposit; avancement or règlement "
                            "d'avancement = progress payment; complément de commande = additional "
                            "order; gros œuvre = structural work; main-d'œuvre = labor. French ordinal "
                            "suffixes around immutable numbers must become correct English suffixes: "
                            "1er or 1ère = 1st, 2e or 2ème = 2nd, and 3e or 3ème = 3rd; never output "
                            "1th, 2th, or 3th. If the input is already in the target language, preserve "
                            "it unless a small correction is required for natural business language. "
                            "Return an items array with exactly one result for every input id.",
                        },
                        {
                            "role": "user",
                            "content": json.dumps({"items": request_items}, ensure_ascii=False),
                        },
                    ],
                    response_schema=BATCH_RESPONSE_SCHEMA,
                    temperature=0.0,
                    top_p=1.0,
                    max_tokens=4096,
                )
                payload = _parse_json(content)
                response_items = payload.get("items") if isinstance(payload, dict) else None
                if not isinstance(response_items, list):
                    raise InvalidModelResponse()
                indexed = {
                    item.get("id"): item.get("suggested_text")
                    for item in response_items
                    if isinstance(item, dict)
                }
                expected_ids = {str(index) for index in range(len(chunk))}
                if set(indexed) != expected_ids:
                    raise InvalidModelResponse()

                restored = []
                for index, protected in enumerate(protected_items):
                    suggested = indexed[str(index)]
                    if not isinstance(suggested, str) or not suggested.strip():
                        raise InvalidModelResponse()
                    restored.append(
                        self._polish_english_translation(
                            protected.restore(suggested), target_language
                        )
                    )
                for (source, cache_key, _protected), suggestion in zip(chunk, restored):
                    value = {
                        "suggested_text": suggestion,
                        "detected_language": "fr" if target_language == "en" else "en",
                    }
                    self.cache.set(cache_key, value, self.cache_ttl)
                    translated[source] = suggestion
                return
            except InvalidModelResponse as exc:
                last_error = exc
        raise last_error or InvalidModelResponse()

    @staticmethod
    def _normalize_english_ordinals(value, target_language):
        if target_language != "en":
            return value

        def replace(match):
            number = int(match.group(1))
            if 10 <= number % 100 <= 20:
                suffix = "th"
            else:
                suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
            return f"{number}{suffix}"

        return re.sub(
            r"\b(\d+)(?:th|er|ere|ère|eme|ème)\b",
            replace,
            value,
            flags=re.IGNORECASE,
        )

    @classmethod
    def _polish_english_translation(cls, value, target_language="en"):
        if target_language != "en":
            return value

        polished = cls._normalize_english_ordinals(value, target_language)
        replacements = (
            (r"\b1st customer down payment\b", "1st client advance payment"),
            (
                r"\b(\d+(?:st|nd|rd|th)) advance of the\b",
                r"\1 advance payment for the",
            ),
            (r"\bcommand supplement\b", "Additional order"),
            (
                r"\bAdditional order Minotti project Brahim\b",
                "Additional Minotti order for the Brahim project",
            ),
            (
                r"\bregulation of the progress of the major work of\b",
                "Progress payment for structural work on",
            ),
            (
                r"\bprogress towards the implementation of\b",
                "Progress payment for",
            ),
            (
                r"\bperformance of interior finishing and furnishings\b",
                "Interior finishing and furnishing work",
            ),
            (
                r"\bproduction of technical services and provision of\b",
                "Technical work and supply of",
            ),
            (
                r"\bTechnical work and supply of design and decoration elements Casa Di Lusso\b",
                "Technical work and supply of Casa Di Lusso design and decoration elements",
            ),
            (
                r"\bProgress payment for Project ([^.]+)$",
                r"Progress payment for the \1 project",
            ),
            (r"\bthe work of the major works\b", "structural work"),
            (r"\blarge amount of work\b", "Structural work"),
            (r"\bpours\b", "for"),
            (r"\s+by itself\b", ""),
        )
        for pattern, replacement in replacements:
            polished = re.sub(pattern, replacement, polished, flags=re.IGNORECASE)
        return polished

    @staticmethod
    def _log(application, action, character_count, processing_ms, cached, error):
        logger.info(
            "AI assistant request",
            extra={
                "ai_operation": action,
                "ai_application": application,
                "ai_character_count": character_count,
                "ai_model": AiAssistantService._model_id(action),
                "ai_cached": cached,
                "ai_duration_ms": processing_ms,
                "ai_error": error.__class__.__name__ if error else None,
            },
        )

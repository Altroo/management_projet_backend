from rest_framework import serializers


class AssistRequestSerializer(serializers.Serializer):
    ACTIONS = ("translate", "fix_grammar", "professionalize")
    LANGUAGES = ("auto", "fr", "en", "nl")
    action = serializers.ChoiceField(choices=ACTIONS)
    text = serializers.CharField(
        allow_blank=False,
        trim_whitespace=False,
        max_length=5000,
    )
    source_language = serializers.ChoiceField(choices=LANGUAGES, default="auto")
    target_language = serializers.ChoiceField(
        choices=("fr", "en", "nl"), required=False
    )
    context = serializers.RegexField(
        r"^[a-z][a-z0-9_]{0,49}$", default="other", max_length=50
    )

    def validate(self, attrs):
        if not attrs["text"].strip():
            raise serializers.ValidationError(
                {"text": "Le texte ne peut pas être vide."}
            )
        if attrs["action"] == "translate" and not attrs.get("target_language"):
            raise serializers.ValidationError(
                {"target_language": "La langue cible est requise pour une traduction."}
            )
        if attrs["action"] != "translate" and "target_language" in attrs:
            attrs.pop("target_language")
        return attrs


class InternalAssistRequestSerializer(AssistRequestSerializer):
    protected_terms = serializers.ListField(
        child=serializers.CharField(max_length=200, trim_whitespace=True),
        required=False,
        default=list,
        max_length=100,
    )


class InternalTranslationRequestSerializer(serializers.Serializer):
    texts = serializers.ListField(
        child=serializers.CharField(
            max_length=5000, trim_whitespace=False, allow_blank=True
        ),
        max_length=20,
        allow_empty=False,
    )
    target_language = serializers.ChoiceField(choices=("fr", "en", "nl"))
    context = serializers.RegexField(
        r"^[a-z][a-z0-9_]{0,49}$", default="other", max_length=50
    )
    protected_terms = serializers.ListField(
        child=serializers.CharField(max_length=200), default=list, max_length=100
    )

    def validate_texts(self, texts):
        if sum(len(text) for text in texts) > 16000:
            raise serializers.ValidationError("Le lot de traduction est trop long.")
        return texts

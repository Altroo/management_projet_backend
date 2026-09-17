from rest_framework.throttling import SimpleRateThrottle, UserRateThrottle


class AiAssistantRateThrottle(UserRateThrottle):
    scope = "ai_assistant"


class AiServiceRateThrottle(SimpleRateThrottle):
    scope = "ai_assistant_service"

    def get_cache_key(self, request, view):
        if not request.auth:
            return None
        return self.cache_format % {"scope": self.scope, "ident": str(request.auth)}

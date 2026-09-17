from django.conf import settings
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .authentication import ServiceHMACAuthentication
from .exceptions import AssistantDisabled
from .serializers import AssistRequestSerializer, InternalAssistRequestSerializer
from .service import AiAssistantService
from .throttles import AiAssistantRateThrottle, AiServiceRateThrottle


def ensure_assistant_access(user):
    if not settings.AI_ASSISTANT_ENABLED:
        raise AssistantDisabled()
    if settings.AI_ASSISTANT_USER_IDS and user.pk not in settings.AI_ASSISTANT_USER_IDS:
        raise AssistantDisabled()


class AssistView(APIView):
    permission_classes = (permissions.IsAuthenticated,)
    throttle_classes = (AiAssistantRateThrottle,)

    @staticmethod
    def post(request):
        ensure_assistant_access(request.user)
        serializer = AssistRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        result = AiAssistantService().assist(
            **payload, application="management_projet"
        )
        return Response(
            {"original_text": payload["text"], **result},
            status=status.HTTP_200_OK,
        )


class InternalAssistView(APIView):
    """Private signed gateway used by other applications on the server."""

    authentication_classes = (ServiceHMACAuthentication,)
    permission_classes = (permissions.IsAuthenticated,)
    throttle_classes = (AiServiceRateThrottle,)

    @staticmethod
    def post(request):
        if not settings.AI_ASSISTANT_ENABLED:
            raise AssistantDisabled()
        serializer = InternalAssistRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        result = AiAssistantService().assist(
            **payload, application=str(request.auth)
        )
        return Response(
            {"original_text": payload["text"], **result},
            status=status.HTTP_200_OK,
        )

from rest_framework import permissions, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import CompanyProfile
from .serializers import CompanyProfileSerializer


def get_company_profile():
    profile, _created = CompanyProfile.objects.get_or_create(singleton_key=True)
    return profile


class CompanyProfileView(APIView):
    permission_classes = (permissions.IsAdminUser,)
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    @staticmethod
    def get(request):
        serializer = CompanyProfileSerializer(
            get_company_profile(), context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @staticmethod
    def patch(request):
        profile = get_company_profile()
        serializer = CompanyProfileSerializer(
            profile,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    put = patch

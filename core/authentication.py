from rest_framework import authentication
from rest_framework import exceptions
from .models import UserSettings

class APIKeyAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        api_key = (
            request.headers.get("X-API-Key")
            or request.GET.get("api_key")
            or request.POST.get("api_key")
            or None
        )

        if not api_key:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.lower().startswith("api-key "):
                api_key = auth_header.split(" ", 1)[1].strip()

        if not api_key:
            return None

        try:
            user_settings = UserSettings.objects.select_related("user").get(api_key=api_key)
        except UserSettings.DoesNotExist:
            raise exceptions.AuthenticationFailed("Invalid API key")

        return (user_settings.user, None)

    def authenticate_header(self, request):
        return 'Api-Key realm="api"'

from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse
from django.views.generic import TemplateView
from rest_framework.schemas import get_schema_view
from rest_framework.renderers import (
    JSONOpenAPIRenderer,
)
from rest_framework.permissions import AllowAny


schema_view = get_schema_view(
    title="Komunikator API",
    description="OpenAPI schema for the Komunikator project",
    version="1.0.0",
    public=True,
    permission_classes=[AllowAny],
    renderer_classes=[JSONOpenAPIRenderer],
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('api/schema/', schema_view, name='openapi-schema'),
    path(
        'api/docs/',
        TemplateView.as_view(
            template_name='api_docs/swagger.html',
            extra_context={'schema_url': '/api/schema/'}
        ),
        name='swagger-ui'
    ),
    path(
        'api/redoc/',
        TemplateView.as_view(
            template_name='api_docs/redoc.html',
            extra_context={'schema_url': '/api/schema/'}
        ),
        name='redoc'
    ),
]
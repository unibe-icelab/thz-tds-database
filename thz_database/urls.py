# thz_database/urls.py
from django.contrib import admin
from django.urls import path, include
from django.views.generic.base import RedirectView
from django.conf import settings # For static files in DEBUG
from django.conf.urls.static import static # For static files in DEBUG


urlpatterns = [
    path('admin/', admin.site.urls),
    path('django_plotly_dash/', include('django_plotly_dash.urls')),
    path('accounts/', include('django.contrib.auth.urls')), # Handles login, logout, etc.
    path('spectra/', include('spectra.urls', namespace='spectra')),
    path('', RedirectView.as_view(url='/spectra/', permanent=True)),
    path('django_plotly_dash/', include('django_plotly_dash.urls')),
]

# Serve static files during development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
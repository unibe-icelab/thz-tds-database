# spectra/urls.py
from django.urls import path
from . import views

app_name = 'spectra'

urlpatterns = [
    # The root of the 'spectra' app now shows the list of spectra.
    path('', views.home_view, name='home'),
    path('spectra', views.SpectrumListView.as_view(), name='spectrum_list'),

    path('<int:pk>/', views.spectrum_list_or_detail, name='spectrum_detail'),
    path('<int:pk>/download/', views.download_spectrum_file, name='download_spectrum_file'),
    path('spectrum/upload/', views.upload_spectrum, name='upload_spectrum'),
    path('token/regenerate/', views.regenerate_token_view, name='regenerate_token'),
]
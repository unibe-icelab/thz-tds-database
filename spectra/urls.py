# spectra/urls.py
from django.urls import path
from . import views
from django.contrib.auth import views as auth_views # Import Django's auth views

app_name = 'spectra'

urlpatterns = [
    # The root of the 'spectra' app now shows the list of spectra.
    path('', views.home_view, name='home'),
    path('spectra', views.SpectrumListView.as_view(), name='spectrum_list'),

    path('<int:pk>/', views.spectrum_list_or_detail, name='spectrum_detail'),
    path('<int:pk>/download/', views.download_spectrum_file, name='download_spectrum_file'),
    path('spectrum/upload/', views.upload_spectrum, name='upload_spectrum'),
    path('token/regenerate/', views.regenerate_token_view, name='regenerate_token'),
    path('material/<int:material_id>/image/', views.material_image_view, name='material_image'),

    path('api/upload/', views.api_upload_spectrum, name='api_upload_spectrum'),
    path('api/spectra/', views.api_spectrum_list, name='api_spectrum_list'),
    path('api/spectra/<int:pk>/', views.api_spectrum_detail, name='api_spectrum_detail'),

    # Password Change URLs
    path('password_change/',
         auth_views.PasswordChangeView.as_view(
             template_name='registration/password_change_form.html', # Custom template
             success_url='/password_change/done/' # Custom success URL
         ),
         name='password_change'),
    path('password_change/done/',
         auth_views.PasswordChangeDoneView.as_view(
             template_name='registration/password_change_done.html' # Custom template
         ),
         name='password_change_done'),
]
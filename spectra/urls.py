# spectra/urls.py
from django.urls import path
from . import views

app_name = 'spectra'

urlpatterns = [
    # The root of the 'spectra' app now shows the list of spectra.
    path('', views.SpectrumListView.as_view(), name='spectrum_list'),

    # If you still want a separate home page, you could use a different path, e.g.,
    # path('home/', views.home, name='home'),
    # Or, you can remove the views.home and home.html if not needed.

    # The path 'spectra/' for SpectrumListView is removed as it's now the app root.
    # path('spectra/', views.SpectrumListView.as_view(), name='spectrum_list'), # Old path
    path('<int:pk>/', views.spectrum_list_or_detail, name='spectrum_detail'),
    path('spectrum/upload/', views.upload_spectrum, name='upload_spectrum'),
]
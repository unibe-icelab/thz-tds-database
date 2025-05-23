# spectra/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, DetailView
from .models import Spectrum, Material
from .forms import SpectrumUploadForm  # MaterialForm import removed as it's not used in these views
import json

from django.shortcuts import render, get_object_or_404
from spectra.models import Spectrum

def curveplot_view(request):
    spectrum_id = request.GET.get('spectrum_id')
    spectrum = get_object_or_404(Spectrum, id=spectrum_id) if spectrum_id else None
    spectra = Spectrum.objects.all()
    return render(request, 'spectra/curveplot.html', {'spectrum': spectrum, 'spectra': spectra})

def home(request):
    materials = Material.objects.order_by('name')
    return render(request, 'spectra/home.html', {'materials': materials})


class SpectrumListView(ListView):
    model = Spectrum
    template_name = 'spectra/spectrum_list.html'
    context_object_name = 'spectra'
    ordering = ['-upload_timestamp']


@login_required
def upload_spectrum(request):
    initial_form_data = {}
    # Populate initial_form_data only for GET requests
    if request.method == 'GET' and 'material_id' in request.GET:
        try:
            material_instance = Material.objects.get(pk=request.GET['material_id'])
            initial_form_data['material_name'] = material_instance.name
        except (Material.DoesNotExist, ValueError):
            pass  # Silently ignore if material_id is invalid

    if request.method == 'POST':
        form = SpectrumUploadForm(request.POST, request.FILES)
        if form.is_valid():
            spectrum = form.save(commit=False)  # spectral_data is populated by form's save()
            spectrum.uploaded_by = request.user

            # Determine data availability flags
            # Ensure these fields exist on your Spectrum model
            spectrum.refractive_index_data_available = False
            spectrum.absorption_coefficient_data_available = False

            if spectrum.spectral_data and isinstance(spectrum.spectral_data, dict):
                # Case 1: Processing (e.g. from a binary file in the form) directly provides specific keys
                if 'refractive_index' in spectrum.spectral_data and spectrum.spectral_data.get('refractive_index'):
                    spectrum.refractive_index_data_available = True

                if 'absorption_coefficient' in spectrum.spectral_data and spectrum.spectral_data.get(
                        'absorption_coefficient'):
                    spectrum.absorption_coefficient_data_available = True

                # Case 2: CSV file was uploaded, spectral_data might contain a generic 'intensity'.
                # Use the 'data_type' field from the form to determine what 'intensity' represents.
                # This assumes that if specific keys like 'refractive_index' are present, they take precedence.
                elif 'intensity' in spectrum.spectral_data and spectrum.spectral_data.get('intensity'):
                    # form.cleaned_data is available because form.is_valid() was true
                    csv_data_type = form.cleaned_data.get('data_type')
                    if csv_data_type == 'refractive_index':
                        spectrum.refractive_index_data_available = True
                    elif csv_data_type == 'absorption_coefficient':
                        spectrum.absorption_coefficient_data_available = True

            spectrum.save()  # This saves the spectrum instance along with the boolean flags
            return redirect('spectra:spectrum_detail', pk=spectrum.pk)
        # If form is not valid, it will fall through to the render statement,
        # and the 'form' object containing errors will be passed to the template.
    else:  # request.method == 'GET'
        form = SpectrumUploadForm(initial=initial_form_data)

    return render(request, 'spectra/upload_spectrum.html', {'form': form})


class SpectrumDetailView(DetailView):
    model = Spectrum
    template_name = 'spectra/spectrum_detail.html'
    context_object_name = 'spectrum'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        spectrum = self.object
        context = {
            'spectrum': spectrum,
            'material_name': spectrum.material.name,
            'material_description': spectrum.material.description,
            'spectrum_metadata': spectrum.metadata,  # Assuming it's a dict
            'can_plot_ref_idx': bool(spectrum.refractive_index_data),
            'can_plot_abs_coeff': bool(spectrum.absorption_coefficient_data),
            'dash_app_name_ref_idx': 'RefractiveIndexPlot',
            'dash_initial_arguments_ref_idx': {
                'frequency': spectrum.frequency_data,
                'refractive_index': spectrum.refractive_index_data,
            },
            'dash_app_name_abs_coeff': 'AbsorptionCoefficientPlot',
            'dash_initial_arguments_abs_coeff': {
                'frequency': spectrum.frequency_data,
                'absorption_coefficient': spectrum.absorption_coefficient_data,
            }
        }
        if hasattr(spectrum, 'metadata') and spectrum.metadata:
            if isinstance(spectrum.metadata, dict):
                context['spectrum_metadata'] = spectrum.metadata
            else:
                try:
                    loaded_metadata = json.loads(str(spectrum.metadata))
                    if isinstance(loaded_metadata, dict):
                        context['spectrum_metadata'] = loaded_metadata
                    else:
                        context['spectrum_metadata'] = {"data": loaded_metadata,
                                                        "info": "Metadata loaded but not a dictionary."}
                except (json.JSONDecodeError, TypeError):
                    context['spectrum_metadata'] = {"error": "Metadata is not a valid JSON format or cannot be parsed."}
        else:
            context['spectrum_metadata'] = {"info": "No detailed metadata available."}

        return context
# spectra/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, DetailView
from .models import Spectrum, Material
from .forms import SpectrumUploadForm, MaterialForm
from . import dash_apps # noqa: F401 -- Ensures dash_apps.py is loaded
import json # For parsing metadata if needed, or handling JSON in general

def home(request):
    materials = Material.objects.order_by('name')
    return render(request, 'spectra/home.html', {'materials': materials})


class MaterialListView(ListView):
    model = Material
    template_name = 'spectra/material_list.html'
    context_object_name = 'materials'
    ordering = ['name']

class SpectrumListView(ListView):
    model = Spectrum
    template_name = 'spectra/spectrum_list.html'
    context_object_name = 'spectra'
    ordering = ['-upload_timestamp']

class MaterialDetailView(DetailView):
    model = Material
    template_name = 'spectra/material_detail.html'
    context_object_name = 'material'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['spectra'] = Spectrum.objects.filter(material=self.object).order_by('-upload_timestamp')
        return context


class SpectrumDetailView(DetailView):
    model = Spectrum
    template_name = 'spectra/spectrum_detail.html'
    context_object_name = 'spectrum'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        spectrum = self.object

        can_plot = False
        initial_args = {}

        # Check if spectral_data is valid for plotting
        if spectrum.spectral_data and \
           isinstance(spectrum.spectral_data.get('frequency'), list) and \
           isinstance(spectrum.spectral_data.get('intensity'), list) and \
           len(spectrum.spectral_data['frequency']) > 0 and \
           len(spectrum.spectral_data['intensity']) == len(spectrum.spectral_data['frequency']):
            can_plot = True
            # Prepare arguments for the Dash app
            initial_args = {
                'frequency': spectrum.spectral_data.get('frequency'),
                'intensity': spectrum.spectral_data.get('intensity'),
                'frequency_unit': spectrum.metadata.get('frequency_unit', 'Frequency (a.u.)') if spectrum.metadata else 'Frequency (a.u.)',
                'intensity_unit': spectrum.metadata.get('intensity_unit', 'Intensity (a.u.)') if spectrum.metadata else 'Intensity (a.u.)',
                'material_name': spectrum.material.name if spectrum.material else 'Spectrum',
            }

        context['can_plot_spectrum'] = can_plot
        context['dash_app_name'] = 'SimpleSpectrumPlotter' # Must match the name in dash_apps.py
        context['dash_initial_arguments'] = initial_args
        return context


@login_required
def upload_spectrum(request):
    initial_form_data = {}
    if 'material_id' in request.GET:
        try:
            material_instance = Material.objects.get(pk=request.GET['material_id'])
            initial_form_data['material'] = material_instance
        except (Material.DoesNotExist, ValueError):
            pass # Material not found, form will show empty material field

    if request.method == 'POST':
        form = SpectrumUploadForm(request.POST, request.FILES) # Pass request.FILES
        if form.is_valid():
            spectrum = form.save(commit=False)
            spectrum.uploaded_by = request.user

            # Handle metadata if it's expected to be JSON from a text field
            # The form field 'metadata' is a CharField, so it needs to be parsed if it's JSON.
            # However, the model's JSONField handles string-to-JSON conversion if the string is valid JSON.
            # If you want to ensure it's valid JSON or provide default, you can do it here or in the form.
            # For now, assuming the model's JSONField handles it or it's simple text.
            # If metadata was meant to be structured from the form, the form needs to handle that.
            # The current SpectrumUploadForm has metadata as a CharField, which is fine if you expect
            # users to type valid JSON or if your model's JSONField handles simple strings.
            # If you want to parse it as JSON here:
            # try:
            #     if form.cleaned_data.get('metadata'):
            #         spectrum.metadata = json.loads(form.cleaned_data.get('metadata'))
            # except json.JSONDecodeError:
            #     form.add_error('metadata', 'Invalid JSON format.')
            #     return render(request, 'spectra/upload_spectrum.html', {'form': form})

            spectrum.save() # Save the instance to the database
            # form.save_m2m() # If your form had m2m fields, call this after spectrum.save()
            return redirect('spectra:spectrum_detail', pk=spectrum.pk)
    else:
        form = SpectrumUploadForm(initial=initial_form_data)
    return render(request, 'spectra/upload_spectrum.html', {'form': form})


@login_required
def create_material(request):
    if request.method == 'POST':
        form = MaterialForm(request.POST)
        if form.is_valid():
            material = form.save()
            return redirect('spectra:material_detail', pk=material.pk)
    else:
        form = MaterialForm()
    return render(request, 'spectra/create_material.html', {'form': form})
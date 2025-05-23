# spectra/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, DetailView
from .models import Spectrum, Material
from .forms import SpectrumUploadForm, SpectrumFilterForm  # MaterialForm import removed as it's not used in these views
import json

from django.shortcuts import render, get_object_or_404
from spectra.models import Spectrum
from django.http import JsonResponse
import plotly.graph_objs as go
from .models import Spectrum
import plotly.graph_objs as go


def spectrum_list_or_detail(request, pk=None):
    spectra = Spectrum.objects.select_related('material', 'uploaded_by').all()
    filter_form = SpectrumFilterForm(request.GET or None)

    if filter_form.is_valid():
        name = filter_form.cleaned_data.get('name')
        uploaded_by = filter_form.cleaned_data.get('uploaded_by')
        upload_date_from = filter_form.cleaned_data.get('upload_date_from')
        upload_date_to = filter_form.cleaned_data.get('upload_date_to')
        meta_key = filter_form.cleaned_data.get('meta_key')
        meta_value = filter_form.cleaned_data.get('meta_value')

        if name:
            spectra = spectra.filter(material__name__icontains=name)
        if uploaded_by:
            spectra = spectra.filter(uploaded_by__username__icontains=uploaded_by)
        if upload_date_from:
            spectra = spectra.filter(upload_timestamp__date__gte=upload_date_from)
        if upload_date_to:
            spectra = spectra.filter(upload_timestamp__date__lte=upload_date_to)
        if meta_key and meta_value:
            spectra = spectra.filter(metadata__has_key=meta_key, metadata__contains={meta_key: meta_value})

    spectrum = None
    plotly_fig_refidx = None
    plotly_fig_abscoeff = None
    meta_data = None

    # Style settings
    axis_style = dict(showgrid=False, showline=True, linecolor='white', linewidth=2, zeroline=False)
    base_layout = dict(
        paper_bgcolor='#1a2d46',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='white'),
        xaxis=axis_style,
        yaxis=axis_style
    )

    if pk is not None:
        spectrum = get_object_or_404(Spectrum, pk=pk)
        freq = getattr(spectrum, 'frequency_data', [])
        refidx = getattr(spectrum, 'refractive_index_data', [])
        abscoeff = getattr(spectrum, 'absorption_coefficient_data', [])

        # Refractive index plot
        fig_refidx = go.Figure()
        if freq and refidx:
            fig_refidx.add_trace(go.Scatter(x=freq, y=refidx, mode='lines', name=spectrum.material.name))
            fig_refidx.update_layout(
                title="Refractive Index",
                xaxis_title="Frequency",
                yaxis_title="Refractive Index (n)",
                **base_layout
            )
        else:
            fig_refidx.update_layout(title="No refractive index data", **base_layout)
        plotly_fig_refidx = fig_refidx.to_json()

        # Absorption coefficient plot
        fig_abscoeff = go.Figure()
        if freq and abscoeff:
            fig_abscoeff.add_trace(go.Scatter(x=freq, y=abscoeff, mode='lines', name=spectrum.material.name))
            fig_abscoeff.update_layout(
                title="Absorption Coefficient",
                xaxis_title="Frequency",
                yaxis_title="Absorption Coefficient",
                **base_layout
            )
        else:
            fig_abscoeff.update_layout(title="No absorption coefficient data", **base_layout)
        plotly_fig_abscoeff = fig_abscoeff.to_json()

        meta_data = {
            'Material': spectrum.material.name if spectrum.material else '',
            'Uploaded by': spectrum.uploaded_by.username if spectrum.uploaded_by else '',
            'Upload time': spectrum.upload_timestamp,
        }
    else:
        fig_refidx = go.Figure()
        fig_refidx.update_layout(title="", **base_layout)
        plotly_fig_refidx = fig_refidx.to_json()

        fig_abscoeff = go.Figure()
        fig_abscoeff.update_layout(title="", **base_layout)
        plotly_fig_abscoeff = fig_abscoeff.to_json()

    return render(request, 'spectra/spectrum_list.html', {
        'spectra': spectra,
        'filter_form': filter_form,
        'selected_spectrum': spectrum,
        'plotly_fig_refidx': plotly_fig_refidx,
        'plotly_fig_abscoeff': plotly_fig_abscoeff,
        'meta_data': meta_data,
    })

def spectrum_plot_api(request, pk):
    spectrum = Spectrum.objects.get(pk=pk)
    # Example: replace with your actual data fields
    freq = getattr(spectrum, 'frequency_data', [])
    refidx = getattr(spectrum, 'refractive_index_data', [])
    fig = go.Figure()
    if freq and refidx:
        fig.add_trace(go.Scatter(x=freq, y=refidx, mode='lines', name=spectrum.material.name))
    return JsonResponse(fig.to_plotly_json())

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
        freq = getattr(spectrum, 'frequency_data', [])
        refidx = getattr(spectrum, 'refractive_index_data', [])
        fig = go.Figure()
        if freq and refidx:
            fig.add_trace(go.Scatter(x=freq, y=refidx, mode='lines', name=spectrum.material.name))
        context['plotly_fig'] = fig.to_json()
        return context
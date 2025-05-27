# spectra/views.py
import base64

from pydotthz import DotthzFile, DotthzMeasurement, DotthzMetaData
from django.forms import forms
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .serializers import SpectrumSerializer
from .models import Material
from .forms import SpectrumUploadForm, SpectrumFilterForm
import io
from rest_framework.authtoken.models import Token
from django.http import HttpResponse
import numpy as np

from django.shortcuts import render, get_object_or_404
from .models import Spectrum
import plotly.graph_objs as go


def home_view(request):
    api_key = None
    if request.user.is_authenticated:
        token, created = Token.objects.get_or_create(user=request.user)
        api_key = token.key

    context = {
        'api_key': api_key,
        'user_is_authenticated': request.user.is_authenticated,
    }
    return render(request, 'spectra/home.html', context)


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
    print(f"{filter_form=}")

    return render(request, 'spectra/spectrum_list.html', {
        'spectra': spectra,
        'filter_form': filter_form,
        'selected_spectrum': spectrum,
        'plotly_fig_refidx': plotly_fig_refidx,
        'plotly_fig_abscoeff': plotly_fig_abscoeff,
        'meta_data': meta_data,
    })


class SpectrumListView(ListView):
    model = Spectrum
    template_name = 'spectra/spectrum_list.html'
    context_object_name = 'spectra'
    ordering = ['-upload_timestamp']

    def get_queryset(self):
        queryset = super().get_queryset().select_related('material', 'uploaded_by')
        self.filter_form = SpectrumFilterForm(self.request.GET or None)
        if self.filter_form.is_valid():
            name = self.filter_form.cleaned_data.get('name')
            uploaded_by = self.filter_form.cleaned_data.get('uploaded_by')
            upload_date_from = self.filter_form.cleaned_data.get('upload_date_from')
            upload_date_to = self.filter_form.cleaned_data.get('upload_date_to')
            meta_key = self.filter_form.cleaned_data.get('meta_key')
            meta_value = self.filter_form.cleaned_data.get('meta_value')

            if name:
                queryset = queryset.filter(material__name__icontains=name)
            if uploaded_by:
                queryset = queryset.filter(uploaded_by__username__icontains=uploaded_by)
            if upload_date_from:
                queryset = queryset.filter(upload_timestamp__date__gte=upload_date_from)
            if upload_date_to:
                queryset = queryset.filter(upload_timestamp__date__lte=upload_date_to)
            if meta_key and meta_value:
                queryset = queryset.filter(metadata__has_key=meta_key, metadata__contains={meta_key: meta_value})
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = getattr(self, 'filter_form', SpectrumFilterForm())
        return context


@login_required
def regenerate_token_view(request):
    if request.method == 'POST':
        Token.objects.filter(user=request.user).delete()
        Token.objects.create(user=request.user)
    return redirect('spectra:home')


@login_required
def upload_spectrum(request):
    initial_form_data = {}
    if request.method == 'GET':
        if 'material_id' in request.GET:
            try:
                material_instance = Material.objects.get(pk=request.GET['material_id'])
                initial_form_data['material_name'] = material_instance.name
            except (Material.DoesNotExist, ValueError):
                pass
        # Clear session state on a new GET request or initial page load
        request.session.pop('upload_file_content_b64', None)
        request.session.pop('upload_file_name', None)
        request.session.pop('prompt_thickness', None)
        form = SpectrumUploadForm(initial=initial_form_data)
        return render(request, 'spectra/upload_spectrum.html', {'form': form, 'prompt_thickness': False})

    # POST request handling
    # Instantiate form once with all POST data and FILES
    form = SpectrumUploadForm(request.POST, request.FILES)
    file_to_parse = None
    # Determine if the template should prompt for thickness based on session state
    prompt_thickness_context = request.session.get('prompt_thickness', False)

    # Scenario 1: A new binary file is being uploaded in the current request
    if 'binary_data_file' in request.FILES:
        uploaded_file = request.FILES['binary_data_file']
        binary_file_content_from_current_upload = uploaded_file.read()
        # Reset file pointer so Django can handle the file if form.is_valid() is called later
        # and the file needs to be processed by ModelForm's save.
        uploaded_file.seek(0)

        # Store file content in session for potential re-submission (e.g., if thickness is needed)
        request.session['upload_file_content_b64'] = base64.b64encode(binary_file_content_from_current_upload).decode(
            'ascii')
        request.session['upload_file_name'] = uploaded_file.name
        # If a new file is uploaded, reset the prompt_thickness flag in session and context
        request.session['prompt_thickness'] = False
        prompt_thickness_context = False
        file_to_parse = io.BytesIO(binary_file_content_from_current_upload)

    # Scenario 2: No new file in request.FILES, but one exists in session
    # (e.g., user is re-submitting after being prompted for thickness)
    elif request.session.get('upload_file_content_b64'):
        file_bytes_b64 = request.session.get('upload_file_content_b64')
        file_bytes = base64.b64decode(file_bytes_b64)
        file_to_parse = io.BytesIO(file_bytes)
        # prompt_thickness_context is already True if 'prompt_thickness' is true in session

    # If we have binary file content (either from new upload or session)
    if file_to_parse:
        # Get sample_thickness value if user submitted it (e.g., after being prompted)
        sample_thickness_val = request.POST.get('sample_thickness')
        try:
            # Call _parse_binary_file with the file content and optional thickness
            parsed_result = form._parse_binary_file(
                file_to_parse,
                sample_thickness=sample_thickness_val
            )

            # If parsing is successful and returns the expected tuple
            if isinstance(parsed_result, tuple) and len(parsed_result) == 2:
                spectral_data_dict, metadata_dict = parsed_result
                # Attach parsed data to the form instance
                form.parsed_spectral_data_from_view = spectral_data_dict
                form.final_metadata_from_view = metadata_dict

                # Successfully parsed, clear session state related to this file upload
                request.session.pop('upload_file_content_b64', None)
                request.session.pop('upload_file_name', None)
                request.session.pop('prompt_thickness', None)
                prompt_thickness_context = False  # Reset prompt on success
            # No 'else' here; if parsing fails in a way that _parse_binary_file handles by returning
            # something else (which it currently doesn't, it raises errors), that would be an issue.

        except forms.ValidationError as e:
            # Add validation errors from _parse_binary_file to the form
            form.add_error(None, e)
            # Check if the error is specifically about missing thickness
            if any("Metadata 'Sample Thickness (mm)' not found and no thickness provided" in msg for msg in e.messages):
                request.session['prompt_thickness'] = True  # Set flag to prompt for thickness on next render
                prompt_thickness_context = True
            else:
                # For other parsing errors (e.g. multiple datasets), clear session file to avoid reprocessing bad data
                # and reset thickness prompt as it's not the issue.
                request.session.pop('upload_file_content_b64', None)
                request.session.pop('upload_file_name', None)
                request.session.pop('prompt_thickness', None)
                prompt_thickness_context = False

        except Exception as e:  # Catch other unexpected errors during parsing
            form.add_error(None, f"An unexpected error occurred during file processing: {e}")
            # Clear session and reset prompt for unexpected errors too
            request.session.pop('upload_file_content_b64', None)
            request.session.pop('upload_file_name', None)
            request.session.pop('prompt_thickness', None)
            prompt_thickness_context = False

    # After attempting to parse (if applicable), validate the whole form.
    # form.is_valid() will:
    # - Be true if binary parsing succeeded and data was attached, and other fields are valid.
    # - Be false if binary parsing failed and form.add_error was called.
    # - Run standard validation for other fields (material_name, notes).
    # - Handle CSV validation if data_file was uploaded and no binary_file.
    if form.is_valid():
        spectrum_instance = form.save(commit=False)
        spectrum_instance.uploaded_by = request.user  # Assign the logged-in user
        spectrum_instance.save()
        # form.save_m2m() # Call if your form has many-to-many fields to save

        # Fully clear session state on successful save
        request.session.pop('upload_file_content_b64', None)
        request.session.pop('upload_file_name', None)
        request.session.pop('prompt_thickness', None)
        return redirect('spectra:spectrum_list')  # Or your desired success URL
    else:
        # Form is not valid, re-render with errors.
        # prompt_thickness_context should be correctly set if thickness is the issue.
        return render(request, 'spectra/upload_spectrum.html', {
            'form': form,
            'prompt_thickness': prompt_thickness_context
        })


# You would also need to ensure your 'spectra/upload_spectrum.html' template
# can conditionally display an input field for 'sample_thickness' when 'prompt_thickness' is true.
# Example snippet for template:
# {% if prompt_thickness %}
#   <p class="errornote">Sample thickness is required. Please provide it below.</p>
#   {{ form.sample_thickness.label_tag }}
#   {{ form.sample_thickness }}
#   {{ form.sample_thickness.errors }}
# {% endif %}
# This requires 'sample_thickness' to be a field in your SpectrumUploadForm.


@login_required
def download_spectrum_file(request, pk):
    spectrum = get_object_or_404(Spectrum, pk=pk)

    filename = f"{spectrum.material.name.replace(' ', '_')}_{spectrum.pk}.thz"
    thz_buffer = io.BytesIO()

    # Define known standard metadata fields for pydotthz.DotthzMetaData
    standard_meta_fields = [
        'user', 'email', 'institution', 'orcid', 'description',
        'date', 'time', 'version', 'instrument', 'mode'
    ]

    try:
        with DotthzFile(thz_buffer, "w") as f:
            measurement_name = f"{spectrum.material.name.replace(' ', '_')}_ID{spectrum.pk}"
            measurement = DotthzMeasurement()
            measurement.datasets = {}

            meta_data = DotthzMetaData()
            # Populate metadata from spectrum.metadata
            if spectrum.metadata:
                for key, value in spectrum.metadata.items():
                    if value is None:  # Skip None values or pydotthz might error
                        continue
                    if key in standard_meta_fields:
                        setattr(meta_data, key, str(value))  # Ensure value is string if expected
                    else:
                        meta_data.md[key] = value

            if not meta_data.description and spectrum.notes:  # If not set from metadata, use notes
                meta_data.description = spectrum.notes
            elif not meta_data.description:
                meta_data.description = f"Exported data for {spectrum.material.name}"

            # Ensure some key identifiers from the database are in the custom metadata
            meta_data.md["DatabaseSpectrumID"] = spectrum.pk
            meta_data.md["DatabaseMaterialName"] = spectrum.material.name
            meta_data.md["DatabaseUploadTimestamp"] = spectrum.upload_timestamp.isoformat()
            meta_data.md["DatabaseUploadUser"] = spectrum.uploaded_by.username
            if spectrum.notes:
                meta_data.md["DatabaseNotes"] = spectrum.notes

            raw_sample_list_t = spectrum.raw_sample_data_t
            raw_sample_list_p = spectrum.raw_sample_data_p
            if raw_sample_list_t and raw_sample_list_p:
                try:
                    raw_sample_np = np.array([np.array([t, p]) for t, p in zip(raw_sample_list_t, raw_sample_list_p)],
                                             dtype=float)
                    measurement.datasets["Sample"] = raw_sample_np
                except Exception as e_rs:
                    print(f"Could not process raw_sample_data for spectrum {pk}: {e_rs}")

            raw_reference_list_t = spectrum.raw_reference_data_t
            raw_reference_list_p = spectrum.raw_reference_data_p
            if raw_reference_list_t and raw_reference_list_p:
                try:
                    raw_reference_np = np.array(
                        [np.array([t, p]) for t, p in zip(raw_reference_list_t, raw_reference_list_p)], dtype=float)
                    measurement.datasets["Reference"] = raw_reference_np
                except Exception as e_rr:
                    print(f"Could not process raw_reference_data for spectrum {pk}: {e_rr}")

            measurement.meta_data = meta_data
            f.write_measurement(measurement_name, measurement)

    except Exception as e:
        print(f"Error creating .thz file for spectrum {pk}: {e}")
        return HttpResponse(f"Could not generate .thz file due to an internal error. Details: {e}", status=500,
                            content_type="text/plain")

    thz_buffer.seek(0)
    file_content = thz_buffer.getvalue()
    thz_buffer.close()

    response = HttpResponse(file_content, content_type='application/pydotthz')  # Or application/octet-stream
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_upload_spectrum(request):
    """
    API endpoint to upload a new spectrum.
    Expects 'binary_data_file' and 'material_name' in request.data.
    """
    # This is a simplified version. You'll need to adapt it to your
    # existing upload_spectrum logic, especially file handling and metadata extraction.
    # Consider using a serializer for validation and saving.
    # For example, if your SpectrumSerializer can handle file uploads:
    # serializer = SpectrumSerializer(data=request.data, context={'request': request})
    # if serializer.is_valid():
    #     serializer.save(uploaded_by=request.user)
    #     return Response(serializer.data, status=status.HTTP_201_CREATED)
    # return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # Placeholder logic:
    if 'binary_data_file' not in request.FILES or 'material_name' not in request.data:
        return Response({'error': 'Missing required fields (binary_data_file, material_name).'},
                        status=status.HTTP_400_BAD_REQUEST)

    # Add your file processing and model creation logic here
    # Example:
    # spectrum = Spectrum.objects.create(
    #     material_name=request.data['material_name'],
    #     binary_data_file=request.FILES['binary_data_file'],
    #     uploaded_by=request.user
    # )
    # # Perform any additional processing like metadata extraction if needed
    # spectrum.save()
    # return Response({'message': 'Spectrum uploaded successfully', 'id': spectrum.id}, status=status.HTTP_201_CREATED)

    return Response({'message': 'API upload endpoint hit. Implement actual upload logic.'}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_spectrum_list(request):
    """
    API endpoint to list all spectra.
    """
    spectra = Spectrum.objects.all()  # Or filter as needed, e.g., by user
    serializer = SpectrumSerializer(spectra, many=True, context={'request': request})
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_spectrum_detail(request, pk):
    """
    API endpoint to retrieve a single spectrum's details.
    """
    try:
        spectrum = Spectrum.objects.get(pk=pk)
    except Spectrum.DoesNotExist:
        return Response({'error': 'Spectrum not found.'}, status=status.HTTP_404_NOT_FOUND)

    serializer = SpectrumSerializer(spectrum, context={'request': request})
    return Response(serializer.data)

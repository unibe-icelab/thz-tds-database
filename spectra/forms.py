# spectra/forms.py
import json
from django import forms
from thzpy.timedomain import common_window
from thzpy.transferfunctions import uniform_slab
import re
from django.core.exceptions import ValidationError

from .models import Spectrum, Material
import pydotthz
# Removed: from pydotthz.core import Empty
import numpy as np


class SpectrumFilterForm(forms.Form):
    name = forms.CharField(label="Material Name", required=False)
    uploaded_by = forms.CharField(label="Uploaded By", required=False)
    upload_date_from_or_exact = forms.DateField(
        required=False,
        label="Uploaded on/after",
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    upload_date_to = forms.DateField(label="Uploaded Before", required=False,
                                     widget=forms.DateInput(attrs={'type': 'date'}))
    meta_key = forms.CharField(label="Metadata Key", required=False)
    meta_value = forms.CharField(label="Metadata Value", required=False)


def validate_material_name(value):
    if not re.match(r'^[\w\-]+$', value, re.UNICODE):
        raise ValidationError(
            "Name must only contain letters, numbers, underscores, or hyphens (no spaces or special characters)."
        )


class SpectrumUploadForm(forms.ModelForm):
    material_name = forms.CharField(
        label="Material Name",
        max_length=100,
        validators=[validate_material_name],
        help_text="Enter the name for the material. If it doesn't exist, it will be created."
    )
    binary_data_file = forms.FileField(
        label="dotTHz file",
        required=False,
        help_text="Upload a single file (.thz) containing both spectral data and metadata."
    )
    data_file = forms.FileField(
        label="Spectral Data File (CSV - Alternative)",
        required=False,
        help_text="Alternatively, upload a UTF-8 encoded CSV text file with two columns: frequency, intensity."
    )
    metadata_json_text = forms.CharField(
        label="Metadata (JSON - for CSV Upload)",
        widget=forms.Textarea(
            attrs={'rows': 4, 'placeholder': 'e.g., {"instrument": "Bruker XYZ", "resolution": "4 cm-1"}'}),
        required=False,
        help_text="If uploading a CSV, provide metadata as a JSON formatted string. This is ignored if a combined file is uploaded."
    )

    class Meta:
        model = Spectrum
        fields = ['material_name', 'binary_data_file', 'data_file', 'metadata_json_text', 'notes']

    def __init__(self, *args, **kwargs):
        kwargs.pop('sample_choices', None)
        kwargs.pop('ref_choices', None)
        super().__init__(*args, **kwargs)

    def _parse_binary_file(self, b_file, sample_thickness=None):
        """
        Parses .thz binary files.
        Extracts full metadata (converting pydotthz's Empty type to None) and processed spectral data.
        Raises ValidationError if multiple sample/reference datasets are found or if thickness is missing/invalid.
        This method is intended to be called by the VIEW.
        """
        try:
            b_file.seek(0)
            with pydotthz.DotthzFile(b_file) as f:
                measurement_keys = list(f.get_measurements().keys())
                if not measurement_keys:
                    raise forms.ValidationError("No measurements found in the .thz file.")
                measurement_key = measurement_keys[0]
                measurement = f.get_measurement(measurement_key)

                dataset_keys = list(measurement.datasets.keys())
                sample_candidates = [k for k in dataset_keys if "sample" in k.lower() or "measurement" in k.lower()]
                ref_candidates = [k for k in dataset_keys if "ref" in k.lower()]

                if len(sample_candidates) > 1:
                    raise forms.ValidationError(
                        f"Multiple sample datasets found: {', '.join(sample_candidates)}. Please ensure the file contains only one sample dataset."
                    )
                if len(ref_candidates) > 1:
                    raise forms.ValidationError(
                        f"Multiple reference datasets found: {', '.join(ref_candidates)}. Please ensure the file contains only one reference dataset."
                    )

                sample_key = sample_candidates[0] if sample_candidates else None
                ref_key = ref_candidates[0] if ref_candidates else None

                if not sample_key:
                    raise forms.ValidationError(
                        f"No sample dataset found. Available datasets: {', '.join(dataset_keys)}"
                    )
                if not ref_key:
                    raise forms.ValidationError(
                        f"No reference dataset found. Available datasets: {', '.join(dataset_keys)}"
                    )

                # Extract and sanitize full metadata
                dotthz_meta = measurement.meta_data
                metadata_dict = {}

                # Standard fields from DotthzMetaData attributes
                standard_fields_map = {
                    "user": "", "email": "", "orcid": "", "institution": "",
                    "description": "", "version": "1.00", "mode": "",
                    "instrument": "", "time": "", "date": ""
                }
                for field_name, default_val in standard_fields_map.items():
                    val = getattr(dotthz_meta, field_name, default_val)
                    # Check for pydotthz's Empty type by class name
                    metadata_dict[field_name] = None if val.__class__.__name__ == 'Empty' else val

                # Custom metadata from dotthz_meta.md dictionary
                if hasattr(dotthz_meta, 'md') and isinstance(dotthz_meta.md, dict):
                    for key, value in dotthz_meta.md.items():
                        # This will overwrite standard fields if keys conflict.
                        # Check for pydotthz's Empty type by class name
                        metadata_dict[key] = None if value.__class__.__name__ == 'Empty' else value

                # Ensure 'md' itself is not an Empty object if it was accessed directly
                if 'md' in metadata_dict and metadata_dict['md'].__class__.__name__ == 'Empty':
                    metadata_dict['md'] = {}

                # Thickness extraction and validation
                thickness_float = None
                # Use .get() on metadata_dict to safely access potentially missing keys
                thickness_value_from_meta = metadata_dict.get("Sample Thickness (mm)")

                if thickness_value_from_meta is not None:  # Will be None if key missing or value was Empty
                    try:
                        # Handle cases where thickness might be a numpy type
                        thickness_float = float(
                            thickness_value_from_meta.item() if hasattr(thickness_value_from_meta,
                                                                        'item') else thickness_value_from_meta
                        )
                    except (ValueError, TypeError):
                        # Invalid format in metadata, thickness_float remains None.
                        pass

                if thickness_float is None and sample_thickness is not None:
                    try:
                        thickness_float = float(sample_thickness)
                    except (ValueError, TypeError):
                        raise forms.ValidationError(
                            f"Provided sample thickness override '{sample_thickness}' is not a valid number."
                        )

                if thickness_float is None:
                    error_message_detail = ""
                    if "Sample Thickness (mm)" in metadata_dict:  # Check original presence before sanitization
                        original_meta_thickness = getattr(dotthz_meta.md, 'Sample Thickness (mm)',
                                                          getattr(dotthz_meta, 'Sample Thickness (mm)',
                                                                  None))  # Check both md and direct
                        if original_meta_thickness is not None and original_meta_thickness.__class__.__name__ == 'Empty':
                            error_message_detail = "Metadata 'Sample Thickness (mm)' was present but empty. "
                        elif thickness_value_from_meta is None and original_meta_thickness is not None:  # It was present but not convertible
                            error_message_detail = f"Metadata 'Sample Thickness (mm)' ('{original_meta_thickness}') could not be converted to a number. "
                        # If thickness_value_from_meta is None and original_meta_thickness was also None, it means it wasn't in metadata_dict

                    if not error_message_detail and "Sample Thickness (mm)" not in metadata_dict:
                        error_message_detail = "Metadata 'Sample Thickness (mm)' not found in file. "

                    if sample_thickness is None:
                        error_message_detail += "And no override thickness was provided."

                    final_error_message = (f"{error_message_detail.strip()} "
                                           "Please ensure a valid thickness is available either in the file's metadata "
                                           "or as an override parameter.")
                    raise forms.ValidationError(final_error_message)

                # Process spectral data
                processed_sample, processed_reference = common_window(
                    [measurement.datasets[sample_key], measurement.datasets[ref_key]],
                    half_width=15, win_func="adapted blackman"
                )
                buffer = uniform_slab(
                    thickness_float, processed_sample, processed_reference,
                    upsampling=3, min_frequency=0.2, max_frequency=3, all_optical_constants=True
                )

                expected_keys = ["frequency", "refractive_index", "absorption_coefficient"]
                for key in expected_keys:
                    if key not in buffer:
                        raise forms.ValidationError(f"Calculated buffer data is missing key: '{key}'.")

                spectral_data_dict = {
                    'frequency': list(buffer["frequency"]),
                    'refractive_index': list(np.real(buffer["refractive_index"])),
                    'absorption_coefficient': list(buffer["absorption_coefficient"])
                }

            return spectral_data_dict, metadata_dict
        except KeyError as e:
            raise forms.ValidationError(f"Error processing .thz file: Missing key: '{e.args[0]}'.")
        except (IndexError, AttributeError) as e:
            # import traceback # For debugging
            # traceback.print_exc() # For debugging
            raise forms.ValidationError(f"Error processing .thz file: Data structure error. Details: {e}")
        except forms.ValidationError:  # Re-raise validation errors from this method
            raise
        except Exception as e:
            # import traceback # For debugging
            # traceback.print_exc() # For debugging
            raise forms.ValidationError(f"Unexpected error processing .thz file: {type(e).__name__}: {e}")

    def clean(self):
        cleaned_data = super().clean()

        if not cleaned_data.get('material_name'):
            self.add_error('material_name', 'This field is required.')

        binary_file = cleaned_data.get('binary_data_file')
        data_file = cleaned_data.get('data_file')

        if not binary_file and not data_file:
            if not (hasattr(self, 'parsed_spectral_data_from_view') and self.parsed_spectral_data_from_view):
                self.add_error(None, "You must upload either a 'dotTHz file' or a 'Spectral Data File (CSV)'.")

        if data_file and not binary_file:  # CSV upload route
            metadata_json_str = cleaned_data.get('metadata_json_text')
            if not metadata_json_str:
                self.add_error('metadata_json_text', 'Metadata is required when uploading a CSV data file.')
            else:
                try:
                    json.loads(metadata_json_str)
                except json.JSONDecodeError:
                    self.add_error('metadata_json_text', 'Invalid JSON format for metadata.')
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        material_name_val = self.cleaned_data.get('material_name')
        if material_name_val:
            material, created = Material.objects.get_or_create(
                name=material_name_val,
                defaults={'description': f'Material created via spectrum upload: {material_name_val}'}
            )
            instance.material = material

        parsed_spectral_data = getattr(self, 'parsed_spectral_data_from_view', None)
        final_metadata = getattr(self, 'final_metadata_from_view', None)

        if parsed_spectral_data and isinstance(parsed_spectral_data, dict):
            instance.spectral_data = parsed_spectral_data
            instance.frequency_data = parsed_spectral_data.get("frequency") or []
            instance.refractive_index_data = parsed_spectral_data.get("refractive_index") or []
            instance.absorption_coefficient_data = parsed_spectral_data.get("absorption_coefficient") or []
        else:
            instance.spectral_data = {}
            instance.frequency_data = []
            instance.refractive_index_data = []
            instance.absorption_coefficient_data = []

        if final_metadata and isinstance(final_metadata, dict):
            instance.metadata = final_metadata
        else:
            instance.metadata = {}

        instance.refractive_index_data_available = bool(instance.refractive_index_data)
        instance.absorption_coefficient_data_available = bool(instance.absorption_coefficient_data)

        if commit:
            instance.save()
        return instance


class MaterialForm(forms.ModelForm):
    class Meta:
        model = Material
        fields = ['name', 'description']
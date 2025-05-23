# spectra/forms.py
import csv
import io
import json
from django import forms
from thzpy.timedomain import common_window
from thzpy.transferfunctions import uniform_slab

from .models import Spectrum, Material
import pydotthz
import numpy as np  # Ensure NumPy is imported


class SpectrumUploadForm(forms.ModelForm):
    material_name = forms.CharField(
        label="Material Name",
        max_length=100,
        help_text="Enter the name for the material. If it doesn't exist, it will be created."
    )
    binary_data_file = forms.FileField(
        label="Combined Data and Metadata File (Recommended)",
        required=False,
        help_text="Upload a single file (e.g., JCAMP-DX, HDF5) containing both spectral data and metadata. If this is provided, the CSV and Metadata text field below will be ignored. A specific parser for your chosen binary format needs to be implemented in the form's `_parse_binary_file` method."
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

    def _parse_binary_file(self, b_file):
        """
        Parses .thz binary files.
        Converts complex numbers in spectral data to a JSON-serializable format.
        """
        try:
            b_file.seek(0)

            with pydotthz.DotthzFile(b_file) as f:
                measurement_keys = list(f.get_measurements().keys())
                if not measurement_keys:
                    raise forms.ValidationError("No measurements found in the .thz file.")
                measurement_key = measurement_keys[0]
                measurement = f.get_measurement(measurement_key)

                if "Sample" not in measurement.datasets or "Reference" not in measurement.datasets:
                    raise forms.ValidationError("Dataset 'Sample' or 'Reference' not found.")

                thickness_raw = measurement.meta_data.md.get("Sample Thickness (mm)")
                if thickness_raw is None:
                    raise forms.ValidationError("Metadata 'Sample Thickness (mm)' not found.")
                try:
                    thickness_float = float(thickness_raw.item() if hasattr(thickness_raw, 'item') else thickness_raw)
                except (ValueError, TypeError) as e_conv:
                    raise forms.ValidationError(f"Could not convert thickness '{thickness_raw}' to a number: {e_conv}")

                processed_sample, processed_reference = common_window(
                    [measurement.datasets["Sample"], measurement.datasets["Reference"]],
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
                    'refractive_index': list( np.real(buffer["refractive_index"])),
                    'absorption_coefficient': list(buffer["absorption_coefficient"])
                }
                metadata_dict = {"thickness_mm": thickness_float}
            return spectral_data_dict, metadata_dict
        except KeyError as e:
            raise forms.ValidationError(f"Error processing .thz file: Missing key: '{e.args[0]}'.")
        except (IndexError, AttributeError) as e:
            raise forms.ValidationError(f"Error processing .thz file: Data structure error. Details: {e}")
        except forms.ValidationError:
            raise
        except Exception as e:
            raise forms.ValidationError(f"Unexpected error processing .thz file: {type(e).__name__}: {e}")

    def _parse_csv_file(self, c_file):
        frequencies = []
        intensities = []
        try:
            c_file.seek(0)
            try:
                text_data = c_file.read().decode('utf-8')
            except UnicodeDecodeError:
                raise forms.ValidationError("CSV file encoding is not UTF-8.")

            reader = csv.reader(io.StringIO(text_data))
            for i, row in enumerate(reader):
                if not row: continue
                if len(row) != 2:
                    raise forms.ValidationError(f"Row {i + 1}: Must have 2 values. Found {len(row)}.")
                try:
                    frequencies.append(float(row[0].strip()))
                    intensities.append(float(row[1].strip()))
                except ValueError:
                    raise forms.ValidationError(f"Row {i + 1}: Values must be numbers.")
            if not frequencies:
                raise forms.ValidationError("CSV file is empty or has no valid data rows.")
            return {'frequency': frequencies, 'intensity': intensities}
        except csv.Error as e:
            raise forms.ValidationError(f"Error parsing CSV: {e}")
        except forms.ValidationError:
            raise
        except Exception as e:
            raise forms.ValidationError(f"Could not process CSV: {e}")

    def clean(self):
        cleaned_data = super().clean()
        binary_file = cleaned_data.get('binary_data_file')
        csv_file = cleaned_data.get('data_file')
        metadata_json_str = cleaned_data.get('metadata_json_text', "")

        cleaned_data['parsed_spectral_data'] = None
        cleaned_data['final_metadata'] = {}

        if binary_file and csv_file:
            self.add_error(None, "Please use either the 'Combined File' or 'CSV File + Metadata', not both.")
            return cleaned_data

        if binary_file:
            try:
                spectral_data, metadata_dict = self._parse_binary_file(binary_file)
                cleaned_data['parsed_spectral_data'] = spectral_data
                cleaned_data['final_metadata'] = metadata_dict
                cleaned_data['data_file'] = None
                cleaned_data['metadata_json_text'] = ""
                # The line `cleaned_data['material_name'] = "hello"` was removed from here.
            except forms.ValidationError as e:
                self.add_error('binary_data_file', e)
        elif csv_file:
            try:
                spectral_data = self._parse_csv_file(csv_file)
                cleaned_data['parsed_spectral_data'] = spectral_data
            except forms.ValidationError as e:
                self.add_error('data_file', e)

            if not self.errors.get('data_file'):
                if metadata_json_str:
                    try:
                        loaded_meta = json.loads(metadata_json_str)
                        if not isinstance(loaded_meta, dict):
                            self.add_error('metadata_json_text', "Metadata must be a valid JSON object.")
                        else:
                            cleaned_data['final_metadata'] = loaded_meta
                    except json.JSONDecodeError:
                        self.add_error('metadata_json_text', "Invalid JSON format for metadata.")
        else:
            if not self.errors:
                self.add_error(None,
                               "You must upload either a 'Combined Data and Metadata File' or a 'Spectral Data File (CSV)'.")

        if not cleaned_data.get('material_name'):
            self.add_error('material_name', 'This field is required.')

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

        instance.spectral_data = self.cleaned_data.get('parsed_spectral_data') or {}
        instance.frequency_data = self.cleaned_data.get('parsed_spectral_data').get("frequency") or []
        instance.refractive_index_data = self.cleaned_data.get('parsed_spectral_data').get("refractive_index") or []
        instance.absorption_coefficient_data = self.cleaned_data.get('parsed_spectral_data').get("absorption_coefficient") or []
        instance.metadata = self.cleaned_data.get('final_metadata') or {}

        if commit:
            instance.save()
        return instance


class MaterialForm(forms.ModelForm):
    class Meta:
        model = Material
        fields = ['name', 'description']
# spectra/forms.py
import csv
import io
import json
from django import forms
from .models import Spectrum, Material
import pydotthz

class SpectrumUploadForm(forms.ModelForm):
    binary_data_file = forms.FileField(
        label="Combined Data and Metadata File (Recommended)",
        required=False,  # Made conditionally required in clean()
        help_text="Upload a single file (e.g., JCAMP-DX, HDF5) containing both spectral data and metadata. If this is provided, the CSV and Metadata text field below will be ignored. A specific parser for your chosen binary format needs to be implemented in the form's `_parse_binary_file` method."
    )
    data_file = forms.FileField(
        label="Spectral Data File (CSV - Alternative)",
        required=False,  # Made conditionally required in clean()
        help_text="Alternatively, upload a UTF-8 encoded CSV text file with two columns: frequency, intensity."
    )
    metadata_json_text = forms.CharField(
        label="Metadata (JSON - for CSV Upload)",
        widget=forms.Textarea(
            attrs={'rows': 4, 'placeholder': 'e.g., {"instrument": "Bruker XYZ", "resolution": "4 cm-1"}'}),
        required=False,  # Only relevant if data_file is used
        help_text="If uploading a CSV, provide metadata as a JSON formatted string. This is ignored if a combined file is uploaded."
    )

    class Meta:
        model = Spectrum
        fields = ['material', 'binary_data_file', 'data_file', 'metadata_json_text', 'notes']
        # 'spectral_data' and 'metadata' (model fields) are populated in save()
        # 'uploaded_by' is handled in the view.

    def _parse_binary_file(self, b_file):
        """
        Placeholder for actual binary file parsing logic.
        This method should parse the binary file and return a tuple:
        (spectral_data_dict, metadata_dict)
        spectral_data_dict = {'frequency': [...], 'intensity': [...]}
        metadata_dict = {...}
        If parsing fails, it should raise forms.ValidationError.

        IMPORTANT: You need to implement the actual parsing logic for your
        specific binary file format(s) here. The example below is a
        simple text-based combined file for demonstration.
        """
        b_file.seek(0)
        # ---- BEGIN DUMMY/EXAMPLE PARSER (assumes text: 1st line JSON meta, rest CSV data) ----
        try:
            with pydotthz.DotthzFile(b_file) as f:
                measurements = f.get_measurements()
                measurement = f.get_measurement(measurements[0])
                time = measurement.datasets["Sample"][:,0]
                signal = measurement.datasets["Sample"][:,1]
                ref_time = measurement.datasets["Reference"][:,0]
                ref_signal = measurement.datasets["Reference"][:,1]


            # Attempt to decode as UTF-8; for true binary, use appropriate libraries
            content = b_file.read().decode('utf-8')
            lines = content.splitlines()
            if not lines:
                raise forms.ValidationError("Combined file is empty.")

            metadata_dict = json.loads(lines[0])
            if not isinstance(metadata_dict, dict):
                raise forms.ValidationError("First line of combined file (metadata) is not a valid JSON object.")

            frequencies = []
            intensities = []
            if len(lines) < 2:
                raise forms.ValidationError("No spectral data found after metadata in combined file.")

            for i, line in enumerate(lines[1:]):
                if not line.strip():  # Skip empty lines
                    continue
                parts = line.split(',')  # Assuming CSV-like data part
                if len(parts) != 2:
                    raise forms.ValidationError(
                        f"Data line {i + 1} in combined file: Expected 2 values, got {len(parts)} ('{line}').")
                try:
                    frequencies.append(float(parts[0].strip()))
                    intensities.append(float(parts[1].strip()))
                except ValueError:
                    raise forms.ValidationError(
                        f"Data line {i + 1} in combined file: Non-numeric data found ('{parts[0]}', '{parts[1]}').")

            if not frequencies or not intensities:  # Check after processing all data lines
                raise forms.ValidationError("No valid spectral data rows found after metadata in combined file.")

            spectral_data_dict = {'frequency': frequencies, 'intensity': intensities}
            return spectral_data_dict, metadata_dict
        except UnicodeDecodeError:
            raise forms.ValidationError(
                "Could not decode combined file as UTF-8. Ensure it's a text-based combined file or implement appropriate binary parsing.")
        except json.JSONDecodeError:
            raise forms.ValidationError("Failed to parse metadata (first line) from combined file as JSON.")
        except forms.ValidationError:  # Re-raise validation errors from this block
            raise
        except Exception as e:  # Catch-all for other parsing issues
            raise forms.ValidationError(f"Error processing combined file: {e}")
        # ---- END DUMMY/EXAMPLE PARSER ----
        # Example for a real scenario:
        # if b_file.name.endswith('.jdx'):
        #     from jcamp import jcamp_read # Fictional library
        #     data = jcamp_read(b_file.read())
        #     return {'frequency': data.x, 'intensity': data.y}, data.parameters
        # else:
        #     raise forms.ValidationError("Unsupported binary file type.")
        # raise NotImplementedError("Binary file parsing logic needs to be implemented for your specific format.")

    def _parse_csv_file(self, c_file):
        frequencies = []
        intensities = []
        try:
            c_file.seek(0)
            try:
                text_data = c_file.read().decode('utf-8')
            except UnicodeDecodeError:
                raise forms.ValidationError("CSV file encoding is not UTF-8. Please upload a UTF-8 encoded text file.")

            reader = csv.reader(io.StringIO(text_data))
            row_count = 0
            for i, row in enumerate(reader):
                if not row:  # Skip empty rows
                    continue
                row_count += 1
                if len(row) != 2:
                    raise forms.ValidationError(
                        f"Row {i + 1}: Each data row must contain exactly two values (frequency, intensity). Found {len(row)} values."
                    )
                try:
                    frequencies.append(float(row[0].strip()))
                    intensities.append(float(row[1].strip()))
                except ValueError:
                    raise forms.ValidationError(
                        f"Row {i + 1}: Both frequency ('{row[0]}') and intensity ('{row[1]}') must be numbers."
                    )

            if row_count == 0 or (not frequencies or not intensities):  # Check after processing all rows
                raise forms.ValidationError("The CSV file is empty or does not contain valid data rows.")

            return {'frequency': frequencies, 'intensity': intensities}

        except csv.Error as e:  # csv.Error is quite broad
            raise forms.ValidationError(f"Error parsing CSV file: {e}")
        except forms.ValidationError:  # Re-raise validation errors from this block
            raise
        except Exception as e:  # Catch-all for other parsing issues
            raise forms.ValidationError(f"Could not process CSV file: {e}")

    def clean(self):
        cleaned_data = super().clean()
        binary_file = cleaned_data.get('binary_data_file')
        csv_file = cleaned_data.get('data_file')
        metadata_json_str = cleaned_data.get('metadata_json_text', "")

        # These will store the final parsed data to be used in save()
        final_spectral_data = None
        final_metadata_dict = {}

        if binary_file and csv_file:
            self.add_error(None,
                           "Please use either the 'Combined File' upload (Option 1) or the 'CSV File + Metadata' upload (Option 2), but not both.")
            return cleaned_data  # Stop further validation if this fundamental error occurs

        if binary_file:
            try:
                final_spectral_data, final_metadata_dict = self._parse_binary_file(binary_file)
                # If binary file is provided and successfully parsed, ignore CSV fields
                cleaned_data['data_file'] = None
                cleaned_data['metadata_json_text'] = ""
            except forms.ValidationError as e:
                self.add_error('binary_data_file', e)
        elif csv_file:
            try:
                final_spectral_data = self._parse_csv_file(csv_file)
            except forms.ValidationError as e:
                self.add_error('data_file', e)

            # Process metadata_json_text only if csv_file was provided
            # This metadata is only for the CSV path
            if metadata_json_str:
                try:
                    loaded_meta = json.loads(metadata_json_str)
                    if not isinstance(loaded_meta, dict):
                        self.add_error('metadata_json_text', "Metadata must be a valid JSON object (e.g., {}).")
                    else:
                        final_metadata_dict = loaded_meta  # Use this metadata for CSV path
                except json.JSONDecodeError:
                    self.add_error('metadata_json_text', "Invalid JSON format for metadata.")
            # If CSV is provided but no metadata_json_text, final_metadata_dict remains {} (default)

        else:
            # Neither binary_file nor csv_file provided
            self.add_error(None,
                           "You must upload either a 'Combined Data and Metadata File' (Option 1) or a 'Spectral Data File (CSV)' (Option 2).")

        # Store successfully parsed data in cleaned_data for the save() method
        # Ensure this happens only if there were no errors for the chosen path
        if final_spectral_data and not self.errors:  # Check general form errors too
            cleaned_data['parsed_spectral_data'] = final_spectral_data

        if not self.errors:  # Only set final_metadata if no errors so far from chosen path
            cleaned_data['final_metadata'] = final_metadata_dict

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)  # Saves fields like 'material', 'notes'

        if 'parsed_spectral_data' in self.cleaned_data:
            instance.spectral_data = self.cleaned_data['parsed_spectral_data']
        else:
            instance.spectral_data = {'frequency': [], 'intensity': []}  # Fallback

        if 'final_metadata' in self.cleaned_data:
            instance.metadata = self.cleaned_data['final_metadata']
        else:
            instance.metadata = {}  # Fallback

        # 'uploaded_by' is set in the view

        if commit:
            instance.save()
        return instance


class MaterialForm(forms.ModelForm):  # Assuming this form exists
    class Meta:
        model = Material
        fields = ['name', 'description']
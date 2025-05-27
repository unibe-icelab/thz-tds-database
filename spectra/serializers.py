from rest_framework import serializers
from .models import Spectrum, Material  # Assuming Material model is in the same app


class SpectrumSerializer(serializers.ModelSerializer):
    # Use StringRelatedField to get the name of the material and username of the uploader
    # If you need more control (e.g., nested object), you can define another serializer for Material
    # and use it here, or use a SlugRelatedField if you want to use a slug for material identification.
    material_name = serializers.CharField(source='material.name', read_only=True)
    uploaded_by_username = serializers.CharField(source='uploaded_by.username', read_only=True)

    # URL for the detail view of the spectrum
    # Ensure your API URL for spectrum detail is named 'api_spectrum_detail'
    # and is in the same namespace if you use namespaces.
    # If you don't have a separate detail URL or prefer not to include it, you can remove this.
    url = serializers.HyperlinkedIdentityField(
        view_name='spectra:api_spectrum_detail',  # Adjust if your app_name or view_name differs
        lookup_field='pk'
    )

    # Custom field for the download URL
    # Ensure your API URL for download is named 'api_download_spectrum_file'
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = Spectrum
        fields = [
            'id',
            'material_name',  # From related Material model
            'notes',
            'upload_timestamp',
            'uploaded_by_username',  # From related User model
            'metadata',  # Assuming this is a JSONField or similar
            'frequency_data',
            'refractive_index_data',
            'absorption_coefficient_data',
            'raw_sample_data_t',  # Potentially large, consider if needed in list/detail views
            'raw_sample_data_p',
            'raw_reference_data_t',
            'raw_reference_data_p',
            'url',  # Link to the spectrum's API detail view
            'download_url',  # Link to download the spectrum file
        ]
        # You might want to make some fields read-only if they are set by the system
        read_only_fields = [
            'id',
            'upload_timestamp',
            'uploaded_by_username',
            'url',
            'download_url',
            'frequency_data',
            'refractive_index_data',
            'absorption_coefficient_data',
        ]

    def get_download_url(self, obj):
        request = self.context.get('request')
        if request is not None:
            # Ensure your API URL for download is named 'api_download_spectrum_file'
            return request.build_absolute_uri(
                serializers.reverse('spectra:api_download_spectrum_file', kwargs={'pk': obj.pk}, request=request)
            )
        return None

    # If you want to handle material creation/linking by name during upload via API:
    # material_name_input = serializers.CharField(write_only=True, source='material.name', required=False)
    #
    # def create(self, validated_data):
    #     material_data = validated_data.pop('material', None)
    #     material_name = material_data.get('name') if material_data else None
    #
    #     if material_name:
    #         material, created = Material.objects.get_or_create(name=material_name)
    #         validated_data['material'] = material
    #
    #     # Assuming 'uploaded_by' should be set from the request user in the view
    #     # e.g., serializer.save(uploaded_by=request.user)
    #     spectrum = Spectrum.objects.create(**validated_data)
    #     return spectrum
    #
    # def update(self, instance, validated_data):
    #     material_data = validated_data.pop('material', None)
    #     material_name = material_data.get('name') if material_data else None
    #
    #     if material_name:
    #         material, created = Material.objects.get_or_create(name=material_name)
    #         instance.material = material
    #
    #     return super().update(instance, validated_data)

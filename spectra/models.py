# spectra/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Material(models.Model):
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class Spectrum(models.Model):
    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name='spectra')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    upload_timestamp = models.DateTimeField(default=timezone.now)

    metadata = models.JSONField(
        blank=True, null=True,
        help_text="Additional metadata as a JSON object (e.g., units, temperature)."
    )
    notes = models.TextField(blank=True, null=True)

    frequency_data = models.JSONField(default=list)
    refractive_index_data = models.JSONField(default=list)
    absorption_coefficient_data = models.JSONField(default=list)
    raw_sample_data_t = models.JSONField(default=list)
    raw_sample_data_p = models.JSONField(default=list)
    raw_reference_data_t = models.JSONField(default=list)
    raw_reference_data_p = models.JSONField(default=list)

    refractive_index_data_available = models.BooleanField(default=False)
    absorption_coefficient_data_available = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "Spectra"
        ordering = ['-upload_timestamp']

    def __str__(self):
        return f"Spectrum for {self.material.name} ({self.upload_timestamp.strftime('%Y-%m-%d')})"
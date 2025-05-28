# spectra/admin.py
from django.contrib import admin
from .models import Material, Spectrum


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)


@admin.register(Spectrum)
class SpectrumAdmin(admin.ModelAdmin):
    list_display = ('material', 'uploaded_by', 'upload_timestamp')
    list_filter = ('material', 'uploaded_by', 'upload_timestamp')
    search_fields = ('material__name', 'notes')
    readonly_fields = ('upload_timestamp',)

    fieldsets = (
        (None, {'fields': ('material', 'metadata', 'notes')}),
        ('Upload Information (auto-set)', {'fields': ('uploaded_by', 'upload_timestamp'), 'classes': ('collapse',)}),
    )

    def save_model(self, request, obj, form, change):
        if not obj.pk:  # When creating a new object
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from os.path import join
from django.conf import settings
from django import forms
from django.db import models
from kraken import binarization, blla, pageseg
from kraken.lib import vgsl
from PIL import Image
from pathlib import Path
from .models import Document, LineSegment
from .segmentation import extract_polygons


def segment_document(modeladmin, request, queryset):
    model_muharaf = vgsl.TorchVGSLModel.load_model("muharaf_seg_best.mlmodel")
    model_blla = vgsl.TorchVGSLModel.load_model("blla.mlmodel")
    for doc in queryset:
        try:
            extract_lines_muharaf(doc.file.path, "muharaf", doc.name, model_muharaf)
            extract_lines_blla(doc.file.path, "blla", doc.name, model_blla)
        except Exception as a:
            pass


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "compare_link", "segments_link"]
    actions = [segment_document]

    def compare_link(self, obj):
        if "_" in obj.name:
            doc_name, page_name = obj.name.rsplit("_", 1)
        else:
            doc_name = obj.name
            page_name = ""
        url = reverse(
            "segment-compare", kwargs={"doc_name": doc_name, "page_name": page_name}
        )
        return format_html('<a href="{}">Compare</a>', url)

    compare_link.short_description = "Compare"

    def segments_link(self, obj):
        url = reverse("admin:selector_linesegment_changelist")
        url = f"{url}?document__id__exact={obj.id}"
        return format_html('<a href="{}">List</a>', url)

    segments_link.short_description = "List"

    def _cleanup_document_files(self, obj):
        import glob
        import os
        from django.conf import settings
        import shutil

        base_name, _ = os.path.splitext(os.path.basename(obj.file.name))
        media_root = settings.MEDIA_ROOT
        # Remove image file (any extension)
        for ext in [".jpg", ".jpeg", ".png"]:
            img_path = os.path.join(media_root, base_name + ext)
            if os.path.exists(img_path):
                os.remove(img_path)
        # Remove all folders matching base_name_*
        for folder in glob.glob(os.path.join(media_root, base_name + "_*")):
            if os.path.isdir(folder):
                shutil.rmtree(folder)

    def delete_model(self, request, obj):
        self._cleanup_document_files(obj)
        super().delete_model(request, obj)

    def save_model(self, request, obj, form, change):
        import os

        if not change and obj.file:
            obj.name = os.path.splitext(os.path.basename(obj.file.name))[0]
        super().save_model(request, obj, form, change)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            self._cleanup_document_files(obj)
        super().delete_queryset(request, queryset)


@admin.register(LineSegment)
class LineSegmentAdmin(admin.ModelAdmin):
    list_display = ["id", "document", "order", "transcribed", "verified"]
    list_filter = ["transcribed", "verified"]
    readonly_fields = ["image_tag"]
    ordering = ["document", "transcribed", "order"]
    formfield_overrides = {
        models.TextField: {'widget': forms.TextInput(attrs={'size': '100'})},
    }
    fieldsets = (
        (
            None,
            {
                "fields": ("document", "image_tag", "transcription", "verified"),
            },
        ),
        (
            "advanced fields",
            {
                "classes": ("collapse",),
                "fields": ("file", "transcribed", "order"),
            },
        ),
    )

    def image_tag(self, obj):
        if obj.file:
            return format_html(
                '<img src="{}" style="max-width:600px; max-height:300px;" />',
                obj.file.url,
            )
        return ""

    image_tag.short_description = "Image"


def extract_lines_muharaf(im_path, save_prefix: str, doc_name: str, model, padding=10):
    # load page image
    im = Image.open(im_path)

    # segment into lines
    seg = blla.segment(im, text_direction="horizontal-rl", model=[model])

    # each region corresponds to a line bounding box
    line_images = extract_polygons(im, seg, pad=padding)
    save_segments(
        join(settings.MEDIA_ROOT, f"{doc_name}_muharaf"), save_prefix, line_images
    )


def extract_lines_blla(im_path, save_prefix: str, doc_name: str, model, padding=10):
    # load page image
    im = Image.open(im_path)

    # segment into lines
    seg = blla.segment(im, text_direction="horizontal-rl", model=[model], device="cuda")

    # each region corresponds to a line bounding box
    line_images = extract_polygons(im, seg, pad=padding)
    save_segments(
        join(settings.MEDIA_ROOT, f"{doc_name}_blla"), save_prefix, line_images
    )


def extract_lines_bbox(im_path, save_prefix: str, doc_name: str):
    # load page image
    im = Image.open(im_path)

    bin = binarization.nlbin(im, 0.5, 0.5, 1.0, 0.2, 80, 20, 5, 90)

    # segment into lines
    seg = pageseg.segment(bin, text_direction="horizontal-rl")
    line_images = extract_polygons(im, seg)
    save_segments(f"{doc_name}_bbox", save_prefix, line_images)


def save_segments(save_folder: str, save_prefix: str, images):
    path = Path(save_folder)
    path.mkdir(parents=True, exist_ok=True)
    for i, output in enumerate(images):
        output[0].save(f"{save_folder}/{save_prefix}_{i}.png")

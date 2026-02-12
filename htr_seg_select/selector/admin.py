import os
from os.path import join
from pathlib import Path

from django import forms
from django.conf import settings
from django.contrib import admin
from django.db import models
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import Document, LineSegment


def segment_document(modeladmin, request, queryset):
    from kraken.lib import vgsl

    model_muharaf = vgsl.TorchVGSLModel.load_model("muharaf_seg_best.mlmodel")
    model_blla = vgsl.TorchVGSLModel.load_model("blla.mlmodel")
    for doc in queryset:
        try:
            extract_lines_muharaf(doc.file.path, "muharaf", doc.name, model_muharaf)
            extract_lines_blla(doc.file.path, "blla", doc.name, model_blla)
        except Exception as a:
            pass


class HasLinesegmentsFilter(admin.SimpleListFilter):
    title = _("دارای تکه خط")
    parameter_name = "has_linesegments"

    def lookups(self, request, model_admin):
        return (
            ("yes", _("بله")),
            ("no", _("خیر")),
        )

    def queryset(self, request, queryset):
        val = self.value()
        if val == "yes":
            return queryset.filter(
                id__in=[doc.pk for doc in queryset if doc.has_linesegments]
            )
        elif val == "no":
            return queryset.filter(
                id__in=[doc.pk for doc in queryset if not doc.has_linesegments]
            )
        return queryset


class IsTranscribedFilter(admin.SimpleListFilter):
    title = _("رونوشت شده")
    parameter_name = "is_transcribed"

    def lookups(self, request, model_admin):
        return (
            ("yes", _("بله")),
            ("no", _("خیر")),
        )

    def queryset(self, request, queryset):
        val = self.value()
        if val == "yes":
            return queryset.filter(
                id__in=[doc.pk for doc in queryset if doc.is_transcribed]
            )
        elif val == "no":
            return queryset.filter(
                id__in=[doc.pk for doc in queryset if not doc.is_transcribed]
            )
        return queryset


class IsVerifiedFilter(admin.SimpleListFilter):
    title = _("تایید شده")
    parameter_name = "is_verified"

    def lookups(self, request, model_admin):
        return (
            ("yes", _("بله")),
            ("no", _("خیر")),
        )

    def queryset(self, request, queryset):
        val = self.value()
        if val == "yes":
            return queryset.filter(
                id__in=[doc.pk for doc in queryset if doc.is_verified]
            )
        elif val == "no":
            return queryset.filter(
                id__in=[doc.pk for doc in queryset if not doc.is_verified]
            )
        return queryset


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "name",
        "compare_link",
        "segments_link",
        "segmenter_link",
        "segments_finalize_link",
        "has_linesegments",
        "is_transcribed",
        "is_verified",
    ]
    actions = [segment_document]
    list_filter = [HasLinesegmentsFilter, IsTranscribedFilter, IsVerifiedFilter]

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
        return format_html('<a href="{}">لیست</a>', url)

    segments_link.short_description = "لیست خط‌ها"

    def segmenter_link(self, obj):
        url = reverse("document-segmenter", args=[obj.id])
        return format_html('<a href="{}">Segment</a>', url)

    segmenter_link.short_description = "Segment"

    def get_queryset(self, request):
        # Store request for later use in segments_finalize_link
        self._request = request
        return super().get_queryset(request)

    def segments_finalize_link(self, obj):
        url = reverse("segment-finalize-admin", args=[obj.id])

        # Preserve active filters/query params if possible
        params = ""
        if hasattr(self, "_request"):
            get_dict = self._request.GET.copy()
            # Remove _changelist_filters or pagination, keep only filters
            for remove_key in ["_changelist_filters", "p"]:
                if remove_key in get_dict:
                    get_dict.pop(remove_key)
            if get_dict:
                params = "?" + get_dict.urlencode()
        url = f"{url}{params}"
        return format_html('<a href="{}">Finalize</a>', url)

    segments_finalize_link.short_description = "Finalize"

    def _cleanup_document_files(self, obj):
        import glob
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

    def has_linesegments(self, obj):
        return obj.linesegments.exists()

    has_linesegments.boolean = True
    has_linesegments.short_description = _("دارای تکه خط")

    def is_transcribed(self, obj):
        return obj.is_transcribed

    is_transcribed.boolean = True
    is_transcribed.short_description = _("رونوشت شده")

    def is_verified(self, obj):
        return obj.is_verified

    is_verified.boolean = True
    is_verified.short_description = _("تایید شده")


@admin.register(LineSegment)
class LineSegmentAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "document",
        "order",
        "transcribed",
        "verified",
        "document_file_link",
    ]
    list_filter = ["transcribed", "verified"]
    readonly_fields = ["image_tag"]
    ordering = ["document", "transcribed", "order"]
    formfield_overrides = {
        models.TextField: {
            "widget": forms.TextInput(
                attrs={"size": "50", "dir": "rtl", "style": "font-size:1.3rem;"}
            )
        },
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

    change_form_template = "admin/selector/linesegment/change_form.html"

    def get_queryset(self, request):
        # Store request GET params for use in context
        qs = super().get_queryset(request)
        self._list_filters = request.GET.urlencode()
        return qs

    def get_next_untranscribed(self, obj, request):
        """
        Returns the next non-transcribed LineSegment queryset, filtered like current changelist (if possible).
        """
        filters = {}
        filter_args = []
        # Try to preserve filters - supports document id, etc.
        if "document__id__exact" in request.GET:
            filters["document__id"] = request.GET["document__id__exact"]
        if hasattr(self, "get_preserved_filters"):
            # Use preserved filters from request, if present
            preserved = self.get_preserved_filters(request)
            if preserved and request.GET.get("_changelist_filters"):
                filter_args.append(request.GET.get("_changelist_filters").split("="))
        if len(filter_args) or len(filters):
            qs = LineSegment.objects.filter(*filter_args, **filters)
        else:
            qs = LineSegment.objects.none()
        next_segment = qs.filter(transcribed=False).order_by("id").first()
        return next_segment

    def has_next_untranscribed(self, obj, request):
        next_seg = self.get_next_untranscribed(obj, request)
        return next_seg is not None

    def render_change_form(self, request, context, *args, **kwargs):
        obj = kwargs.get("obj")
        # context['has_next_untranscribed'] for template logic
        context["has_next_untranscribed"] = (
            self.has_next_untranscribed(obj, request) if obj else False
        )
        return super().render_change_form(request, context, *args, **kwargs)

    def response_change(self, request, obj):
        if "save_and_next" in request.POST:
            next_segment = self.get_next_untranscribed(obj, request)
            if next_segment:
                # Preserve filters/query params
                params = request.GET.urlencode()
                url = reverse(
                    "admin:selector_linesegment_change",
                    args=[next_segment.pk],
                )
                if params:
                    url = f"{url}?{params}"
                return HttpResponseRedirect(url)
            else:
                self.message_user(
                    request, _("No more non-transcribed line segments."), level="info"
                )
                # Fallback to default; stay on current page
                return super().response_change(request, obj)
        return super().response_change(request, obj)

    def image_tag(self, obj):
        if obj.file:
            return format_html(
                '<img src="{}" style="max-width:600px; max-height:300px;" />',
                obj.file.url,
            )
        return ""

    image_tag.short_description = "Image"

    def document_file_link(self, obj):
        if obj.document and obj.document.file:
            url = obj.document.file.url
            return format_html(
                '<a href="{}" target="_blank">{}</a>', url, _("گشودن تصویر")
            )
        return "-"

    document_file_link.short_description = _("تصویر سند")
    document_file_link.admin_order_field = "document"


def extract_lines_muharaf(im_path, save_prefix: str, doc_name: str, model, padding=10):
    from kraken import blla
    from PIL import Image

    from .segmentation import extract_polygons

    base_name = os.path.basename(im_path)
    _, ext = os.path.splitext(base_name)
    ext = ext.lstrip(".")
    # load page image
    im = Image.open(im_path)

    # segment into lines
    seg = blla.segment(im, text_direction="horizontal-rl", model=[model], device="cuda")

    # each region corresponds to a line bounding box
    line_images = extract_polygons(im, seg, pad=padding)
    save_segments(
        join(settings.MEDIA_ROOT, f"{doc_name}_muharaf"),
        save_prefix,
        line_images,
        ext=ext,
    )


def extract_lines_blla(im_path, save_prefix: str, doc_name: str, model, padding=10):
    from kraken import blla
    from PIL import Image

    from .segmentation import extract_polygons

    base_name = os.path.basename(im_path)
    _, ext = os.path.splitext(base_name)
    ext = ext.lstrip(".")
    # load page image
    im = Image.open(im_path)

    # segment into lines
    seg = blla.segment(im, text_direction="horizontal-rl", model=[model], device="cuda")

    # each region corresponds to a line bounding box
    line_images = extract_polygons(im, seg, pad=padding)
    save_segments(
        join(settings.MEDIA_ROOT, f"{doc_name}_blla"), save_prefix, line_images, ext=ext
    )


def extract_lines_bbox(im_path, save_prefix: str, doc_name: str):
    from kraken import binarization, pageseg
    from PIL import Image

    from .segmentation import extract_polygons

    # load page image
    im = Image.open(im_path)

    bin = binarization.nlbin(im, 0.5, 0.5, 1.0, 0.2, 80, 20, 5, 90)

    # segment into lines
    seg = pageseg.segment(bin, text_direction="horizontal-rl")
    line_images = extract_polygons(im, seg)
    save_segments(f"{doc_name}_bbox", save_prefix, line_images)


def save_segments(save_folder: str, save_prefix: str, images, ext: str = "png"):
    path = Path(save_folder)
    path.mkdir(parents=True, exist_ok=True)
    for i, output in enumerate(images):
        output[0].save(f"{save_folder}/{save_prefix}_{i}.{ext}")

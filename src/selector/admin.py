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

from .models import Document, LineSegment, Notebook
from .utils.symbol_conversion import convert_symbols


def segment_document(modeladmin, request, queryset):
    from kraken.lib import vgsl

    model_muharaf = vgsl.TorchVGSLModel.load_model("muharaf_seg_best.mlmodel")
    model_blla = vgsl.TorchVGSLModel.load_model("blla.mlmodel")
    for doc in queryset:
        try:
            extract_lines_muharaf(doc.file.path, "muharaf", model_muharaf)
            extract_lines_blla(doc.file.path, "blla", model_blla)
        except Exception as a:
            pass


def convert_to_unchecked(model_admin, request, queryset):
    updated = queryset.update(verification=LineSegment.VerifiedState.UNCHECKED)
    model_admin.message_user(
        request,
        _("%d line segments marked as unchecked.") % updated,
        level="info",
    )


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
    parameter_name = "verification"

    def lookups(self, request, model_admin):
        return (
            ("accepted", _("قبول")),
            ("rejected", _("رد")),
            ("unchecked", _("بررسی نشده")),
        )

    def queryset(self, request, queryset):
        val = self.value()
        if val == "accepted":
            return queryset.filter(
                id__in=[doc.pk for doc in queryset if doc.is_verified]
            )
        elif val == "rejected":
            return queryset.filter(
                id__in=[
                    doc.pk
                    for doc in queryset
                    if doc.linesegments.exists()
                    and any(
                        seg.verification == LineSegment.VerifiedState.REJECTED
                        for seg in doc.linesegments.all()
                    )
                ]
            )
        elif val == "unchecked":
            return queryset.filter(
                id__in=[
                    doc.pk
                    for doc in queryset
                    if doc.linesegments.exists()
                    and any(
                        seg.verification == LineSegment.VerifiedState.UNCHECKED
                        for seg in doc.linesegments.all()
                    )
                ]
            )
        return queryset


@admin.register(Notebook)
class NotebookAdmin(admin.ModelAdmin):
    list_display = ("name", "file")
    actions = ["convert_to_document_images", "create_output"]

    @admin.action(description=_("Export docs/Lines"))
    def create_output(self, request, queryset):
        """
        Creates/refreshes MEDIA_ROOT/output with:
        - All verified&transcribed docs and their files (copied to output/)
        - Each doc's LineSegments (copied to output/NotebookName_PageNum/)
        - output.csv listing all segments
        """
        import csv
        import shutil

        media_root = settings.MEDIA_ROOT
        output_dir = os.path.join(media_root, "output")
        # Remove existing output directory, if it exists
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
        os.makedirs(output_dir, exist_ok=True)
        csv_rows = []
        for notebook in queryset:
            docs = notebook.documents.all()
            # Only export docs that are both transcribed and verified
            docs = [d for d in docs if d.is_transcribed and d.is_verified]
            for doc in docs:
                # Copy document file to output root
                if doc.file and os.path.exists(doc.file.path):
                    dest_doc_file = os.path.join(
                        output_dir, os.path.basename(doc.file.name)
                    )
                    shutil.copy2(doc.file.path, dest_doc_file)
                # Prepare target dir for line segments
                seg_dir_name = f"{notebook.name}_{doc.page}"
                seg_dir = os.path.join(output_dir, seg_dir_name)
                os.makedirs(seg_dir, exist_ok=True)
                # For each line segment
                for seg in doc.linesegments.all():
                    if seg.file and os.path.exists(seg.file.path):
                        seg_dest_path = os.path.join(
                            seg_dir, os.path.basename(seg.file.name)
                        )
                        shutil.copy2(seg.file.path, seg_dest_path)
                        rel_path = os.path.relpath(seg_dest_path, output_dir)
                        csv_rows.append(
                            [
                                rel_path,  # 0: line_segment_path
                                notebook.name,  # 1: notebook_name
                                doc.page,  # 2: page_number
                                seg.transcription or "",  # 3: transcription
                                seg.order,  # 4: line_segment_order (for sorting, not to be exported)
                            ]
                        )
        # Sort rows by notebook_name, page_number, line_segment_order
        csv_rows.sort(key=lambda row: (str(row[1]), int(row[2]), int(row[4])))
        # Write CSV summary (exclude order from output)
        csv_path = os.path.join(output_dir, "output.csv")
        with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(
                ["line_segment_path", "notebook_name", "page_number", "transcription"]
            )
            for row in csv_rows:
                writer.writerow(row[:4])
        self.message_user(
            request,
            f"Export complete: {len(csv_rows)} line segments from {queryset.count()} notebook(s). Output in 'media/output/'.",
            level="info",
        )

    @admin.action(description=_("تبدیل به تصاویر سند"))
    def convert_to_document_images(self, request, queryset):
        pass


def sync_validated_to_remote(modeladmin, request, queryset):
    """
    Sync the validated folder for each selected document to a remote server using rsync.
    Source: MEDIA_ROOT/{document_file_basename}_validated
    Target: bol:/opt/transcription/media
    """
    import subprocess
    import os

    success_count = 0
    error_count = 0
    missing_count = 0

    for doc in queryset:
        if not doc.file:
            error_count += 1
            continue

        # Get basename without extension
        base_name = os.path.splitext(os.path.basename(doc.file.name))[0]
        folder_name = f"{base_name}_validated"
        source_path = os.path.join(settings.MEDIA_ROOT, folder_name)

        if not os.path.exists(source_path):
            missing_count += 1
            continue

        try:
            result = subprocess.run(
                ["rsync", "-avz", source_path, "bol:/opt/transcription/media"],
                capture_output=True,
                text=True,
                check=True,
            )
            success_count += 1
        except subprocess.CalledProcessError as e:
            error_count += 1

    modeladmin.message_user(
        request,
        f"Sync complete: {success_count} successful, {missing_count} missing folders, {error_count} errors.",
        level="info" if error_count == 0 else "warning",
    )


sync_validated_to_remote.short_description = _("ارسال فایل‌ها")


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    actions = [segment_document, sync_validated_to_remote]
    list_filter = [HasLinesegmentsFilter, IsTranscribedFilter, IsVerifiedFilter]

    SEGMENTER_COLS = [
        "id",
        "notebook__name",
        "page",
        "compare_link",
        "segmenter_link",
        "segments_finalize_link",
        "has_linesegments",
    ]
    TRANSCRIBER_COLS = [
        "id",
        "notebook__name",
        "page",
        "segments_link",
        "has_linesegments",
        "is_transcribed",
    ]
    VERIFIER_COLS = [
        "id",
        "notebook__name",
        "page",
        "segments_link",
        "has_linesegments",
        "is_transcribed",
        "is_verified",
    ]

    COLUMN_ORDER = [
        "id",
        "notebook__name",
        "page",
        "compare_link",
        "segments_link",
        "segmenter_link",
        "segments_finalize_link",
        "has_linesegments",
        "is_transcribed",
        "is_verified",
    ]
    list_per_page = 50

    def get_list_display(self, request):
        # Assess user roles by group name
        user = request.user
        roles = set()
        group_names = set(g.name for g in user.groups.all())
        if "segmenter" in group_names:
            roles.add("segmenter")
        if "transcriber" in group_names:
            roles.add("transcriber")
        if "verifier" in group_names:
            roles.add("verifier")
        # Union all columns for assigned roles
        cols = set()
        if "segmenter" in roles:
            cols.update(self.SEGMENTER_COLS)
        if "transcriber" in roles:
            cols.update(self.TRANSCRIBER_COLS)
        if "verifier" in roles:
            cols.update(self.VERIFIER_COLS)
        # Always show at least id and name if no group assigned
        if not cols:
            return ("id", "name")
        # Order columns deterministically (by COLUMN_ORDER)
        ordered = [x for x in self.COLUMN_ORDER if x in cols]
        return ordered

    def compare_link(self, obj):
        url = reverse(
            "segment-compare",
            args=[obj.pk],
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
        # Preserve active filters/query params if possible
        params = ""
        if hasattr(self, "_request"):
            get_dict = self._request.GET.copy()
            if get_dict:
                params = "?" + get_dict.urlencode()
        url = f"{url}{params}"
        return format_html('<a href="{}">Segment</a>', url)

    segmenter_link.short_description = "Segment"

    def get_queryset(self, request):
        # Store request for later use in segments_finalize_link
        self._request = request
        return super().get_queryset(request).select_related("notebook")

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
        "verification",
    ]
    list_filter = ["transcribed", "verification"]
    readonly_fields = [
        "image_tag",
        "last_transcribed_by",
        "last_verified_by",
        "document_image_tag",
        "transcribed",
    ]
    formfield_overrides = {
        models.TextField: {
            "widget": forms.Textarea(
                attrs={
                    "rows": 3,
                    "dir": "rtl",
                    "style": "font-size:1.3rem; resize:none;",
                    "autocomplete": "off",
                }
            )
        },
    }

    def get_ordering(self, request):
        user = request.user
        group_names = set(g.name for g in user.groups.all())
        is_verifier = "verifier" in group_names
        is_transcriber = "transcriber" in group_names
        is_segmenter = "segmenter" in group_names
        if is_verifier and not is_transcriber and not is_segmenter:
            return ["verification", "document", "order"]
        elif is_transcriber and not is_verifier and not is_segmenter:
            return ["transcribed", "document", "order"]
        else:
            return ["transcribed", "verification", "document", "order"]

    def document_image_tag(self, obj):
        if obj.document and obj.document.file:
            # Add a unique class for reliable JS/CSS targeting
            return format_html(
                '<img src="{}" class="zoomable-document-image" style="max-width:600px; max-height:300px;" />',
                obj.document.file.url,
            )
        return ""

    document_image_tag.short_description = _("تصویر سند مرتبط")
    document_image_tag.allow_tags = True

    def get_fieldsets(self, request, obj=None):
        # user = request.user
        # group_names = set(g.name for g in user.groups.all())
        # Fieldset for document image, expanded for 'verifier' group, collapsed otherwise
        default_fieldsets = (
            (
                None,
                {
                    "fields": (
                        "document",
                        "image_tag",
                        "transcription",
                        "verification",
                    ),
                },
            ),
            (
                _("تصویر سند مرتبط"),
                {
                    "classes": ("collapse",),
                    "fields": ("document_image_tag",),
                },
            ),
            (
                _("ویژگی‌های پیشرفته"),  # Advanced fields
                {
                    "classes": ("collapse",),
                    "fields": (
                        "file",
                        "order",
                        "last_transcribed_by",
                        "last_verified_by",
                    ),
                },
            ),
        )
        return default_fieldsets

    @admin.action(description=_("تبدیل نمادها (convert symbols)"))
    def convert_symbols_action(self, request, queryset):
        updated_count = 0
        for segment in queryset:
            original = segment.transcription or ""
            converted = convert_symbols(original)
            if original != converted:
                segment.transcription = converted
                segment.save(update_fields=["transcription"])
                updated_count += 1
        self.message_user(
            request,
            _("%d line segments were updated with converted symbols.") % updated_count,
            level="info",
        )

    actions = [convert_to_unchecked, "convert_symbols_action"]

    change_form_template = "admin/selector/linesegment/change_form.html"

    def save_model(self, request, obj, form, change):
        if change:
            orig = type(obj).objects.get(pk=obj.pk)
            transcription_changed = orig.transcription != obj.transcription
            verification_changed = orig.verification != obj.verification
            if transcription_changed:
                obj.last_transcribed_by = request.user
            if verification_changed:
                obj.last_verified_by = request.user
        else:
            if obj.transcription:
                obj.last_transcribed_by = request.user
            # If verification is not UNCHECKED on creation, attribute to user
            if obj.verification != obj.VerifiedState.UNCHECKED:
                obj.last_verified_by = request.user
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        # Store request GET params for use in context
        qs = super().get_queryset(request)
        self._list_filters = request.GET.urlencode()
        return qs.select_related("document")

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
            preserved = self.get_preserved_filters(request)
            if preserved and request.GET.get("_changelist_filters"):
                if not request.GET.get("_changelist_filters").startswith("p="):
                    arguments = request.GET.get("_changelist_filters").split("&")
                    arguments = [
                        dict(zip([temp.split("=")[0]], [temp.split("=")[1]]))
                        for temp in arguments
                    ]
                    filters.update({k: v for d in arguments for k, v in d.items()})
        if len(filter_args) or len(filters):
            qs = LineSegment.objects.filter(*filter_args, **filters)
        else:
            qs = LineSegment.objects.none()
        next_segment = qs.filter(transcribed=False).order_by("document","order").first()
        return next_segment

    def get_next_unverified(self, obj, request):
        """
        Returns the next unverified (UNCHECKED) LineSegment, already transcribed, filtered like current changelist (if possible).
        Orders by document_id, then order.
        """
        filters = {}
        filter_args = []
        if "document__id__exact" in request.GET:
            filters["document__id"] = request.GET["document__id__exact"]
        if hasattr(self, "get_preserved_filters"):
            preserved = self.get_preserved_filters(request)
            if preserved and request.GET.get("_changelist_filters"):
                if not request.GET.get("_changelist_filters").startswith("p="):
                    arguments = request.GET.get("_changelist_filters").split("&")
                    arguments = [
                        dict(zip([temp.split("=")[0]], [temp.split("=")[1]]))
                        for temp in arguments
                    ]
                    filters.update({k: v for d in arguments for k, v in d.items()})

        if len(filter_args) or len(filters):
            qs = LineSegment.objects.filter(*filter_args, **filters)
        else:
            qs = LineSegment.objects.none()
        next_segment = qs.filter(
            transcribed=True,
            verification=LineSegment.VerifiedState.UNCHECKED
        ).order_by("document_id", "order").first()
        return next_segment

    def has_next_untranscribed(self, obj, request):
        next_seg = self.get_next_untranscribed(obj, request)
        return next_seg is not None

    def has_next_unverified(self, obj, request):
        next_seg = self.get_next_unverified(obj, request)
        return next_seg is not None

    def render_change_form(self, request, context, *args, **kwargs):
        obj = kwargs.get("obj")
        context["has_next_untranscribed"] = (
            self.has_next_untranscribed(obj, request) if obj else False
        )
        context["has_next_unverified"] = (
            self.has_next_unverified(obj, request) if obj else False
        )
        return super().render_change_form(request, context, *args, **kwargs)

    def response_change(self, request, obj):
        if "save_and_next" in request.POST:
            # Decide next segment based on current transcribed status
            if obj.transcribed:
                next_segment = self.get_next_unverified(obj, request)
                if next_segment:
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
                        request, _("No more unverified line segments."), level="info"
                    )
                    return super().response_change(request, obj)
            else:
                next_segment = self.get_next_untranscribed(obj, request)
                if next_segment:
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


def extract_lines_muharaf(im_path, save_prefix: str, model, padding=10):
    from kraken import blla
    from PIL import Image

    from .segmentation import extract_polygons

    base_name = os.path.basename(im_path)
    base_name_wo_ext, ext = os.path.splitext(base_name)
    ext = ext.lstrip(".")
    # load page image
    im = Image.open(im_path)

    # segment into lines
    seg = blla.segment(im, text_direction="horizontal-rl", model=[model], device="cuda")

    # each region corresponds to a line bounding box
    line_images = extract_polygons(im, seg, pad=padding)
    save_segments(
        join(settings.MEDIA_ROOT, f"{base_name_wo_ext}_muharaf"),
        save_prefix,
        line_images,
        ext=ext,
    )


def extract_lines_blla(im_path, save_prefix: str, model, padding=10):
    from kraken import blla
    from PIL import Image

    from .segmentation import extract_polygons

    base_name = os.path.basename(im_path)
    base_name_wo_ext, ext = os.path.splitext(base_name)
    ext = ext.lstrip(".")
    # load page image
    im = Image.open(im_path)

    # segment into lines
    seg = blla.segment(im, text_direction="horizontal-rl", model=[model], device="cuda")

    # each region corresponds to a line bounding box
    line_images = extract_polygons(im, seg, pad=padding)
    save_segments(
        join(settings.MEDIA_ROOT, f"{base_name_wo_ext}_blla"),
        save_prefix,
        line_images,
        ext=ext,
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

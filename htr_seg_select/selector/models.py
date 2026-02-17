from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from django.utils.translation import gettext_lazy as _

class Notebook(models.Model):
    name = models.CharField(max_length=250, verbose_name=_("نام"))
    file = models.FileField(null=True, verbose_name=_("فایل"))

    class Meta:
        verbose_name = _("جزوه")
        verbose_name_plural = _("جزوات")

    def __str__(self):
        return self.name

class Document(models.Model):
    # A single image of a page
    file = models.FileField(null=True, verbose_name=_("فایل"))
    notebook = models.ForeignKey(
        Notebook,
        on_delete=models.SET_NULL,
        null=True,
        related_name="documents",
    )
    page = models.IntegerField(null=True, verbose_name=_("شماره صفحه"))

    class Meta:
        verbose_name = _("سند")
        verbose_name_plural = _("اسناد")

    def __str__(self) -> str:
        return f"{self.notebook.name} p{self.page}" or f"Document ({self.pk})"

    @property
    def is_transcribed(self) -> bool:
        segments = self.linesegments.all()
        return segments.exists() and all(segment.transcribed for segment in segments)

    @property
    def is_verified(self) -> bool:
        segments = self.linesegments.all()
        return segments.exists() and all(
            segment.verification == LineSegment.VerifiedState.ACCEPTED
            for segment in segments
        )

    @property
    def has_linesegments(self) -> bool:
        return self.linesegments.exists()

class LineSegment(models.Model):
    file = models.FileField(verbose_name=_("فایل"))
    order = models.IntegerField(verbose_name=_("ترتیب"))
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="linesegments",
        verbose_name=_("سند"),
    )
    transcription = models.TextField(blank=True, verbose_name=_("رونوشت"))
    transcribed = models.BooleanField(default=False, verbose_name=_("رونوشت شده"))

    class VerifiedState(models.IntegerChoices):
        UNCHECKED = 0, _("بررسی نشده")
        ACCEPTED = 1, _("قبول")
        REJECTED = 2, _("رد")

    verification = models.SmallIntegerField(
        choices=VerifiedState.choices,
        default=VerifiedState.UNCHECKED,
        verbose_name=_("تایید شده"),
    )

    last_transcribed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="transcribed_segments",
        verbose_name=_("آخرین رونوشت‌کننده"),
    )
    last_verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="verified_segments",
        verbose_name=_("آخرین بازبین"),
    )

    class Meta:
        verbose_name = _("تکه خط")
        verbose_name_plural = _("تکه‌های خط")

    def save(self, *args, **kwargs):
        # Set transcribed to True if transcription is non-empty, else False
        self.transcribed = bool(self.transcription and self.transcription.strip())
        super().save(*args, **kwargs)


# @receiver(post_save, sender="selector.Document")
# def sync_name_with_file(sender, instance, created, **kwargs):
#     import os

#     if instance.file:
#         base_name = os.path.splitext(os.path.basename(instance.file.name))[0]
#         if instance.name != base_name:
#             instance.name = base_name
#             instance.save(update_fields=["name"])
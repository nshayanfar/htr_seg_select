from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class Document(models.Model):
    # A single image of a page
    name = models.CharField(max_length=250, blank=True)
    file = models.FileField(null=True)

class LineSegment(models.Model):
    file = models.FileField()
    order = models.IntegerField()
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="linesegments")
    transcription = models.TextField(blank=True)
    transcribed = models.BooleanField(default=False)
    verified = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        # Set transcribed to True if transcription is non-empty, else False
        self.transcribed = bool(self.transcription and self.transcription.strip())
        super().save(*args, **kwargs)


@receiver(post_save, sender="selector.Document")
def sync_name_with_file(sender, instance, created, **kwargs):
    import os

    if instance.file:
        base_name = os.path.splitext(os.path.basename(instance.file.name))[0]
        if instance.name != base_name:
            instance.name = base_name
            instance.save(update_fields=["name"])

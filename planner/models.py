from django.db import models


class SiteText(models.Model):
    """Admin-editable text snippet shown on student-facing pages.

    Snippets are looked up by ``key`` (e.g. ``checker_subtitle``).
    """

    KEY_LABELS = {
        'checker_subtitle': 'Checker page subtitle',
    }

    key = models.SlugField(max_length=64, unique=True)
    content = models.TextField(blank=True)

    class Meta:
        ordering = ['key']
        verbose_name = 'site text'
        verbose_name_plural = 'site texts'

    def __str__(self) -> str:
        return self.key

    @property
    def label(self) -> str:
        """Human-friendly name shown in the manage dashboard."""
        return self.KEY_LABELS.get(self.key, self.key)

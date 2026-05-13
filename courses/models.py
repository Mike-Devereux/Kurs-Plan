from django.db import models


class CourseCategory(models.Model):
    name = models.CharField(max_length=255, unique=True)
    display_order = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['display_order', 'name']
        verbose_name = 'course category'
        verbose_name_plural = 'course categories'

    def __str__(self) -> str:
        return self.name


class Module(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self) -> str:
        return self.name

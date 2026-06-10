from django.db import models


class CourseCategory(models.Model):
    name = models.CharField(max_length=255, unique=True)
    display_order = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['display_order', 'name']
        verbose_name = 'course category'
        verbose_name_plural = 'course categories'
        constraints = [
            models.UniqueConstraint(
                fields=['display_order'],
                name='unique_course_category_display_order',
            ),
        ]

    def __str__(self) -> str:
        return self.name

    @classmethod
    def lowest_unused_display_order(cls) -> int:
        """Smallest non-negative integer not used as a category display order."""
        used = set(cls.objects.values_list('display_order', flat=True))
        order = 0
        while order in used:
            order += 1
        return order


class Module(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class Course(models.Model):
    code = models.CharField(max_length=32, unique=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    credit_points = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name='credit points',
    )
    category = models.ForeignKey(
        CourseCategory,
        on_delete=models.PROTECT,
        related_name='courses',
    )
    modules = models.ManyToManyField(
        Module,
        related_name='courses',
        blank=True,
    )
    active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['code']

    def __str__(self) -> str:
        return f'{self.code} - {self.title}'

from django.db import models


class Specialization(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class SpecializationModuleRequirement(models.Model):
    specialization = models.ForeignKey(
        Specialization,
        on_delete=models.CASCADE,
        related_name='module_requirements',
    )
    module = models.ForeignKey(
        'courses.Module',
        on_delete=models.PROTECT,
        related_name='specialization_requirements',
    )
    required_credit_points = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name='required credit points',
    )
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['specialization', 'display_order', 'module']
        constraints = [
            models.UniqueConstraint(
                fields=['specialization', 'module'],
                name='unique_specialization_module',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.specialization} / {self.module}: {self.required_credit_points} CP'


class AdditionalRequirementRuleType(models.TextChoices):
    MINIMUM_CREDITS_ACROSS_MODULES = (
        'minimum_credits_across_modules',
        'Minimum credits across modules',
    )


class AdditionalRequirementRule(models.Model):
    specialization = models.ForeignKey(
        Specialization,
        on_delete=models.CASCADE,
        related_name='additional_requirement_rules',
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    rule_type = models.CharField(
        max_length=64,
        choices=AdditionalRequirementRuleType.choices,
    )
    required_credit_points = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name='required credit points',
    )
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['specialization', 'name']

    def __str__(self) -> str:
        return f'{self.specialization}: {self.name} ({self.get_rule_type_display()})'

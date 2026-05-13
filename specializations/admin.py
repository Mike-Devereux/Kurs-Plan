from django.contrib import admin

from .models import (
    AdditionalRequirementRule,
    Specialization,
    SpecializationModuleRequirement,
)


class SpecializationModuleRequirementInline(admin.TabularInline):
    model = SpecializationModuleRequirement
    extra = 0
    autocomplete_fields = ('module',)
    fields = ('module', 'required_credit_points', 'display_order')
    ordering = ('display_order', 'module')


class AdditionalRequirementRuleInline(admin.StackedInline):
    model = AdditionalRequirementRule
    extra = 0
    filter_horizontal = ('modules_included',)
    fields = (
        'name',
        'rule_type',
        'required_credit_points',
        'modules_included',
        'description',
        'active',
    )


@admin.register(Specialization)
class SpecializationAdmin(admin.ModelAdmin):
    list_display = ('name', 'active', 'module_requirement_count', 'rule_count')
    list_filter = ('active',)
    search_fields = ('name', 'description')
    ordering = ('name',)
    inlines = (
        SpecializationModuleRequirementInline,
        AdditionalRequirementRuleInline,
    )

    @admin.display(description='module requirements')
    def module_requirement_count(self, obj: Specialization) -> int:
        return obj.module_requirements.count()

    @admin.display(description='additional rules')
    def rule_count(self, obj: Specialization) -> int:
        return obj.additional_requirement_rules.count()


@admin.register(SpecializationModuleRequirement)
class SpecializationModuleRequirementAdmin(admin.ModelAdmin):
    list_display = (
        'specialization',
        'module',
        'required_credit_points',
        'display_order',
    )
    list_filter = ('specialization', 'module')
    search_fields = ('specialization__name', 'module__name')
    ordering = ('specialization', 'display_order', 'module')
    autocomplete_fields = ('specialization', 'module')
    list_select_related = ('specialization', 'module')


@admin.register(AdditionalRequirementRule)
class AdditionalRequirementRuleAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'specialization',
        'rule_type',
        'required_credit_points',
        'active',
    )
    list_filter = ('active', 'rule_type', 'specialization')
    search_fields = ('name', 'description', 'specialization__name')
    ordering = ('specialization', 'name')
    autocomplete_fields = ('specialization',)
    filter_horizontal = ('modules_included',)
    list_select_related = ('specialization',)
    fieldsets = (
        (None, {
            'fields': ('specialization', 'name', 'description', 'active'),
        }),
        ('Rule definition', {
            'fields': (
                'rule_type',
                'required_credit_points',
                'modules_included',
            ),
        }),
    )

from django import forms
from django.forms.models import BaseInlineFormSet, inlineformset_factory

from courses.models import Course, CourseCategory, Module
from specializations.models import (
    AdditionalRequirementRule,
    Specialization,
    SpecializationModuleRequirement,
)


class CourseCategoryForm(forms.ModelForm):
    class Meta:
        model = CourseCategory
        fields = ['name', 'display_order', 'active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk and not self.data:
            self.initial.setdefault(
                'display_order',
                CourseCategory.lowest_unused_display_order(),
            )

    def clean_display_order(self):
        display_order = self.cleaned_data['display_order']
        qs = CourseCategory.objects.filter(display_order=display_order)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('This display order is already in use.')
        return display_order


class ModuleForm(forms.ModelForm):
    class Meta:
        model = Module
        fields = ['name', 'description', 'active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = [
            'code',
            'title',
            'description',
            'credit_points',
            'category',
            'modules',
            'notes',
            'active',
        ]
        widgets = {
            'modules': forms.CheckboxSelectMultiple(),
            'description': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_modules(self):
        modules = self.cleaned_data.get('modules')
        if not modules:
            raise forms.ValidationError('Select at least one module.')
        return modules


class SpecializationForm(forms.ModelForm):
    class Meta:
        model = Specialization
        fields = ['name', 'description', 'active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }


SpecializationModuleRequirementFormSet = inlineformset_factory(
    Specialization,
    SpecializationModuleRequirement,
    fields=['module', 'required_credit_points', 'display_order'],
    extra=1,
    can_delete=True,
)
# Duplicate ``module`` across rows is caught by the formset's built-in
# unique-check, which reads the model's ``UniqueConstraint(['specialization',
# 'module'])`` — no custom ``clean()`` is needed.


class BaseAdditionalRuleFormSet(BaseInlineFormSet):
    """Ensure each active rule has at least one module in modules_included.

    Today the only rule type aggregates across modules; structuring the check
    around ``rule_type`` keeps it easy to relax later for rule types that do
    not need modules.
    """

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        for form in self.forms:
            data = getattr(form, 'cleaned_data', None)
            if not data or data.get('DELETE'):
                continue
            rule_type = data.get('rule_type')
            modules = data.get('modules_included')
            if rule_type and not modules:
                form.add_error(
                    'modules_included',
                    'Select at least one module for this rule.',
                )


AdditionalRequirementRuleFormSet = inlineformset_factory(
    Specialization,
    AdditionalRequirementRule,
    formset=BaseAdditionalRuleFormSet,
    fields=[
        'name',
        'description',
        'rule_type',
        'required_credit_points',
        'modules_included',
        'active',
    ],
    extra=1,
    can_delete=True,
    widgets={
        'description': forms.Textarea(attrs={'rows': 2}),
        'modules_included': forms.CheckboxSelectMultiple(),
    },
)

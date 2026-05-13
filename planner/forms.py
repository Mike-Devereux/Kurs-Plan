from __future__ import annotations

from django import forms

from courses.models import Course
from specializations.models import Specialization


class StudentCheckerForm(forms.Form):
    """Specialization + selected courses chosen by an anonymous student."""

    specialization = forms.ModelChoiceField(
        queryset=Specialization.objects.none(),
        empty_label='Choose a specialization…',
        label='Specialization',
    )
    # The catalog is rendered manually in the template (grouped by category),
    # so we don't need a Django-rendered widget. We keep the field only for
    # validation: every posted ID must be in the active-courses queryset.
    # ``required=False`` so our own ``clean_courses`` controls the empty-
    # selection message instead of Django's generic "This field is required."
    courses = forms.ModelMultipleChoiceField(
        queryset=Course.objects.none(),
        required=False,
        label='Selected courses',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['specialization'].queryset = (
            Specialization.objects.filter(active=True).order_by('name')
        )
        self.fields['courses'].queryset = (
            Course.objects.filter(active=True)
            .select_related('category')
            .order_by('category__display_order', 'category__name', 'code')
        )

    def clean_courses(self):
        courses = self.cleaned_data.get('courses')
        if not courses:
            raise forms.ValidationError('Select at least one course.')
        return courses

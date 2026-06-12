from __future__ import annotations

from collections import OrderedDict

from django.templatetags.static import static
from django.views.generic import FormView

from courses.models import Course, CourseCategory

from .forms import StudentCheckerForm
from .models import SiteText
from .services import evaluate_selection

CHECKER_SUBTITLE_KEY = 'checker_subtitle'


class CheckerView(FormView):
    """Single-page student workflow: choose a specialization, tick courses,
    submit, and see the result on the same URL.

    The page renders identically for GET and POST; the only difference is
    that a successful POST adds a ``result`` to the context.
    """

    template_name = 'planner/checker.html'
    form_class = StudentCheckerForm

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['categories_with_courses'] = self._categories_with_courses()
        selected_ids = self._selected_ids_from_request()
        ctx['selected_course_ids'] = selected_ids
        ctx['webtool_banner_logo_right'] = static(
            'webtool_template/logos/DepChe_Logo_DE_Schwarz_RGB.png'
        )
        ctx['subtitle'] = (
            SiteText.objects.filter(key=CHECKER_SUBTITLE_KEY)
            .values_list('content', flat=True)
            .first()
        )
        return ctx

    def form_valid(self, form):
        result = evaluate_selection(
            specialization=form.cleaned_data['specialization'],
            courses=form.cleaned_data['courses'],
        )
        return self.render_to_response(
            self.get_context_data(form=form, result=result)
        )

    def _categories_with_courses(self):
        """Return an ordered mapping of category -> list[Course].

        Only active categories and active courses are included; categories
        that end up with zero courses are omitted so the student doesn't
        see empty panels.
        """
        courses = (
            Course.objects.filter(active=True, category__active=True)
            .select_related('category')
            .order_by('category__display_order', 'category__name', 'code')
        )
        grouped: 'OrderedDict[CourseCategory, list[Course]]' = OrderedDict()
        for course in courses:
            grouped.setdefault(course.category, []).append(course)
        return grouped

    def _selected_ids_from_request(self) -> set[int]:
        """IDs the student had ticked when submitting (used to re-check
        boxes after a re-render). Empty on initial GET."""
        raw = self.request.POST.getlist('courses') if self.request.method == 'POST' else []
        ids: set[int] = set()
        for value in raw:
            try:
                ids.add(int(value))
            except (TypeError, ValueError):
                continue
        return ids

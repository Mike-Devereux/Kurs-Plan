from django.db import transaction
from django.db.models import Count
from django.shortcuts import redirect
from django.views.generic import (
    CreateView,
    DeleteView,
    TemplateView,
    UpdateView,
)

from courses.models import Course, CourseCategory, Module
from specializations.models import Specialization

from .forms import (
    AdditionalRequirementRuleFormSet,
    CourseCategoryForm,
    CourseForm,
    ModuleForm,
    SpecializationForm,
    SpecializationModuleRequirementFormSet,
)
from .mixins import (
    ModalContextMixin,
    ModalDeleteMixin,
    ModalFormMixin,
    StaffRequiredMixin,
    is_htmx,
)


class DashboardView(StaffRequiredMixin, TemplateView):
    template_name = 'manage/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = CourseCategory.objects.all()
        context['modules'] = Module.objects.all()
        context['courses'] = Course.objects.select_related('category').all()
        context['specializations'] = Specialization.objects.annotate(
            requirement_count=Count('module_requirements', distinct=True),
            rule_count=Count('additional_requirement_rules', distinct=True),
        )
        return context


# --- Course categories -------------------------------------------------------


class _CategoryListMixin:
    list_box_id = 'box-categories'
    list_template_name = 'manage/partials/list_categories.html'

    def get_list_queryset(self):
        return CourseCategory.objects.all()


class CategoryCreateView(
    StaffRequiredMixin, _CategoryListMixin, ModalFormMixin, CreateView,
):
    model = CourseCategory
    form_class = CourseCategoryForm
    fragment_template_name = 'manage/partials/category_form.html'
    page_title = 'Add course category'


class CategoryUpdateView(
    StaffRequiredMixin, _CategoryListMixin, ModalFormMixin, UpdateView,
):
    model = CourseCategory
    form_class = CourseCategoryForm
    fragment_template_name = 'manage/partials/category_form.html'
    page_title = 'Edit course category'


class CategoryDeleteView(
    StaffRequiredMixin, _CategoryListMixin, ModalDeleteMixin, DeleteView,
):
    model = CourseCategory
    fragment_template_name = 'manage/partials/confirm_delete.html'
    page_title = 'Delete course category'


# --- Modules -----------------------------------------------------------------


class _ModuleListMixin:
    list_box_id = 'box-modules'
    list_template_name = 'manage/partials/list_modules.html'

    def get_list_queryset(self):
        return Module.objects.all()


class ModuleCreateView(
    StaffRequiredMixin, _ModuleListMixin, ModalFormMixin, CreateView,
):
    model = Module
    form_class = ModuleForm
    fragment_template_name = 'manage/partials/module_form.html'
    page_title = 'Add module'


class ModuleUpdateView(
    StaffRequiredMixin, _ModuleListMixin, ModalFormMixin, UpdateView,
):
    model = Module
    form_class = ModuleForm
    fragment_template_name = 'manage/partials/module_form.html'
    page_title = 'Edit module'


class ModuleDeleteView(
    StaffRequiredMixin, _ModuleListMixin, ModalDeleteMixin, DeleteView,
):
    model = Module
    fragment_template_name = 'manage/partials/confirm_delete.html'
    page_title = 'Delete module'


# --- Courses -----------------------------------------------------------------


class _CourseListMixin:
    list_box_id = 'box-courses'
    list_template_name = 'manage/partials/list_courses.html'

    def get_list_queryset(self):
        return Course.objects.select_related('category').all()


class CourseCreateView(
    StaffRequiredMixin, _CourseListMixin, ModalFormMixin, CreateView,
):
    model = Course
    form_class = CourseForm
    fragment_template_name = 'manage/partials/course_form.html'
    page_title = 'Add course'


class CourseUpdateView(
    StaffRequiredMixin, _CourseListMixin, ModalFormMixin, UpdateView,
):
    model = Course
    form_class = CourseForm
    fragment_template_name = 'manage/partials/course_form.html'
    page_title = 'Edit course'


class CourseDeleteView(
    StaffRequiredMixin, _CourseListMixin, ModalDeleteMixin, DeleteView,
):
    model = Course
    fragment_template_name = 'manage/partials/confirm_delete.html'
    page_title = 'Delete course'


# --- Specializations --------------------------------------------------------


class _SpecializationListMixin:
    list_box_id = 'box-specializations'
    list_template_name = 'manage/partials/list_specializations.html'

    def get_list_queryset(self):
        return Specialization.objects.annotate(
            requirement_count=Count('module_requirements', distinct=True),
            rule_count=Count('additional_requirement_rules', distinct=True),
        )


class SpecializationFormViewMixin:
    """Save the parent ``Specialization`` together with its two inline
    formsets (``SpecializationModuleRequirement`` and
    ``AdditionalRequirementRule``) in a single transaction.
    """

    def _build_formsets(self, instance, data=None):
        requirements = SpecializationModuleRequirementFormSet(
            data,
            instance=instance,
            prefix='requirements',
        )
        rules = AdditionalRequirementRuleFormSet(
            data,
            instance=instance,
            prefix='rules',
        )
        return requirements, rules

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if 'requirement_formset' not in ctx:
            req_fs, rule_fs = self._build_formsets(self.object)
            ctx['requirement_formset'] = req_fs
            ctx.setdefault('rule_formset', rule_fs)
        elif 'rule_formset' not in ctx:
            _, rule_fs = self._build_formsets(self.object)
            ctx['rule_formset'] = rule_fs
        return ctx

    def post(self, request, *args, **kwargs):
        self.object = self._get_post_object()
        form = self.get_form()
        req_fs, rule_fs = self._build_formsets(self.object, data=request.POST)

        # Use bitwise & so all three .is_valid() calls run (each populates
        # its own .errors); a Python ``and`` would short-circuit.
        all_valid = (
            bool(form.is_valid())
            & bool(req_fs.is_valid())
            & bool(rule_fs.is_valid())
        )
        if all_valid:
            return self._forms_valid(form, req_fs, rule_fs)
        return self._forms_invalid(form, req_fs, rule_fs)

    def _get_post_object(self):
        raise NotImplementedError

    @transaction.atomic
    def _forms_valid(self, form, requirement_formset, rule_formset):
        self.object = form.save()
        requirement_formset.instance = self.object
        requirement_formset.save()
        rule_formset.instance = self.object
        rule_formset.save()
        if is_htmx(self.request):
            return self.refresh_response()
        return redirect('manage:dashboard')

    def _forms_invalid(self, form, requirement_formset, rule_formset):
        context = self.get_context_data(
            form=form,
            requirement_formset=requirement_formset,
            rule_formset=rule_formset,
        )
        return self.render_to_response(context)


class SpecializationCreateView(
    StaffRequiredMixin,
    _SpecializationListMixin,
    SpecializationFormViewMixin,
    ModalContextMixin,
    CreateView,
):
    model = Specialization
    form_class = SpecializationForm
    fragment_template_name = 'manage/partials/specialization_form.html'
    page_title = 'Add specialization'

    def _get_post_object(self):
        return None


class SpecializationUpdateView(
    StaffRequiredMixin,
    _SpecializationListMixin,
    SpecializationFormViewMixin,
    ModalContextMixin,
    UpdateView,
):
    model = Specialization
    form_class = SpecializationForm
    fragment_template_name = 'manage/partials/specialization_form.html'
    page_title = 'Edit specialization'

    def _get_post_object(self):
        return self.get_object()


class SpecializationDeleteView(
    StaffRequiredMixin,
    _SpecializationListMixin,
    ModalDeleteMixin,
    DeleteView,
):
    model = Specialization
    fragment_template_name = 'manage/partials/confirm_delete.html'
    page_title = 'Delete specialization'

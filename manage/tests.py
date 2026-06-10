from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from courses.models import Course, CourseCategory, Module
from specializations.models import (
    AdditionalRequirementRule,
    AdditionalRequirementRuleType,
    Specialization,
    SpecializationModuleRequirement,
)


def staff_user(username='staff'):
    user = User.objects.create_user(username, password='x', is_staff=True)
    return user


class BulkDeleteTests(TestCase):
    def setUp(self):
        self.client.force_login(staff_user())

    def test_dashboard_lists_include_bulk_checkboxes(self):
        response = self.client.get(reverse('manage:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-bulk-item', count=0)
        CourseCategory.objects.create(name='Cat', display_order=0)
        Module.objects.create(name='Mod')
        response = self.client.get(reverse('manage:dashboard'))
        self.assertContains(response, 'data-bulk-select-all')
        self.assertContains(response, 'data-bulk-delete')
        self.assertContains(response, 'name="ids"')
        self.assertContains(response, 'id="box-categories-bulk-form"')
        self.assertContains(response, 'data-bulk-select-all')
        self.assertContains(response, 'onchange="applyBulkSelectAll(this)"')
        self.assertContains(response, 'type="submit"')

    def test_bulk_delete_categories(self):
        c1 = CourseCategory.objects.create(name='C1', display_order=0)
        c2 = CourseCategory.objects.create(name='C2', display_order=1)
        response = self.client.post(
            reverse('manage:category_bulk_delete'),
            {'ids': [str(c1.pk), str(c2.pk)]},
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="box-categories-list"')
        self.assertFalse(CourseCategory.objects.filter(pk__in=[c1.pk, c2.pk]).exists())

    def test_bulk_delete_skips_protected_and_reports_modal(self):
        cat = CourseCategory.objects.create(name='InUse', display_order=0)
        orphan = CourseCategory.objects.create(name='Orphan', display_order=1)
        module = Module.objects.create(name='M')
        course = Course.objects.create(
            code='X1', title='X', credit_points=Decimal('3'),
            category=cat,
        )
        course.modules.add(module)

        response = self.client.post(
            reverse('manage:category_bulk_delete'),
            {'ids': [str(cat.pk), str(orphan.pk)]},
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="modal"')
        self.assertContains(response, 'could not be deleted')
        self.assertTrue(CourseCategory.objects.filter(pk=cat.pk).exists())
        self.assertFalse(CourseCategory.objects.filter(pk=orphan.pk).exists())

    def test_bulk_delete_courses(self):
        cat = CourseCategory.objects.create(name='Cat', display_order=0)
        mod = Module.objects.create(name='M')
        c1 = Course.objects.create(
            code='A1', title='A', credit_points=Decimal('3'), category=cat,
        )
        c2 = Course.objects.create(
            code='B1', title='B', credit_points=Decimal('3'), category=cat,
        )
        c1.modules.add(mod)
        c2.modules.add(mod)

        response = self.client.post(
            reverse('manage:course_bulk_delete'),
            {'ids': [str(c1.pk), str(c2.pk)]},
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Course.objects.filter(pk__in=[c1.pk, c2.pk]).exists())

    def test_bulk_delete_specializations_cascades(self):
        mod = Module.objects.create(name='M')
        s1 = Specialization.objects.create(name='S1')
        s2 = Specialization.objects.create(name='S2')
        SpecializationModuleRequirement.objects.create(
            specialization=s1, module=mod, required_credit_points=Decimal('3'),
        )

        response = self.client.post(
            reverse('manage:specialization_bulk_delete'),
            {'ids': [str(s1.pk), str(s2.pk)]},
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Specialization.objects.filter(pk__in=[s1.pk, s2.pk]).exists())
        self.assertTrue(Module.objects.filter(pk=mod.pk).exists())


class AccessControlTests(TestCase):
    def test_dashboard_redirects_anonymous_to_login(self):
        response = self.client.get(reverse('manage:dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/manage/login/', response['Location'])

    def test_dashboard_403_for_non_staff(self):
        user = User.objects.create_user('user', password='x')
        self.client.force_login(user)
        response = self.client.get(reverse('manage:dashboard'))
        self.assertEqual(response.status_code, 403)

    def test_dashboard_200_for_staff(self):
        self.client.force_login(staff_user())
        response = self.client.get(reverse('manage:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dashboard')


class CategoryCRUDTests(TestCase):
    def setUp(self):
        self.client.force_login(staff_user())

    def test_get_add_form_as_fragment(self):
        response = self.client.get(
            reverse('manage:category_add'),
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'modal__card')
        self.assertContains(response, 'Add course category')
        self.assertNotContains(response, '<html')

    def test_add_form_suggests_lowest_unused_display_order(self):
        CourseCategory.objects.create(name='A', display_order=0)
        CourseCategory.objects.create(name='B', display_order=2)
        response = self.client.get(
            reverse('manage:category_add'),
            HTTP_HX_REQUEST='true',
        )
        self.assertContains(
            response,
            'name="display_order" value="1"',
        )

    def test_add_form_suggests_zero_when_no_categories_exist(self):
        response = self.client.get(
            reverse('manage:category_add'),
            HTTP_HX_REQUEST='true',
        )
        self.assertContains(
            response,
            'name="display_order" value="0"',
        )

    def test_post_duplicate_display_order_is_rejected(self):
        CourseCategory.objects.create(name='Existing', display_order=5)
        response = self.client.post(
            reverse('manage:category_add'),
            {'name': 'New Cat', 'display_order': 5, 'active': 'on'},
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already in use')
        self.assertFalse(CourseCategory.objects.filter(name='New Cat').exists())

    def test_get_add_form_as_full_page_without_htmx(self):
        response = self.client.get(reverse('manage:category_add'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<html')
        self.assertContains(response, 'Add course category')
        self.assertContains(response, 'Back to dashboard')

    def test_post_valid_creates_and_returns_oob_refresh(self):
        response = self.client.post(
            reverse('manage:category_add'),
            {'name': 'New Cat', 'display_order': 7, 'active': 'on'},
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="modal"')
        self.assertContains(response, 'id="box-categories-list"')
        self.assertContains(response, 'hx-swap-oob="innerHTML"')
        self.assertContains(response, 'hx-swap-oob="true"')
        self.assertContains(response, 'New Cat')
        self.assertTrue(CourseCategory.objects.filter(name='New Cat').exists())

    def test_post_invalid_redisplays_form_with_errors(self):
        response = self.client.post(
            reverse('manage:category_add'),
            {'name': '', 'display_order': 7},
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'modal__card')
        self.assertNotContains(response, 'hx-swap-oob')
        self.assertFalse(CourseCategory.objects.exists())

    def test_post_valid_without_htmx_redirects_to_dashboard(self):
        response = self.client.post(
            reverse('manage:category_add'),
            {'name': 'No JS', 'display_order': 1, 'active': 'on'},
        )
        self.assertRedirects(response, reverse('manage:dashboard'))
        self.assertTrue(CourseCategory.objects.filter(name='No JS').exists())

    def test_edit_updates_existing(self):
        cat = CourseCategory.objects.create(name='Old', display_order=1)
        response = self.client.post(
            reverse('manage:category_edit', args=[cat.pk]),
            {'name': 'Renamed', 'display_order': 9, 'active': 'on'},
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        cat.refresh_from_db()
        self.assertEqual(cat.name, 'Renamed')
        self.assertEqual(cat.display_order, 9)

    def test_delete_unused_removes_and_refreshes_list(self):
        cat = CourseCategory.objects.create(name='Doomed')
        response = self.client.post(
            reverse('manage:category_delete', args=[cat.pk]),
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="box-categories-list"')
        self.assertFalse(CourseCategory.objects.filter(pk=cat.pk).exists())

    def test_delete_protected_shows_friendly_error(self):
        cat = CourseCategory.objects.create(name='InUse')
        module = Module.objects.create(name='M')
        course = Course.objects.create(
            code='X1', title='X', credit_points=Decimal('3'),
            category=cat,
        )
        course.modules.add(module)

        response = self.client.post(
            reverse('manage:category_delete', args=[cat.pk]),
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Cannot delete')
        self.assertContains(response, 'X1')
        # Original category must still exist; response is the modal form,
        # not an OOB refresh, because the delete did not succeed.
        self.assertTrue(CourseCategory.objects.filter(pk=cat.pk).exists())
        self.assertNotContains(response, 'hx-swap-oob')


class ModuleCRUDTests(TestCase):
    def setUp(self):
        self.client.force_login(staff_user())

    def test_get_add_form_as_fragment(self):
        response = self.client.get(
            reverse('manage:module_add'),
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'modal__card')
        self.assertContains(response, 'Add module')
        self.assertNotContains(response, '<html')

    def test_post_invalid_redisplays_form_with_errors(self):
        response = self.client.post(
            reverse('manage:module_add'),
            {'name': '', 'description': '', 'active': 'on'},
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'modal__card')
        self.assertNotContains(response, 'hx-swap-oob')
        self.assertFalse(Module.objects.exists())

    def test_post_valid_creates(self):
        response = self.client.post(
            reverse('manage:module_add'),
            {'name': 'New Module', 'description': 'desc', 'active': 'on'},
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="box-modules-list"')
        self.assertTrue(Module.objects.filter(name='New Module').exists())

    def test_delete_protected_by_specialization_requirement(self):
        from specializations.models import (
            Specialization,
            SpecializationModuleRequirement,
        )

        module = Module.objects.create(name='Linked')
        spec = Specialization.objects.create(name='S')
        SpecializationModuleRequirement.objects.create(
            specialization=spec,
            module=module,
            required_credit_points=Decimal('3.00'),
        )

        response = self.client.post(
            reverse('manage:module_delete', args=[module.pk]),
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Cannot delete')
        self.assertTrue(Module.objects.filter(pk=module.pk).exists())

    def test_delete_unused_removes_and_refreshes_list(self):
        module = Module.objects.create(name='Orphan')
        response = self.client.post(
            reverse('manage:module_delete', args=[module.pk]),
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="box-modules-list"')
        self.assertFalse(Module.objects.filter(pk=module.pk).exists())


class CourseSortTests(TestCase):
    def setUp(self):
        self.client.force_login(staff_user())
        self.cat_a = CourseCategory.objects.create(name='Alpha', display_order=0)
        self.cat_z = CourseCategory.objects.create(name='Zulu', display_order=1)
        self.mod = Module.objects.create(name='M')
        self.course_b = Course.objects.create(
            code='B-100', title='Bravo', credit_points=Decimal('6.00'),
            category=self.cat_z,
        )
        self.course_a = Course.objects.create(
            code='A-100', title='Alpha', credit_points=Decimal('3.00'),
            category=self.cat_a,
        )
        self.course_b.modules.add(self.mod)
        self.course_a.modules.add(self.mod)

    def _course_codes_in_response(self, response):
        content = response.content.decode()
        pos_b = content.find('B-100')
        pos_a = content.find('A-100')
        self.assertGreater(pos_b, -1)
        self.assertGreater(pos_a, -1)
        return pos_a, pos_b

    def test_dashboard_lists_course_modules(self):
        mod2 = Module.objects.create(name='Zeta')
        self.course_a.modules.add(mod2)
        response = self.client.get(reverse('manage:dashboard'))
        self.assertContains(response, '<th>Modules</th>')
        row_a = response.content.decode().split('A-100', 1)[1].split('</tr>', 1)[0]
        self.assertIn('M', row_a)
        self.assertIn('Zeta', row_a)
        self.assertLess(row_a.index('M'), row_a.index('Zeta'))

    def test_dashboard_sorts_courses_by_code_asc_by_default(self):
        response = self.client.get(reverse('manage:dashboard'))
        pos_a, pos_b = self._course_codes_in_response(response)
        self.assertLess(pos_a, pos_b)

    def test_dashboard_sorts_courses_by_title_desc(self):
        response = self.client.get(
            reverse('manage:dashboard'),
            {'course_sort': 'title', 'course_dir': 'desc'},
        )
        pos_a, pos_b = self._course_codes_in_response(response)
        self.assertLess(pos_b, pos_a)

    def test_dashboard_sorts_courses_by_category(self):
        response = self.client.get(
            reverse('manage:dashboard'),
            {'course_sort': 'category', 'course_dir': 'asc'},
        )
        pos_a, pos_b = self._course_codes_in_response(response)
        self.assertLess(pos_a, pos_b)

    def test_dashboard_sorts_courses_by_credit_points(self):
        response = self.client.get(
            reverse('manage:dashboard'),
            {'course_sort': 'credit_points', 'course_dir': 'asc'},
        )
        pos_a, pos_b = self._course_codes_in_response(response)
        self.assertLess(pos_a, pos_b)

    def test_sort_persists_in_session_after_course_create_refresh(self):
        self.client.get(
            reverse('manage:dashboard'),
            {'course_sort': 'title', 'course_dir': 'desc'},
        )
        response = self.client.post(
            reverse('manage:course_add'),
            {
                'code': 'C-100', 'title': 'Charlie', 'description': '',
                'credit_points': '1.00', 'category': self.cat_a.pk,
                'modules': [self.mod.pk], 'notes': '', 'active': 'on',
            },
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        pos_c = content.find('C-100')
        pos_b = content.find('B-100')
        pos_a = content.find('A-100')
        self.assertLess(pos_c, pos_b)
        self.assertLess(pos_b, pos_a)

    def test_dashboard_includes_sortable_column_links(self):
        response = self.client.get(reverse('manage:dashboard'))
        self.assertContains(response, 'course_sort=code')
        self.assertContains(response, 'course_sort=title')
        self.assertContains(response, 'course_sort=category')
        self.assertContains(response, 'course_sort=credit_points')
        self.assertContains(response, 'list-table__sort-btn')
        self.assertContains(response, 'list-table__heading')
        self.assertContains(response, 'aria-sort="ascending"')
        self.assertContains(response, 'Sort by Code descending')
        self.assertContains(response, 'hx-target="#box-courses-list"')
        self.assertContains(response, 'data-sort-key="code"')
        self.assertNotContains(response, 'list-table__sort"')

    def test_course_list_partial_via_htmx(self):
        response = self.client.get(
            reverse('manage:course_list'),
            {'course_sort': 'title', 'course_dir': 'desc'},
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '<!DOCTYPE html>')
        pos_a, pos_b = self._course_codes_in_response(response)
        self.assertLess(pos_b, pos_a)


class CourseCRUDTests(TestCase):
    def setUp(self):
        self.client.force_login(staff_user())
        self.cat = CourseCategory.objects.create(name='Cat')
        self.mod1 = Module.objects.create(name='M1')
        self.mod2 = Module.objects.create(name='M2')

    def _payload(self, **overrides):
        data = {
            'code': 'COD101',
            'title': 'Course title',
            'description': '',
            'credit_points': '4.50',
            'category': self.cat.pk,
            'modules': [self.mod1.pk, self.mod2.pk],
            'notes': '',
            'active': 'on',
        }
        data.update(overrides)
        return data

    def test_get_add_form_as_fragment(self):
        response = self.client.get(
            reverse('manage:course_add'),
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'modal__card')
        self.assertContains(response, 'Add course')
        self.assertContains(response, 'name="credit_points"')
        self.assertContains(response, 'step="1"')
        self.assertNotContains(response, '<html')

    def test_post_valid_creates_with_modules(self):
        response = self.client.post(
            reverse('manage:course_add'),
            self._payload(),
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        course = Course.objects.get(code='COD101')
        self.assertEqual(course.credit_points, Decimal('4.50'))
        self.assertEqual(course.category_id, self.cat.pk)
        self.assertEqual(
            set(course.modules.values_list('pk', flat=True)),
            {self.mod1.pk, self.mod2.pk},
        )

    def test_post_without_modules_is_rejected(self):
        response = self.client.post(
            reverse('manage:course_add'),
            self._payload(modules=[]),
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Select at least one module')
        self.assertFalse(Course.objects.filter(code='COD101').exists())

    def test_edit_updates_modules(self):
        course = Course.objects.create(
            code='C1', title='t', credit_points=Decimal('3'),
            category=self.cat,
        )
        course.modules.add(self.mod1)

        response = self.client.post(
            reverse('manage:course_edit', args=[course.pk]),
            self._payload(code='C1', title='renamed', modules=[self.mod2.pk]),
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        course.refresh_from_db()
        self.assertEqual(course.title, 'renamed')
        self.assertEqual(
            list(course.modules.values_list('pk', flat=True)),
            [self.mod2.pk],
        )

    def test_delete_succeeds(self):
        course = Course.objects.create(
            code='Z9', title='z', credit_points=Decimal('1'),
            category=self.cat,
        )
        course.modules.add(self.mod1)

        response = self.client.post(
            reverse('manage:course_delete', args=[course.pk]),
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Course.objects.filter(pk=course.pk).exists())


class SpecializationCRUDTests(TestCase):
    def setUp(self):
        self.client.force_login(staff_user())
        self.mod1 = Module.objects.create(name='M1')
        self.mod2 = Module.objects.create(name='M2')

    def _payload(self, **overrides):
        data = {
            'name': 'Spec',
            'description': '',
            'active': 'on',

            'requirements-TOTAL_FORMS': '2',
            'requirements-INITIAL_FORMS': '0',
            'requirements-MIN_NUM_FORMS': '0',
            'requirements-MAX_NUM_FORMS': '1000',
            'requirements-0-id': '',
            'requirements-0-module': str(self.mod1.pk),
            'requirements-0-required_credit_points': '6.00',
            'requirements-0-display_order': '10',
            'requirements-1-id': '',
            'requirements-1-module': str(self.mod2.pk),
            'requirements-1-required_credit_points': '9.00',
            'requirements-1-display_order': '20',

            'rules-TOTAL_FORMS': '0',
            'rules-INITIAL_FORMS': '0',
            'rules-MIN_NUM_FORMS': '0',
            'rules-MAX_NUM_FORMS': '1000',
        }
        data.update(overrides)
        return data

    def test_get_add_form_renders_both_formsets(self):
        response = self.client.get(
            reverse('manage:specialization_add'),
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Module requirements')
        self.assertContains(response, 'Additional requirement rules')
        self.assertContains(response, 'requirements-TOTAL_FORMS')
        self.assertContains(response, 'rules-TOTAL_FORMS')
        # The two empty-row templates ship with the page for client-side cloning.
        self.assertContains(response, 'id="empty-requirement-row"')
        self.assertContains(response, 'id="empty-rule-row"')

    def test_add_form_suggests_lowest_unused_requirement_display_order(self):
        response = self.client.get(
            reverse('manage:specialization_add'),
            HTTP_HX_REQUEST='true',
        )
        self.assertContains(response, 'name="requirements-0-required_credit_points"')
        self.assertContains(
            response,
            'name="requirements-0-required_credit_points" step="1"',
        )
        self.assertContains(response, 'name="requirements-0-display_order" value="0"')

    def test_edit_form_suggests_lowest_unused_requirement_display_order(self):
        spec = Specialization.objects.create(name='Ordered')
        SpecializationModuleRequirement.objects.create(
            specialization=spec, module=self.mod1,
            required_credit_points=Decimal('6.00'), display_order=0,
        )
        response = self.client.get(
            reverse('manage:specialization_edit', args=[spec.pk]),
            HTTP_HX_REQUEST='true',
        )
        self.assertContains(response, 'name="requirements-0-display_order" value="0"')
        self.assertContains(response, 'name="requirements-1-display_order" value="1"')

    def test_post_duplicate_requirement_display_order_is_rejected(self):
        data = self._payload(
            **{
                'requirements-1-display_order': '10',
            }
        )
        response = self.client.post(
            reverse('manage:specialization_add'),
            data,
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This display order is already in use.')
        self.assertFalse(Specialization.objects.exists())

    def test_post_creates_spec_with_requirements(self):
        response = self.client.post(
            reverse('manage:specialization_add'),
            self._payload(),
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="box-specializations-list"')

        spec = Specialization.objects.get(name='Spec')
        reqs = list(spec.module_requirements.order_by('display_order'))
        self.assertEqual([r.module_id for r in reqs], [self.mod1.pk, self.mod2.pk])
        self.assertEqual(reqs[0].required_credit_points, Decimal('6.00'))
        self.assertEqual(reqs[1].required_credit_points, Decimal('9.00'))

    def test_post_with_additional_rule_creates_it_with_modules(self):
        data = self._payload(
            **{
                'rules-TOTAL_FORMS': '1',
                'rules-0-id': '',
                'rules-0-name': 'Methods & Stats minimum',
                'rules-0-description': '',
                'rules-0-rule_type':
                    AdditionalRequirementRuleType.MINIMUM_CREDITS_ACROSS_MODULES,
                'rules-0-required_credit_points': '9.00',
                'rules-0-modules_included': [str(self.mod1.pk), str(self.mod2.pk)],
                'rules-0-active': 'on',
            }
        )
        response = self.client.post(
            reverse('manage:specialization_add'),
            data,
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)

        spec = Specialization.objects.get(name='Spec')
        rule = spec.additional_requirement_rules.get()
        self.assertEqual(rule.name, 'Methods & Stats minimum')
        self.assertEqual(rule.required_credit_points, Decimal('9.00'))
        self.assertEqual(
            set(rule.modules_included.values_list('pk', flat=True)),
            {self.mod1.pk, self.mod2.pk},
        )

    def test_post_with_duplicate_modules_is_rejected(self):
        data = self._payload(
            **{
                'requirements-1-module': str(self.mod1.pk),  # same as row 0
            }
        )
        response = self.client.post(
            reverse('manage:specialization_add'),
            data,
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        # Django's BaseInlineFormSet.validate_unique() detects the violation
        # via the model's UniqueConstraint and surfaces a friendly message.
        self.assertContains(response, 'duplicate data')
        self.assertFalse(Specialization.objects.exists())

    def test_post_rule_without_modules_is_rejected(self):
        data = self._payload(
            **{
                'rules-TOTAL_FORMS': '1',
                'rules-0-id': '',
                'rules-0-name': 'Bad rule',
                'rules-0-description': '',
                'rules-0-rule_type':
                    AdditionalRequirementRuleType.MINIMUM_CREDITS_ACROSS_MODULES,
                'rules-0-required_credit_points': '9.00',
                # No modules_included.
                'rules-0-active': 'on',
            }
        )
        response = self.client.post(
            reverse('manage:specialization_add'),
            data,
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Select at least one module for this rule.')
        self.assertFalse(Specialization.objects.exists())

    def test_edit_save_ignores_blank_extra_requirement_row(self):
        spec = Specialization.objects.create(name='Edit me')
        r1 = SpecializationModuleRequirement.objects.create(
            specialization=spec, module=self.mod1,
            required_credit_points=Decimal('6.00'), display_order=0,
        )
        response = self.client.post(
            reverse('manage:specialization_edit', args=[spec.pk]),
            {
                'name': 'Edit me',
                'description': '',
                'active': 'on',
                'requirements-TOTAL_FORMS': '2',
                'requirements-INITIAL_FORMS': '1',
                'requirements-MIN_NUM_FORMS': '0',
                'requirements-MAX_NUM_FORMS': '1000',
                'requirements-0-id': str(r1.pk),
                'requirements-0-module': str(self.mod1.pk),
                'requirements-0-required_credit_points': '6.00',
                'requirements-0-display_order': '0',
                'requirements-1-id': '',
                'requirements-1-module': '',
                'requirements-1-required_credit_points': '',
                'requirements-1-display_order': '1',
                'rules-TOTAL_FORMS': '0',
                'rules-INITIAL_FORMS': '0',
                'rules-MIN_NUM_FORMS': '0',
                'rules-MAX_NUM_FORMS': '1000',
            },
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="box-specializations-list"')
        self.assertEqual(spec.module_requirements.count(), 1)

    def test_edit_updates_requirements_and_deletes_one(self):
        spec = Specialization.objects.create(name='Edit me')
        r1 = SpecializationModuleRequirement.objects.create(
            specialization=spec, module=self.mod1,
            required_credit_points=Decimal('6.00'), display_order=10,
        )
        r2 = SpecializationModuleRequirement.objects.create(
            specialization=spec, module=self.mod2,
            required_credit_points=Decimal('9.00'), display_order=20,
        )

        data = {
            'name': 'Edit me',
            'description': '',
            'active': 'on',

            'requirements-TOTAL_FORMS': '2',
            'requirements-INITIAL_FORMS': '2',
            'requirements-MIN_NUM_FORMS': '0',
            'requirements-MAX_NUM_FORMS': '1000',
            'requirements-0-id': str(r1.pk),
            'requirements-0-module': str(self.mod1.pk),
            'requirements-0-required_credit_points': '7.50',  # changed
            'requirements-0-display_order': '10',
            'requirements-1-id': str(r2.pk),
            'requirements-1-module': str(self.mod2.pk),
            'requirements-1-required_credit_points': '9.00',
            'requirements-1-display_order': '20',
            'requirements-1-DELETE': 'on',  # mark r2 for deletion

            'rules-TOTAL_FORMS': '0',
            'rules-INITIAL_FORMS': '0',
            'rules-MIN_NUM_FORMS': '0',
            'rules-MAX_NUM_FORMS': '1000',
        }
        response = self.client.post(
            reverse('manage:specialization_edit', args=[spec.pk]),
            data,
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)

        r1.refresh_from_db()
        self.assertEqual(r1.required_credit_points, Decimal('7.50'))
        self.assertFalse(
            SpecializationModuleRequirement.objects.filter(pk=r2.pk).exists()
        )

    def test_delete_removes_spec_and_cascades_requirements(self):
        spec = Specialization.objects.create(name='Doomed')
        SpecializationModuleRequirement.objects.create(
            specialization=spec, module=self.mod1,
            required_credit_points=Decimal('3.00'),
        )
        response = self.client.post(
            reverse('manage:specialization_delete', args=[spec.pk]),
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Specialization.objects.filter(pk=spec.pk).exists())
        # Cascade should have removed the requirement; module survives (PROTECT
        # is on Module ← requirement, not the other direction).
        self.assertFalse(SpecializationModuleRequirement.objects.exists())
        self.assertTrue(Module.objects.filter(pk=self.mod1.pk).exists())

    def test_atomic_save_rollback_on_formset_failure(self):
        # Make the parent form valid but the rule formset invalid (rule without
        # modules) — nothing should land in the DB.
        data = self._payload(
            **{
                'rules-TOTAL_FORMS': '1',
                'rules-0-id': '',
                'rules-0-name': 'Bad',
                'rules-0-description': '',
                'rules-0-rule_type':
                    AdditionalRequirementRuleType.MINIMUM_CREDITS_ACROSS_MODULES,
                'rules-0-required_credit_points': '5.00',
                'rules-0-active': 'on',
            }
        )
        self.client.post(
            reverse('manage:specialization_add'),
            data,
            HTTP_HX_REQUEST='true',
        )
        self.assertFalse(Specialization.objects.exists())
        self.assertFalse(SpecializationModuleRequirement.objects.exists())
        self.assertFalse(AdditionalRequirementRule.objects.exists())

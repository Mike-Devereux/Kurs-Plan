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

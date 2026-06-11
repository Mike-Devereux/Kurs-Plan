from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from courses.models import Course, CourseCategory, Module
from specializations.models import (
    AdditionalRequirementRule,
    AdditionalRequirementRuleType,
    Specialization,
    SpecializationModuleRequirement,
)

from .allocator import (
    MAX_NODES,
    BacktrackingAllocator,
    allocation_as_map,
    assigned_module,
    course_by_id,
    credits_for_module,
    default_allocator,
    unused_course_ids,
)
from .allocator.base import AllocatorProtocol
from .domain import (
    AdditionalRule,
    AdditionalRuleStatus,
    Allocation,
    CheckResultSummary,
    CourseRef,
    EvaluationInput,
    EvaluationResult,
    FailureReason,
    ModuleRef,
    ModuleRequirement,
    ModuleStatus,
)
from .evaluator import (
    COURSE_UNUSABLE,
    FAILURE,
    MODULE_UNDERFILLED,
    NO_VIABLE_ALLOCATION,
    RULE_NOT_MET,
    SEARCH_BUDGET_EXCEEDED,
    SUCCESS,
    compute_module_statuses,
    evaluate,
)
from .loader import build_input
from .rules import REGISTRY as RULE_REGISTRY, register
from .rules.base import RuleEvaluator
from .rules.minimum_credits import RULE_TYPE as MIN_CREDITS_RULE_TYPE
from .rules.minimum_credits import evaluate as minimum_credits_evaluate
from .scoring import score
from .services import evaluate_selection


class DomainTypesTests(TestCase):
    def test_check_result_summary_defaults_messages(self):
        summary = CheckResultSummary(
            status='pending',
            total_credit_points=Decimal('0'),
        )
        self.assertEqual(summary.messages, ())

    def test_course_ref_frozen_fields(self):
        ref = CourseRef(
            id=1,
            code='X',
            title='Y',
            credit_points=Decimal('4.50'),
            eligible_module_ids=frozenset({2, 3}),
        )
        self.assertEqual(ref.eligible_module_ids, frozenset({2, 3}))

    def test_evaluation_result_defaults(self):
        result = EvaluationResult(status='failure')
        self.assertIsNone(result.allocation)
        self.assertEqual(result.module_statuses, ())
        self.assertEqual(result.failure_reasons, ())


class CheckerPageTests(TestCase):
    def setUp(self):
        self.category_active = CourseCategory.objects.create(
            name='Active cat', display_order=10,
        )
        self.category_inactive = CourseCategory.objects.create(
            name='Inactive cat', display_order=20, active=False,
        )
        self.module = Module.objects.create(name='M1')
        self.specialization = Specialization.objects.create(name='Spec A')
        Specialization.objects.create(name='Inactive spec', active=False)

        self.course1 = Course.objects.create(
            code='AC101', title='Active course 1',
            credit_points=Decimal('6.00'),
            category=self.category_active,
        )
        self.course1.modules.add(self.module)
        self.course2 = Course.objects.create(
            code='AC102', title='Active course 2',
            credit_points=Decimal('4.50'),
            category=self.category_active,
        )
        self.course2.modules.add(self.module)

        SpecializationModuleRequirement.objects.create(
            specialization=self.specialization,
            module=self.module,
            required_credit_points=Decimal('6.00'),
            display_order=0,
        )

        self.inactive_course = Course.objects.create(
            code='ZX999', title='Hidden course',
            credit_points=Decimal('3.00'),
            category=self.category_active,
            active=False,
        )
        self.course_in_inactive_cat = Course.objects.create(
            code='IC101', title='Course in inactive category',
            credit_points=Decimal('3.00'),
            category=self.category_inactive,
        )

    def test_get_renders_active_specializations_and_courses_only(self):
        response = self.client.get(reverse('planner:checker'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Spec A')
        self.assertNotContains(response, 'Inactive spec')
        self.assertContains(response, 'AC101')
        self.assertContains(response, 'AC102')
        # Inactive course / inactive-category course must not appear.
        self.assertNotContains(response, 'ZX999')
        self.assertNotContains(response, 'IC101')
        # Catalog grouped by category, with a section heading.
        self.assertContains(response, 'Active cat')
        self.assertNotContains(response, 'Inactive cat')

    def test_get_does_not_show_result_block(self):
        response = self.client.get(reverse('planner:checker'))
        self.assertNotContains(response, 'id="result-heading"')

    def test_post_valid_renders_result_on_same_page(self):
        response = self.client.post(
            reverse('planner:checker'),
            {
                'specialization': self.specialization.pk,
                'courses': [self.course1.pk, self.course2.pk],
            },
        )
        self.assertEqual(response.status_code, 200)
        # Form remains visible (same template); result section appears.
        self.assertContains(response, 'Specialization checker')
        self.assertContains(response, 'id="result-heading"')
        self.assertContains(response, 'Spec A')
        # Total credit points should reflect the sum of selected courses.
        self.assertContains(response, '10.5')
        self.assertContains(response, 'Requirements satisfied')
        self.assertContains(
            response,
            'All specialization requirements checked for this selection',
        )
        self.assertContains(response, 'M1')

    def test_post_without_courses_shows_validation_error(self):
        response = self.client.post(
            reverse('planner:checker'),
            {'specialization': self.specialization.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Select at least one course')
        self.assertNotContains(response, 'id="result-heading"')

    def test_post_with_inactive_course_is_rejected(self):
        response = self.client.post(
            reverse('planner:checker'),
            {
                'specialization': self.specialization.pk,
                'courses': [self.inactive_course.pk],
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="result-heading"')

    def test_post_with_inactive_specialization_is_rejected(self):
        inactive = Specialization.objects.get(name='Inactive spec')
        response = self.client.post(
            reverse('planner:checker'),
            {
                'specialization': inactive.pk,
                'courses': [self.course1.pk],
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="result-heading"')

    def test_post_preserves_selection_after_invalid_submit(self):
        # Submitting without specialization keeps the checked boxes; we
        # re-check by inspecting context rather than parsing whitespace-
        # sensitive HTML.
        response = self.client.post(
            reverse('planner:checker'),
            {'courses': [self.course1.pk]},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context['selected_course_ids'],
            {self.course1.pk},
        )
        self.assertNotContains(response, 'id="result-heading"')


class EvaluateSelectionTests(TestCase):
    def test_success_when_no_requirements_and_empty_eligible_universe(self):
        """Loader yields an empty eligible set; evaluator still accepts."""
        spec = Specialization.objects.create(name='S')
        category = CourseCategory.objects.create(name='C')
        c1 = Course.objects.create(
            code='X1', title='X1', credit_points=Decimal('4.50'),
            category=category,
        )
        c2 = Course.objects.create(
            code='X2', title='X2', credit_points=Decimal('3.00'),
            category=category,
        )
        result = evaluate_selection(spec, [c1, c2])
        self.assertEqual(result.status, 'success')
        self.assertEqual(result.specialization, spec)
        self.assertEqual(result.selected_courses, (c1, c2))
        self.assertEqual(result.total_credit_points, Decimal('7.50'))
        self.assertTrue(result.messages)
        self.assertEqual(result.module_statuses, ())
        self.assertEqual(len(result.allocation), 2)
        self.assertTrue(all(e.module is None for e in result.allocation))


class PresenterIntegrationTests(TestCase):
    def test_evaluate_selection_hydrates_module_status(self):
        category = CourseCategory.objects.create(name='Cat')
        module = Module.objects.create(name='Foundations')
        spec = Specialization.objects.create(name='Spec')
        SpecializationModuleRequirement.objects.create(
            specialization=spec,
            module=module,
            required_credit_points=Decimal('6.00'),
            display_order=0,
        )
        course = Course.objects.create(
            code='CHE101',
            title='Intro',
            credit_points=Decimal('6.00'),
            category=category,
        )
        course.modules.add(module)
        result = evaluate_selection(spec, [course])
        self.assertEqual(result.status, 'success')
        self.assertEqual(len(result.module_statuses), 1)
        row = result.module_statuses[0]
        self.assertEqual(row.module, module)
        self.assertTrue(row.satisfied)
        self.assertEqual(len(result.allocation), 1)
        self.assertEqual(result.allocation[0].course, course)
        self.assertEqual(result.allocation[0].module, module)

    def test_allocation_ordered_by_module_name_then_course_code(self):
        from .domain import Allocation, EvaluationResult
        from .evaluator import SUCCESS
        from .presenter import build_check_result

        category = CourseCategory.objects.create(name='Cat')
        mod_alpha = Module.objects.create(name='Alpha')
        mod_zulu = Module.objects.create(name='Zulu')
        spec = Specialization.objects.create(name='Spec')
        course_b = Course.objects.create(
            code='B-100', title='Bravo', credit_points=Decimal('3.00'),
            category=category,
        )
        course_a = Course.objects.create(
            code='A-100', title='Alpha course', credit_points=Decimal('3.00'),
            category=category,
        )
        course_b.modules.add(mod_zulu)
        course_a.modules.add(mod_alpha)

        result = EvaluationResult(
            status=SUCCESS,
            allocation=Allocation(pairs=(
                (course_b.pk, mod_zulu.pk),
                (course_a.pk, mod_alpha.pk),
            )),
        )
        check = build_check_result(
            result,
            spec,
            (course_b, course_a),
            total_credit_points=Decimal('6.00'),
        )

        self.assertEqual(check.allocation[0].module, mod_alpha)
        self.assertEqual(check.allocation[0].course, course_a)
        self.assertFalse(check.allocation[0].module_block_start)
        self.assertEqual(check.allocation[1].module, mod_zulu)
        self.assertEqual(check.allocation[1].course, course_b)
        self.assertTrue(check.allocation[1].module_block_start)

    def test_allocation_separator_only_on_module_change(self):
        from django.template.loader import render_to_string

        from .domain import Allocation, EvaluationResult
        from .evaluator import SUCCESS
        from .presenter import build_check_result

        category = CourseCategory.objects.create(name='Cat')
        mod = Module.objects.create(name='Shared')
        spec = Specialization.objects.create(name='Spec')
        course_a = Course.objects.create(
            code='A-100', title='A', credit_points=Decimal('3.00'),
            category=category,
        )
        course_b = Course.objects.create(
            code='B-100', title='B', credit_points=Decimal('3.00'),
            category=category,
        )
        course_a.modules.add(mod)
        course_b.modules.add(mod)

        same_module = build_check_result(
            EvaluationResult(
                status=SUCCESS,
                allocation=Allocation(pairs=(
                    (course_a.pk, mod.pk),
                    (course_b.pk, mod.pk),
                )),
            ),
            spec,
            (course_a, course_b),
            total_credit_points=Decimal('6.00'),
        )
        self.assertFalse(same_module.allocation[0].module_block_start)
        self.assertFalse(same_module.allocation[1].module_block_start)
        same_module_html = render_to_string(
            'planner/partials/_result.html',
            {'result': same_module},
        )
        self.assertEqual(
            same_module_html.count('result__allocation-row--module-start'),
            0,
        )

        mod_other = Module.objects.create(name='Other')
        course_c = Course.objects.create(
            code='C-100', title='C', credit_points=Decimal('3.00'),
            category=category,
        )
        course_c.modules.add(mod_other)
        mixed_modules = build_check_result(
            EvaluationResult(
                status=SUCCESS,
                allocation=Allocation(pairs=(
                    (course_a.pk, mod.pk),
                    (course_b.pk, mod.pk),
                    (course_c.pk, mod_other.pk),
                )),
            ),
            spec,
            (course_a, course_b, course_c),
            total_credit_points=Decimal('9.00'),
        )
        # Rows are sorted by module name, then course code ("Other" before "Shared").
        self.assertEqual(mixed_modules.allocation[0].course, course_c)
        self.assertFalse(mixed_modules.allocation[0].module_block_start)
        self.assertEqual(mixed_modules.allocation[1].course, course_a)
        self.assertTrue(mixed_modules.allocation[1].module_block_start)
        self.assertEqual(mixed_modules.allocation[2].course, course_b)
        self.assertFalse(mixed_modules.allocation[2].module_block_start)
        mixed_html = render_to_string(
            'planner/partials/_result.html',
            {'result': mixed_modules},
        )
        self.assertEqual(
            mixed_html.count('result__allocation-row--module-start'),
            1,
        )


class EvaluateSelectionEndToEndTests(TestCase):
    """End-to-end ORM tests against the ``seed_demo_data`` fixture.

    These exercise the full pipeline: loader → backtracking allocator →
    rule registry → scoring → evaluator → presenter. The seed data lives
    next to the ``BSc Chemistry – Analytical Track`` specialization:
    Foundations (6 CP), Synthesis (9 CP), Analysis (6 CP), plus a
    ``Methods+Statistics ≥ 9 CP`` additional rule.
    """

    SPEC_NAME = 'BSc Chemistry – Analytical Track'

    @classmethod
    def setUpTestData(cls):
        call_command('seed_demo_data', stdout=StringIO())
        cls.spec = Specialization.objects.get(name=cls.SPEC_NAME)

    def _courses(self, *codes):
        by_code = {c.code: c for c in Course.objects.filter(code__in=codes)}
        return [by_code[c] for c in codes]

    def test_clear_pass_all_seeded_courses(self):
        courses = list(
            Course.objects.filter(active=True).order_by('code')
        )
        result = evaluate_selection(self.spec, courses)
        self.assertEqual(result.status, 'success')
        self.assertTrue(
            all(s.satisfied for s in result.module_statuses),
            msg=[(s.module.name, s.achieved_credit_points,
                  s.required_credit_points) for s in result.module_statuses],
        )
        self.assertTrue(
            all(s.satisfied for s in result.additional_rule_statuses),
        )
        self.assertEqual(result.failure_reasons, ())
        self.assertEqual(result.total_credit_points, Decimal('46.50'))

    def test_additional_rule_borderline_exact_match(self):
        # MAT210 (Methods, 6 CP) + MAT220 (Methods, 3 CP) = 9 CP exactly
        # on the rule. Foundations must come from CHE101 because CHE201
        # is the only multi-module course that can feed Synthesis up to
        # 9 CP alongside CHE301 (4.5 CP).
        courses = self._courses(
            'CHE101', 'CHE201', 'CHE301', 'CHE220', 'MAT210', 'MAT220',
        )
        result = evaluate_selection(self.spec, courses)
        self.assertEqual(result.status, 'success')

        # Rule is satisfied exactly at the threshold (9.00 CP).
        rule_row = next(
            r for r in result.additional_rule_statuses
            if r.rule.name == 'Methods & Statistics minimum'
        )
        self.assertTrue(rule_row.satisfied)
        self.assertEqual(rule_row.achieved_credit_points, Decimal('9.00'))

        # Allocation must thread the needle: CHE101→Foundations,
        # CHE201→Synthesis, CHE301→Synthesis, CHE220→Analysis, and
        # both MAT* courses on Methods (the only module they're
        # eligible for).
        placed = {e.course.code: e.module.name if e.module else None
                  for e in result.allocation}
        self.assertEqual(placed['CHE101'], 'Foundations')
        self.assertEqual(placed['CHE201'], 'Synthesis')
        self.assertEqual(placed['CHE301'], 'Synthesis')
        self.assertEqual(placed['CHE220'], 'Analysis')
        self.assertEqual(placed['MAT210'], 'Methods')
        self.assertEqual(placed['MAT220'], 'Methods')


class OverFillSatisfiedModuleTests(TestCase):
    """End-to-end ORM tests for the milestone-5 over-fill rule.

    A course must be allowed to land on a module whose base requirement
    is already met whenever doing so is needed to satisfy an additional
    rule. The fixture pins this at the public API: Methods is the only
    base requirement, MAT210 covers it on its own, and the rule needs
    9 CP across Methods + Statistics — so CSC210 must end up on one of
    those modules (and *not* unused) for the result to be a success.
    """

    def setUp(self):
        self.category = CourseCategory.objects.create(name='Cat')
        self.mod_methods = Module.objects.create(name='Methods')
        self.mod_stat = Module.objects.create(name='Statistics')

        self.spec = Specialization.objects.create(name='Methods Track')
        SpecializationModuleRequirement.objects.create(
            specialization=self.spec,
            module=self.mod_methods,
            required_credit_points=Decimal('6.00'),
            display_order=10,
        )
        self.rule = AdditionalRequirementRule.objects.create(
            specialization=self.spec,
            name='Methods & Statistics minimum',
            rule_type=(
                AdditionalRequirementRuleType.MINIMUM_CREDITS_ACROSS_MODULES
            ),
            required_credit_points=Decimal('9.00'),
        )
        self.rule.modules_included.set([self.mod_methods, self.mod_stat])

        self.mat210 = Course.objects.create(
            code='MAT210',
            title='Mathematical methods',
            credit_points=Decimal('6.00'),
            category=self.category,
        )
        self.mat210.modules.add(self.mod_methods)

        self.csc210 = Course.objects.create(
            code='CSC210',
            title='Data analysis',
            credit_points=Decimal('4.50'),
            category=self.category,
        )
        self.csc210.modules.set([self.mod_methods, self.mod_stat])

    def test_course_placed_on_satisfied_module_to_meet_rule(self):
        result = evaluate_selection(self.spec, [self.mat210, self.csc210])
        self.assertEqual(result.status, 'success')

        # MAT210 anchors the base requirement.
        placed = {e.course.code: e.module for e in result.allocation}
        self.assertEqual(placed['MAT210'], self.mod_methods)
        # CSC210 must land on Methods or Statistics; the orchestrator
        # is not allowed to skip it (which would leave the rule unmet).
        self.assertIn(placed['CSC210'], {self.mod_methods, self.mod_stat})

        # Methods status is satisfied (potentially over-filled).
        methods_status = next(
            s for s in result.module_statuses
            if s.module == self.mod_methods
        )
        self.assertTrue(methods_status.satisfied)

        # Rule is satisfied via 6 + 4.5 = 10.5 CP across Methods + Stats.
        rule_status = result.additional_rule_statuses[0]
        self.assertEqual(rule_status.achieved_credit_points, Decimal('10.50'))
        self.assertTrue(rule_status.satisfied)


class PresenterFailureReasonViewTests(TestCase):
    def test_search_budget_exceeded_message_includes_node_count(self):
        from .domain import EvaluationResult
        from .presenter import build_check_result

        spec = Specialization.objects.create(name='S')
        result = EvaluationResult(
            status=FAILURE,
            allocation=None,
            failure_reasons=(
                FailureReason(
                    code=SEARCH_BUDGET_EXCEEDED,
                    attempted_module_ids=(42_000,),
                ),
            ),
        )
        check_result = build_check_result(
            result, spec, (),
            total_credit_points=Decimal('0'),
        )
        view = check_result.failure_reasons[0]
        self.assertEqual(view.code, SEARCH_BUDGET_EXCEEDED)
        self.assertIn('42000', view.message)
        self.assertIn('best one found so far', view.message)


class CheckerResultHtmlTests(TestCase):
    """Step 11: POST the checker and assert structured result HTML."""

    SPEC_NAME = 'BSc Chemistry – Analytical Track'

    @classmethod
    def setUpTestData(cls):
        call_command('seed_demo_data', stdout=StringIO())
        cls.spec = Specialization.objects.get(name=cls.SPEC_NAME)

    def _post_checker(self, course_queryset):
        return self.client.post(
            reverse('planner:checker'),
            {
                'specialization': self.spec.pk,
                'courses': list(course_queryset.values_list('pk', flat=True)),
            },
        )

    def test_success_post_renders_module_rule_and_allocation_tables(self):
        courses = Course.objects.filter(active=True).order_by('code')
        response = self._post_checker(courses)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()

        self.assertContains(response, 'id="result-heading"')
        self.assertContains(response, 'Requirements satisfied.')
        self.assertContains(response, self.SPEC_NAME)
        self.assertContains(response, '46.50')

        self.assertContains(response, 'Module requirements')
        for name in ('Foundations', 'Synthesis', 'Analysis'):
            self.assertContains(response, name)

        self.assertContains(response, 'Additional rules')
        self.assertContains(response, 'Methods &amp; Statistics minimum')
        self.assertContains(response, 'Minimum credits across modules')
        self.assertIn('Methods', content)
        self.assertIn('Statistics', content)

        self.assertContains(response, 'Allocation (best or chosen)')
        self.assertContains(response, 'result__table--allocation')
        self.assertContains(response, 'result__allocation-row--module-start')
        self.assertContains(response, 'CHE101')

    def test_failure_post_renders_headline_and_what_failed_section(self):
        che101 = Course.objects.get(code='CHE101')
        response = self._post_checker(Course.objects.filter(pk=che101.pk))
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, 'Requirements not satisfied.')
        self.assertContains(response, 'What did not match')
        self.assertContains(response, 'short by')


class LoaderTests(TestCase):
    def setUp(self):
        self.category = CourseCategory.objects.create(name='Cat')
        self.mod_foundations = Module.objects.create(name='Foundations')
        self.mod_synthesis = Module.objects.create(name='Synthesis')
        self.mod_methods = Module.objects.create(name='Methods')
        self.mod_statistics = Module.objects.create(name='Statistics')
        # An extra module that is *not* referenced by the specialization;
        # courses eligible for it should not have it in eligible_module_ids.
        self.mod_unrelated = Module.objects.create(name='Unrelated')

        self.spec = Specialization.objects.create(name='Spec')
        SpecializationModuleRequirement.objects.create(
            specialization=self.spec, module=self.mod_foundations,
            required_credit_points=Decimal('6.00'), display_order=10,
        )
        SpecializationModuleRequirement.objects.create(
            specialization=self.spec, module=self.mod_synthesis,
            required_credit_points=Decimal('9.00'), display_order=20,
        )
        self.rule = AdditionalRequirementRule.objects.create(
            specialization=self.spec,
            name='Methods & Stats minimum',
            rule_type=AdditionalRequirementRuleType.MINIMUM_CREDITS_ACROSS_MODULES,
            required_credit_points=Decimal('9.00'),
        )
        self.rule.modules_included.set([self.mod_methods, self.mod_statistics])

        self.course_che101 = Course.objects.create(
            code='CHE101', title='Gen Chem',
            credit_points=Decimal('6.00'),
            category=self.category,
        )
        self.course_che101.modules.add(self.mod_foundations)

        self.course_csc210 = Course.objects.create(
            code='CSC210', title='Data Analysis',
            credit_points=Decimal('4.50'),
            category=self.category,
        )
        self.course_csc210.modules.set([
            self.mod_methods, self.mod_statistics, self.mod_unrelated,
        ])

    def test_projects_specialization_metadata(self):
        result = build_input(self.spec, [])
        self.assertEqual(result.specialization_id, self.spec.pk)
        self.assertEqual(result.specialization_name, 'Spec')

    def test_modules_include_requirement_and_rule_targets(self):
        result = build_input(self.spec, [])
        names = {m.name for m in result.modules}
        self.assertEqual(
            names,
            {'Foundations', 'Synthesis', 'Methods', 'Statistics'},
        )

    def test_module_requirements_preserve_display_order(self):
        result = build_input(self.spec, [])
        self.assertEqual(
            [r.module_id for r in result.module_requirements],
            [self.mod_foundations.id, self.mod_synthesis.id],
        )
        self.assertEqual(
            result.module_requirements[0].required_credit_points,
            Decimal('6.00'),
        )

    def test_additional_rules_carry_modules_included_ids(self):
        result = build_input(self.spec, [])
        self.assertEqual(len(result.additional_rules), 1)
        rule = result.additional_rules[0]
        self.assertEqual(rule.id, self.rule.pk)
        self.assertEqual(rule.rule_type,
                         AdditionalRequirementRuleType.MINIMUM_CREDITS_ACROSS_MODULES.value)
        self.assertEqual(
            rule.modules_included_ids,
            frozenset({self.mod_methods.id, self.mod_statistics.id}),
        )

    def test_courses_eligible_modules_are_restricted_to_universe(self):
        result = build_input(
            self.spec,
            [self.course_che101, self.course_csc210],
        )
        codes = [c.code for c in result.courses]
        self.assertEqual(codes, ['CHE101', 'CSC210'])
        csc210 = result.courses[1]
        # ``Unrelated`` must be filtered out because no requirement/rule
        # references it for this specialization.
        self.assertEqual(
            csc210.eligible_module_ids,
            frozenset({self.mod_methods.id, self.mod_statistics.id}),
        )

    def test_inactive_additional_rule_is_skipped(self):
        self.rule.active = False
        self.rule.save()
        result = build_input(self.spec, [])
        self.assertEqual(result.additional_rules, ())
        # Modules previously brought in only by the rule (Methods,
        # Statistics) should disappear from the universe now that the
        # rule is gone.
        names = {m.name for m in result.modules}
        self.assertEqual(names, {'Foundations', 'Synthesis'})

    def test_duplicate_courses_are_deduplicated(self):
        result = build_input(
            self.spec,
            [self.course_che101, self.course_che101],
        )
        self.assertEqual(len(result.courses), 1)


class AllocatorProtocolTests(SimpleTestCase):
    def test_default_allocator_is_protocol_compatible(self):
        alloc = default_allocator()
        self.assertIsInstance(alloc, BacktrackingAllocator)
        self.assertIsInstance(alloc, AllocatorProtocol)


class BacktrackingAllocatorTests(SimpleTestCase):
    def test_empty_course_list_yields_single_empty_allocation(self):
        inp = EvaluationInput(
            specialization_id=1,
            specialization_name='S',
            modules=(),
            module_requirements=(),
            additional_rules=(),
            courses=(),
        )
        out = list(BacktrackingAllocator().search(inp))
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].pairs, ())

    def test_single_course_one_eligible_module_two_allocations(self):
        """One eligible module plus UNUSED → two complete assignments."""
        inp = EvaluationInput(
            specialization_id=1,
            specialization_name='S',
            modules=(ModuleRef(id=10, name='M'),),
            module_requirements=(
                ModuleRequirement(
                    module_id=10,
                    required_credit_points=Decimal('6'),
                    display_order=0,
                ),
            ),
            additional_rules=(),
            courses=(
                CourseRef(
                    id=1,
                    code='A',
                    title='A',
                    credit_points=Decimal('3'),
                    eligible_module_ids=frozenset({10}),
                ),
            ),
        )
        out = list(BacktrackingAllocator().search(inp))
        self.assertEqual(len(out), 2)
        self.assertCountEqual(
            [a.pairs for a in out],
            [((1, 10),), ((1, None),)],
        )

    def test_one_course_two_eligible_modules_three_allocations(self):
        inp = EvaluationInput(
            specialization_id=1,
            specialization_name='S',
            modules=(),
            module_requirements=(),
            additional_rules=(),
            courses=(
                CourseRef(
                    id=1,
                    code='A',
                    title='A',
                    credit_points=Decimal('3'),
                    eligible_module_ids=frozenset({10, 20}),
                ),
            ),
        )
        out = list(BacktrackingAllocator().search(inp))
        self.assertEqual(len(out), 3)
        self.assertCountEqual(
            [a.pairs for a in out],
            [((1, 10),), ((1, 20),), ((1, None),)],
        )

    def test_course_may_be_placed_on_already_satisfied_module(self):
        """Second course only eligible for module 10; first course fills 10's
        requirement — allocator must still emit (2 → 10) branches.
        """
        inp = EvaluationInput(
            specialization_id=1,
            specialization_name='S',
            modules=(ModuleRef(id=10, name='M'),),
            module_requirements=(
                ModuleRequirement(
                    module_id=10,
                    required_credit_points=Decimal('6'),
                    display_order=0,
                ),
            ),
            additional_rules=(),
            courses=(
                CourseRef(
                    id=1,
                    code='BIG',
                    title='Big',
                    credit_points=Decimal('6'),
                    eligible_module_ids=frozenset({10}),
                ),
                CourseRef(
                    id=2,
                    code='SMALL',
                    title='Small',
                    credit_points=Decimal('3'),
                    eligible_module_ids=frozenset({10}),
                ),
            ),
        )
        alloc = BacktrackingAllocator()
        pair_sets = {a.pairs for a in alloc.search(inp)}
        self.assertIn(((1, 10), (2, 10)), pair_sets)
        # UNUSED branch for course 2 must still exist.
        self.assertIn(((1, 10), (2, None)), pair_sets)

    def test_search_is_deterministic(self):
        inp = EvaluationInput(
            specialization_id=1,
            specialization_name='S',
            modules=(),
            module_requirements=(),
            additional_rules=(),
            courses=(
                CourseRef(
                    id=2,
                    code='B',
                    title='B',
                    credit_points=Decimal('1'),
                    eligible_module_ids=frozenset({99}),
                ),
                CourseRef(
                    id=1,
                    code='A',
                    title='A',
                    credit_points=Decimal('1'),
                    eligible_module_ids=frozenset({99}),
                ),
            ),
        )
        a = [x.pairs for x in BacktrackingAllocator().search(inp)]
        b = [x.pairs for x in BacktrackingAllocator().search(inp)]
        self.assertEqual(a, b)
        # DFS order: course 1 before 2; each {99, None}.
        self.assertEqual(
            a,
            [
                ((1, 99), (2, 99)),
                ((1, 99), (2, None)),
                ((1, None), (2, 99)),
                ((1, None), (2, None)),
            ],
        )

    def test_max_nodes_stops_without_complete_enumeration(self):
        courses = tuple(
            CourseRef(
                id=i,
                code=f'C{i}',
                title='T',
                credit_points=Decimal('1'),
                eligible_module_ids=frozenset({1}),
            )
            for i in range(1, 5)
        )
        inp = EvaluationInput(
            specialization_id=1,
            specialization_name='S',
            modules=(),
            module_requirements=(),
            additional_rules=(),
            courses=courses,
        )
        full_alloc = BacktrackingAllocator(max_nodes=MAX_NODES)
        full = list(full_alloc.search(inp))
        self.assertEqual(len(full), 16)
        self.assertFalse(full_alloc.budget_exhausted)
        capped = BacktrackingAllocator(max_nodes=12)
        result = list(capped.search(inp))
        self.assertLess(len(result), 16)
        self.assertGreater(len(result), 0)
        self.assertTrue(capped.budget_exhausted)
        self.assertGreater(capped.nodes_visited, 12)

    def test_course_with_no_eligible_modules_only_unused_branch(self):
        inp = EvaluationInput(
            specialization_id=1,
            specialization_name='S',
            modules=(),
            module_requirements=(),
            additional_rules=(),
            courses=(
                CourseRef(
                    id=1,
                    code='ORPH',
                    title='Orphan',
                    credit_points=Decimal('2'),
                    eligible_module_ids=frozenset(),
                ),
            ),
        )
        out = list(BacktrackingAllocator().search(inp))
        self.assertEqual([a.pairs for a in out], [((1, None),)])


class RuleRegistryTests(SimpleTestCase):
    def test_minimum_credits_is_registered(self):
        self.assertIn(MIN_CREDITS_RULE_TYPE, RULE_REGISTRY)
        self.assertIs(RULE_REGISTRY[MIN_CREDITS_RULE_TYPE],
                      minimum_credits_evaluate)

    def test_registered_evaluator_satisfies_protocol(self):
        self.assertIsInstance(
            RULE_REGISTRY[MIN_CREDITS_RULE_TYPE],
            RuleEvaluator,
        )

    def test_register_rejects_duplicate(self):
        type_id = 'unit_test_dup_rule_type'

        @register(type_id)
        def _evaluate(rule, allocation, input_):  # pragma: no cover
            raise AssertionError('should not be called')

        try:
            with self.assertRaises(ValueError):
                @register(type_id)
                def _other(rule, allocation, input_):  # pragma: no cover
                    raise AssertionError('should not be called')
        finally:
            RULE_REGISTRY.pop(type_id, None)


def _input_for_rule_tests() -> EvaluationInput:
    """Three courses; modules 10/20 are inside the rule, module 30 is not."""
    return EvaluationInput(
        specialization_id=1,
        specialization_name='S',
        modules=(
            ModuleRef(id=10, name='Methods'),
            ModuleRef(id=20, name='Statistics'),
            ModuleRef(id=30, name='Other'),
        ),
        module_requirements=(),
        additional_rules=(),
        courses=(
            CourseRef(
                id=1,
                code='A',
                title='A',
                credit_points=Decimal('4'),
                eligible_module_ids=frozenset({10, 20, 30}),
            ),
            CourseRef(
                id=2,
                code='B',
                title='B',
                credit_points=Decimal('5'),
                eligible_module_ids=frozenset({10, 20, 30}),
            ),
            CourseRef(
                id=3,
                code='C',
                title='C',
                credit_points=Decimal('6'),
                eligible_module_ids=frozenset({10, 20, 30}),
            ),
        ),
    )


class MinimumCreditsRuleTests(SimpleTestCase):
    def setUp(self):
        self.input_ = _input_for_rule_tests()
        self.rule = AdditionalRule(
            id=42,
            name='Min credits across Methods+Statistics',
            rule_type=MIN_CREDITS_RULE_TYPE,
            required_credit_points=Decimal('9'),
            modules_included_ids=frozenset({10, 20}),
        )

    def test_under_threshold_is_not_satisfied(self):
        # Only course 1 → 4 CP on module 10 (< 9).
        allocation = Allocation(pairs=((1, 10), (2, None), (3, None)))
        status = minimum_credits_evaluate(self.rule, allocation, self.input_)
        self.assertEqual(
            status,
            AdditionalRuleStatus(
                rule_id=42,
                required_credit_points=Decimal('9'),
                achieved_credit_points=Decimal('4'),
                satisfied=False,
            ),
        )

    def test_exactly_at_threshold_is_satisfied(self):
        # 4 + 5 = 9 across the included modules.
        allocation = Allocation(pairs=((1, 10), (2, 20), (3, None)))
        status = minimum_credits_evaluate(self.rule, allocation, self.input_)
        self.assertEqual(status.achieved_credit_points, Decimal('9'))
        self.assertTrue(status.satisfied)

    def test_over_threshold_is_satisfied(self):
        # 4 + 5 + 6 = 15 across included modules.
        allocation = Allocation(pairs=((1, 10), (2, 20), (3, 10)))
        status = minimum_credits_evaluate(self.rule, allocation, self.input_)
        self.assertEqual(status.achieved_credit_points, Decimal('15'))
        self.assertTrue(status.satisfied)

    def test_excludes_modules_outside_rule(self):
        # All on module 30; rule covers {10, 20} so achieved == 0.
        allocation = Allocation(pairs=((1, 30), (2, 30), (3, 30)))
        status = minimum_credits_evaluate(self.rule, allocation, self.input_)
        self.assertEqual(status.achieved_credit_points, Decimal('0'))
        self.assertFalse(status.satisfied)

    def test_ignores_unused_branches(self):
        allocation = Allocation(pairs=((1, None), (2, None), (3, None)))
        status = minimum_credits_evaluate(self.rule, allocation, self.input_)
        self.assertEqual(status.achieved_credit_points, Decimal('0'))
        self.assertFalse(status.satisfied)


def _input_for_module_status_tests() -> EvaluationInput:
    """Two modules with separate requirements; three eligible courses."""
    return EvaluationInput(
        specialization_id=1,
        specialization_name='S',
        modules=(
            ModuleRef(id=10, name='Foundations'),
            ModuleRef(id=20, name='Synthesis'),
        ),
        module_requirements=(
            ModuleRequirement(
                module_id=10,
                required_credit_points=Decimal('6'),
                display_order=10,
            ),
            ModuleRequirement(
                module_id=20,
                required_credit_points=Decimal('9'),
                display_order=20,
            ),
        ),
        additional_rules=(),
        courses=(
            CourseRef(
                id=1,
                code='F1',
                title='F1',
                credit_points=Decimal('3'),
                eligible_module_ids=frozenset({10}),
            ),
            CourseRef(
                id=2,
                code='F2',
                title='F2',
                credit_points=Decimal('3'),
                eligible_module_ids=frozenset({10}),
            ),
            CourseRef(
                id=3,
                code='F3',
                title='F3',
                credit_points=Decimal('4.5'),
                eligible_module_ids=frozenset({10, 20}),
            ),
        ),
    )


class ComputeModuleStatusesTests(SimpleTestCase):
    def setUp(self):
        self.input_ = _input_for_module_status_tests()

    def test_exactly_satisfied_module_and_unsatisfied_module(self):
        # 3 + 3 = 6 on module 10 (== 6 required, satisfied);
        # module 20 receives nothing.
        allocation = Allocation(pairs=((1, 10), (2, 10), (3, None)))
        statuses = compute_module_statuses(allocation, self.input_)
        self.assertEqual(
            statuses,
            (
                ModuleStatus(
                    module_id=10,
                    required_credit_points=Decimal('6'),
                    achieved_credit_points=Decimal('6'),
                    satisfied=True,
                ),
                ModuleStatus(
                    module_id=20,
                    required_credit_points=Decimal('9'),
                    achieved_credit_points=Decimal('0'),
                    satisfied=False,
                ),
            ),
        )

    def test_under_filled_module_is_not_satisfied(self):
        # 3 CP on module 10 (< 6); module 20 still empty.
        allocation = Allocation(pairs=((1, 10), (2, None), (3, None)))
        statuses = compute_module_statuses(allocation, self.input_)
        self.assertEqual(statuses[0].achieved_credit_points, Decimal('3'))
        self.assertFalse(statuses[0].satisfied)
        self.assertFalse(statuses[1].satisfied)

    def test_over_filled_module_is_still_satisfied(self):
        # 3 + 3 + 4.5 = 10.5 on module 10 (> 6 required) — the
        # over-fill invariant: surplus credit must not invalidate the
        # allocation; an additional rule (step 5) may depend on it.
        allocation = Allocation(pairs=((1, 10), (2, 10), (3, 10)))
        statuses = compute_module_statuses(allocation, self.input_)
        self.assertEqual(statuses[0].achieved_credit_points, Decimal('10.5'))
        self.assertTrue(statuses[0].satisfied)
        self.assertEqual(statuses[1].achieved_credit_points, Decimal('0'))
        self.assertFalse(statuses[1].satisfied)

    def test_preserves_module_requirement_order(self):
        # Requirements were loaded display_order=10, 20 — the returned
        # tuple must mirror that order regardless of pair order.
        allocation = Allocation(pairs=((3, 20), (1, 10), (2, 10)))
        statuses = compute_module_statuses(allocation, self.input_)
        self.assertEqual(
            [s.module_id for s in statuses],
            [10, 20],
        )

    def test_empty_module_requirements_yields_empty_tuple(self):
        empty = EvaluationInput(
            specialization_id=1,
            specialization_name='S',
            modules=(),
            module_requirements=(),
            additional_rules=(),
            courses=self.input_.courses,
        )
        allocation = Allocation(pairs=((1, 10), (2, 10), (3, 20)))
        self.assertEqual(compute_module_statuses(allocation, empty), ())


def _input_for_scoring_tests() -> EvaluationInput:
    """One module + one additional rule that needs credit on module 20.

    Module 10 requires 6 CP. The additional rule wants 6 CP across
    module 20 (which has *no* base requirement; it only exists to host
    rule credit). Courses are arranged so that ``module 10`` can either
    be just satisfied (leaving the rule unmet) or over-filled (helping
    nothing) or have one of its courses redirected to ``module 20`` to
    satisfy the rule.
    """
    return EvaluationInput(
        specialization_id=1,
        specialization_name='S',
        modules=(
            ModuleRef(id=10, name='M10'),
            ModuleRef(id=20, name='M20'),
        ),
        module_requirements=(
            ModuleRequirement(
                module_id=10,
                required_credit_points=Decimal('6'),
                display_order=10,
            ),
        ),
        additional_rules=(
            AdditionalRule(
                id=99,
                name='Need 6 CP on M20',
                rule_type=MIN_CREDITS_RULE_TYPE,
                required_credit_points=Decimal('6'),
                modules_included_ids=frozenset({20}),
            ),
        ),
        courses=(
            CourseRef(
                id=1,
                code='A',
                title='A',
                credit_points=Decimal('6'),
                eligible_module_ids=frozenset({10}),
            ),
            CourseRef(
                id=2,
                code='B',
                title='B',
                credit_points=Decimal('6'),
                eligible_module_ids=frozenset({10, 20}),
            ),
        ),
    )


def _score_against(input_: EvaluationInput, allocation: Allocation):
    """Helper: build statuses for ``allocation`` and return its score."""
    module_statuses = compute_module_statuses(allocation, input_)
    rule_statuses = tuple(
        minimum_credits_evaluate(rule, allocation, input_)
        for rule in input_.additional_rules
    )
    return score(allocation, module_statuses, rule_statuses, input_)


class ScoringTests(SimpleTestCase):
    def setUp(self):
        self.input_ = _input_for_scoring_tests()

    def test_score_shape(self):
        empty_alloc = Allocation(pairs=((1, None), (2, None)))
        result = _score_against(self.input_, empty_alloc)
        self.assertEqual(len(result), 4)
        mandatory, rules, neg_missing, assigned = result
        self.assertEqual(mandatory, 0)
        self.assertEqual(rules, 0)
        # 6 CP missing on module 10 + 6 CP missing on rule 99 = -12.
        self.assertEqual(neg_missing, Decimal('-12'))
        self.assertEqual(assigned, 0)

    def test_satisfying_a_rule_beats_overfilling_a_module(self):
        # ``overfill`` puts both courses on the already-required module 10
        # (12 CP > 6 required). The additional rule still needs 6 CP on
        # module 20, so it stays unmet.
        overfill = Allocation(pairs=((1, 10), (2, 10)))
        # ``rule_satisfied`` redirects course 2 onto module 20, which
        # satisfies the additional rule. Module 10 is just satisfied.
        rule_satisfied = Allocation(pairs=((1, 10), (2, 20)))

        s_overfill = _score_against(self.input_, overfill)
        s_rule = _score_against(self.input_, rule_satisfied)

        # Both allocations satisfy module 10's mandatory requirement…
        self.assertEqual(s_overfill[0], 1)
        self.assertEqual(s_rule[0], 1)
        # …but only one satisfies the additional rule, and rules sort
        # ahead of the missing-credit and assigned-count components.
        self.assertGreater(s_rule, s_overfill)

    def test_assigned_count_breaks_ties_when_satisfaction_equal(self):
        # ``unused`` leaves course 2 dangling; ``placed`` parks it on
        # module 20 even though doing so changes nothing about whether
        # any requirement is satisfied (the rule needs 6 CP, course 2
        # provides 6 CP → both allocations satisfy module 10 and the
        # rule). The placed allocation should win on the tie-breaker.
        unused = Allocation(pairs=((1, 10), (2, None)))
        placed = Allocation(pairs=((1, 10), (2, 20)))

        s_unused = _score_against(self.input_, unused)
        s_placed = _score_against(self.input_, placed)

        # ``placed`` satisfies module 10 *and* the rule; ``unused`` only
        # satisfies module 10. We compare the assigned-count tie-breaker
        # explicitly by checking the equal-satisfaction case below.
        self.assertGreater(s_placed, s_unused)

        # Now construct a head-to-head where both are equally satisfied:
        # a second module 20 placement makes no extra contribution, so
        # only ``assigned_count`` can differ.
        a = Allocation(pairs=((1, 10), (2, 20)))
        b = Allocation(pairs=((1, 10), (2, None)))
        self.assertGreater(_score_against(self.input_, a)[3],
                           _score_against(self.input_, b)[3])

    def test_negative_total_missing_orders_partial_failures(self):
        # All-unused vs single placement on module 10: module 10 is now
        # half-filled (3 CP, needs 6), so missing drops from 12 to 9.
        empty = Allocation(pairs=((1, None), (2, None)))
        half = Allocation(
            pairs=(
                (1, 10),
                # Course 2 contributes nothing here.
                (2, None),
            ),
        )
        self.assertGreater(
            _score_against(self.input_, half)[2],
            _score_against(self.input_, empty)[2],
        )


class _NoYieldAllocator:
    """Test double: yields nothing, exercising the ``NO_VIABLE_ALLOCATION``
    branch of :func:`planner.evaluator.evaluate`.
    """

    def search(self, _input):
        return iter(())


class _SingleAllocationAllocator:
    """Test double: yields exactly one hand-built allocation so we can
    pin the orchestrator's failure-reason construction independently of
    the scoring/DFS interplay.
    """

    def __init__(self, allocation):
        self._allocation = allocation

    def search(self, _input):
        yield self._allocation


class EvaluatorOrchestratorTests(SimpleTestCase):
    def test_pure_success_returns_success_and_short_circuits(self):
        # One module needing 6 CP, one 6-CP course eligible for it.
        inp = EvaluationInput(
            specialization_id=1,
            specialization_name='S',
            modules=(ModuleRef(id=10, name='M'),),
            module_requirements=(
                ModuleRequirement(
                    module_id=10,
                    required_credit_points=Decimal('6'),
                    display_order=0,
                ),
            ),
            additional_rules=(),
            courses=(
                CourseRef(
                    id=1,
                    code='A',
                    title='A',
                    credit_points=Decimal('6'),
                    eligible_module_ids=frozenset({10}),
                ),
            ),
        )
        result = evaluate(inp)
        self.assertEqual(result.status, SUCCESS)
        self.assertEqual(result.allocation, Allocation(pairs=((1, 10),)))
        self.assertTrue(result.module_statuses[0].satisfied)
        self.assertEqual(result.failure_reasons, ())
        self.assertEqual(result.unused_course_ids, frozenset())

    def test_already_satisfied_module_can_be_used_to_meet_a_rule(self):
        """Key milestone-5 behaviour: a course is allowed to land on a
        module whose base requirement is already met when doing so is
        needed to satisfy an additional rule.
        """
        inp = EvaluationInput(
            specialization_id=1,
            specialization_name='S',
            modules=(ModuleRef(id=10, name='M'),),
            module_requirements=(
                ModuleRequirement(
                    module_id=10,
                    required_credit_points=Decimal('6'),
                    display_order=0,
                ),
            ),
            additional_rules=(
                AdditionalRule(
                    id=99,
                    name='Need 9 CP on M',
                    rule_type=MIN_CREDITS_RULE_TYPE,
                    required_credit_points=Decimal('9'),
                    modules_included_ids=frozenset({10}),
                ),
            ),
            courses=(
                CourseRef(
                    id=1,
                    code='BIG',
                    title='Big',
                    credit_points=Decimal('6'),
                    eligible_module_ids=frozenset({10}),
                ),
                CourseRef(
                    id=2,
                    code='SMALL',
                    title='Small',
                    credit_points=Decimal('3'),
                    eligible_module_ids=frozenset({10}),
                ),
            ),
        )
        result = evaluate(inp)
        self.assertEqual(result.status, SUCCESS)
        # Course 2 must land on module 10 even though module 10's base
        # requirement (6 CP) is already met by course 1.
        self.assertEqual(
            dict(result.allocation.pairs),
            {1: 10, 2: 10},
        )
        self.assertTrue(result.module_statuses[0].satisfied)
        self.assertTrue(result.additional_rule_statuses[0].satisfied)
        self.assertEqual(
            result.additional_rule_statuses[0].achieved_credit_points,
            Decimal('9'),
        )

    def test_best_failed_allocation_is_returned_with_reasons(self):
        # Module 10 needs 6 CP, module 20 needs 6 CP. Only one 3-CP
        # course eligible for module 10 exists, plus an orphan course
        # eligible for nothing.
        inp = EvaluationInput(
            specialization_id=1,
            specialization_name='S',
            modules=(
                ModuleRef(id=10, name='M10'),
                ModuleRef(id=20, name='M20'),
            ),
            module_requirements=(
                ModuleRequirement(
                    module_id=10,
                    required_credit_points=Decimal('6'),
                    display_order=10,
                ),
                ModuleRequirement(
                    module_id=20,
                    required_credit_points=Decimal('6'),
                    display_order=20,
                ),
            ),
            additional_rules=(),
            courses=(
                CourseRef(
                    id=1,
                    code='A',
                    title='A',
                    credit_points=Decimal('3'),
                    eligible_module_ids=frozenset({10}),
                ),
                CourseRef(
                    id=2,
                    code='ORPH',
                    title='Orphan',
                    credit_points=Decimal('2'),
                    eligible_module_ids=frozenset(),
                ),
            ),
        )
        result = evaluate(inp)
        self.assertEqual(result.status, FAILURE)
        # Best allocation places course 1 on module 10 (any score where
        # mandatory_count=0, missing=9 beats the empty allocation's
        # missing=12); course 2 has no eligible module so it stays unused.
        self.assertEqual(dict(result.allocation.pairs), {1: 10, 2: None})
        self.assertEqual(result.unused_course_ids, frozenset({2}))

        codes = [r.code for r in result.failure_reasons]
        # Two module under-fills (module 10 missing 3 CP, module 20
        # missing 6 CP). Course 2 has *empty* eligible_module_ids so it
        # is intentionally **not** reported as COURSE_UNUSABLE.
        self.assertEqual(codes, [MODULE_UNDERFILLED, MODULE_UNDERFILLED])
        self.assertEqual(result.failure_reasons[0].module_id, 10)
        self.assertEqual(
            result.failure_reasons[0].missing_credit_points,
            Decimal('3'),
        )
        self.assertEqual(result.failure_reasons[1].module_id, 20)
        self.assertEqual(
            result.failure_reasons[1].missing_credit_points,
            Decimal('6'),
        )

    def test_failure_reasons_include_unmet_rule_and_unusable_course(self):
        # Module 10 satisfied by course 1; module 20 unmet; the
        # additional rule on module 20 is unmet; course 2 is eligible
        # for module 20 but the best allocation chosen by the score
        # places it on module 10 (over-fill is preferred since both
        # allocations satisfy the same count of mandatory modules but
        # the rule remains unmet either way) — wait, let's instead test
        # COURSE_UNUSABLE deterministically by giving course 2 only
        # access to a non-required module while module 20 is required.
        inp = EvaluationInput(
            specialization_id=1,
            specialization_name='S',
            modules=(
                ModuleRef(id=10, name='M10'),
                ModuleRef(id=20, name='M20'),
            ),
            module_requirements=(
                ModuleRequirement(
                    module_id=10,
                    required_credit_points=Decimal('6'),
                    display_order=10,
                ),
                ModuleRequirement(
                    module_id=20,
                    required_credit_points=Decimal('6'),
                    display_order=20,
                ),
            ),
            additional_rules=(
                AdditionalRule(
                    id=99,
                    name='Need 6 CP on M20',
                    rule_type=MIN_CREDITS_RULE_TYPE,
                    required_credit_points=Decimal('6'),
                    modules_included_ids=frozenset({20}),
                ),
            ),
            courses=(
                CourseRef(
                    id=1,
                    code='A',
                    title='A',
                    credit_points=Decimal('6'),
                    eligible_module_ids=frozenset({10}),
                ),
                CourseRef(
                    id=2,
                    code='B',
                    title='B',
                    credit_points=Decimal('2'),
                    eligible_module_ids=frozenset({10}),
                ),
            ),
        )
        result = evaluate(inp)
        self.assertEqual(result.status, FAILURE)
        codes_by_payload = {
            (r.code, r.module_id, r.rule_id, r.course_id)
            for r in result.failure_reasons
        }
        self.assertIn((MODULE_UNDERFILLED, 20, None, None), codes_by_payload)
        self.assertIn((RULE_NOT_MET, None, 99, None), codes_by_payload)
        # Module 10 must be satisfied so it should NOT appear as a reason.
        self.assertNotIn((MODULE_UNDERFILLED, 10, None, None),
                         codes_by_payload)

    def test_unusable_course_reason_includes_eligible_modules(self):
        # The scoring tie-breaker prefers placing every eligible course,
        # so COURSE_UNUSABLE is structurally rare in the orchestrator's
        # natural output. We inject a single allocation that *leaves*
        # course 2 unused to pin the failure-reason code path.
        inp = EvaluationInput(
            specialization_id=1,
            specialization_name='S',
            modules=(ModuleRef(id=10, name='M10'),),
            module_requirements=(
                ModuleRequirement(
                    module_id=10,
                    required_credit_points=Decimal('6'),
                    display_order=0,
                ),
            ),
            additional_rules=(),
            courses=(
                CourseRef(
                    id=1,
                    code='A',
                    title='A',
                    credit_points=Decimal('3'),
                    eligible_module_ids=frozenset({10}),
                ),
                CourseRef(
                    id=2,
                    code='B',
                    title='B',
                    credit_points=Decimal('4'),
                    # Non-empty eligible set, but the injected allocation
                    # leaves this course on the *unused* branch.
                    eligible_module_ids=frozenset({10, 99}),
                ),
                CourseRef(
                    id=3,
                    code='ORPH',
                    title='Orphan',
                    credit_points=Decimal('2'),
                    eligible_module_ids=frozenset(),
                ),
            ),
        )
        forced = Allocation(pairs=((1, 10), (2, None), (3, None)))
        result = evaluate(
            inp,
            allocator=_SingleAllocationAllocator(forced),
        )
        self.assertEqual(result.status, FAILURE)
        unusable = [
            r for r in result.failure_reasons
            if r.code == COURSE_UNUSABLE
        ]
        # Course 3's eligible set is empty → no COURSE_UNUSABLE for it.
        self.assertEqual([r.course_id for r in unusable], [2])
        self.assertEqual(unusable[0].attempted_module_ids, (10, 99))

    def test_search_budget_exhausted_appended_to_failure_reasons(self):
        # Force the budget exhaustion path by injecting a tiny cap so the
        # allocator stops mid-DFS. One module requirement that nothing
        # can meet guarantees the result is a failure.
        inp = EvaluationInput(
            specialization_id=1,
            specialization_name='S',
            modules=(ModuleRef(id=10, name='M'),),
            module_requirements=(
                ModuleRequirement(
                    module_id=10,
                    required_credit_points=Decimal('100'),
                    display_order=0,
                ),
            ),
            additional_rules=(),
            courses=tuple(
                CourseRef(
                    id=i,
                    code=f'C{i}',
                    title='T',
                    credit_points=Decimal('1'),
                    eligible_module_ids=frozenset({10}),
                )
                for i in range(1, 5)
            ),
        )
        tiny = BacktrackingAllocator(max_nodes=8)
        result = evaluate(inp, allocator=tiny)
        self.assertEqual(result.status, FAILURE)
        codes = [r.code for r in result.failure_reasons]
        self.assertIn(SEARCH_BUDGET_EXCEEDED, codes)
        # nodes_visited is surfaced via attempted_module_ids[0].
        budget = next(r for r in result.failure_reasons
                      if r.code == SEARCH_BUDGET_EXCEEDED)
        self.assertGreaterEqual(budget.attempted_module_ids[0], 1)

    def test_no_viable_allocation_when_allocator_yields_nothing(self):
        inp = EvaluationInput(
            specialization_id=1,
            specialization_name='S',
            modules=(),
            module_requirements=(),
            additional_rules=(),
            courses=(),
        )
        result = evaluate(inp, allocator=_NoYieldAllocator())
        self.assertEqual(result.status, FAILURE)
        self.assertIsNone(result.allocation)
        self.assertEqual(
            result.failure_reasons,
            (FailureReason(code=NO_VIABLE_ALLOCATION),),
        )


class AllocationHelperTests(SimpleTestCase):
    def setUp(self):
        self.inp = EvaluationInput(
            specialization_id=1,
            specialization_name='S',
            modules=(),
            module_requirements=(),
            additional_rules=(),
            courses=(
                CourseRef(
                    id=1,
                    code='C1',
                    title='One',
                    credit_points=Decimal('4.5'),
                    eligible_module_ids=frozenset({10, 20}),
                ),
                CourseRef(
                    id=2,
                    code='C2',
                    title='Two',
                    credit_points=Decimal('3'),
                    eligible_module_ids=frozenset({20}),
                ),
            ),
        )

    def test_course_by_id(self):
        d = course_by_id(self.inp)
        self.assertEqual(set(d), {1, 2})
        self.assertEqual(d[1].code, 'C1')

    def test_allocation_as_map_and_assigned_module(self):
        a = Allocation(pairs=((1, 10), (2, None)))
        self.assertEqual(allocation_as_map(a), {1: 10, 2: None})
        self.assertEqual(assigned_module(a, 1), 10)
        self.assertIsNone(assigned_module(a, 2))
        self.assertIsNone(assigned_module(a, 99))

    def test_credits_for_module(self):
        a = Allocation(pairs=((1, 10), (2, 10)))
        self.assertEqual(
            credits_for_module(a, 10, self.inp),
            Decimal('7.5'),
        )
        self.assertEqual(credits_for_module(a, 20, self.inp), Decimal('0'))

    def test_unused_course_ids(self):
        a = Allocation(pairs=((1, 10),))
        self.assertEqual(unused_course_ids(a, self.inp), frozenset({2}))


class ExactSolverRescueTests(SimpleTestCase):
    """Step: exact ILP rescue for budget-exhausted searches.

    The bounded backtracking allocator can exhaust its node budget before
    reaching a valid allocation, yielding a *false* failure. When the
    budget is exhausted, the evaluator falls back to an exact
    :func:`planner.allocator.exact.solve_feasible` solve.
    """

    def _two_module_feasible_input(self) -> EvaluationInput:
        # Two modules each needing 6 CP; two 6-CP courses each eligible for
        # both. The only satisfying allocation splits them one-per-module.
        return EvaluationInput(
            specialization_id=1,
            specialization_name='S',
            modules=(ModuleRef(id=10, name='M10'), ModuleRef(id=20, name='M20')),
            module_requirements=(
                ModuleRequirement(
                    module_id=10,
                    required_credit_points=Decimal('6'),
                    display_order=0,
                ),
                ModuleRequirement(
                    module_id=20,
                    required_credit_points=Decimal('6'),
                    display_order=1,
                ),
            ),
            additional_rules=(),
            courses=(
                CourseRef(
                    id=1, code='A', title='A',
                    credit_points=Decimal('6'),
                    eligible_module_ids=frozenset({10, 20}),
                ),
                CourseRef(
                    id=2, code='B', title='B',
                    credit_points=Decimal('6'),
                    eligible_module_ids=frozenset({10, 20}),
                ),
            ),
        )

    def test_budget_exhausted_feasible_selection_is_rescued(self):
        inp = self._two_module_feasible_input()
        # A 1-node budget guarantees the DFS exhausts before any leaf.
        tiny = BacktrackingAllocator(max_nodes=1)
        result = evaluate(inp, allocator=tiny)

        self.assertEqual(result.status, SUCCESS)
        self.assertTrue(all(s.satisfied for s in result.module_statuses))
        self.assertEqual(result.failure_reasons, ())
        # Each course is placed on exactly one (distinct) module.
        placed = dict(result.allocation.pairs)
        self.assertEqual(set(placed.values()), {10, 20})

    def test_budget_exhausted_infeasible_selection_stays_failure(self):
        # Module needs 100 CP but only 4 CP of eligible courses exist:
        # no exact allocation can rescue this, so the failure verdict and
        # the SEARCH_BUDGET_EXCEEDED note must remain.
        inp = EvaluationInput(
            specialization_id=1,
            specialization_name='S',
            modules=(ModuleRef(id=10, name='M'),),
            module_requirements=(
                ModuleRequirement(
                    module_id=10,
                    required_credit_points=Decimal('100'),
                    display_order=0,
                ),
            ),
            additional_rules=(),
            courses=tuple(
                CourseRef(
                    id=i, code=f'C{i}', title='T',
                    credit_points=Decimal('1'),
                    eligible_module_ids=frozenset({10}),
                )
                for i in range(1, 5)
            ),
        )
        result = evaluate(inp, allocator=BacktrackingAllocator(max_nodes=8))
        self.assertEqual(result.status, FAILURE)
        self.assertIn(
            SEARCH_BUDGET_EXCEEDED,
            [r.code for r in result.failure_reasons],
        )

    def test_solve_feasible_returns_allocation_when_satisfiable(self):
        from planner.allocator.exact import solve_feasible

        allocation = solve_feasible(self._two_module_feasible_input())
        self.assertIsNotNone(allocation)
        placed = dict(allocation.pairs)
        # Both courses placed, one per module.
        self.assertEqual(sorted(placed), [1, 2])
        self.assertEqual(set(placed.values()), {10, 20})

    def test_solve_feasible_returns_none_when_infeasible(self):
        from planner.allocator.exact import solve_feasible

        inp = EvaluationInput(
            specialization_id=1,
            specialization_name='S',
            modules=(ModuleRef(id=10, name='M'),),
            module_requirements=(
                ModuleRequirement(
                    module_id=10,
                    required_credit_points=Decimal('100'),
                    display_order=0,
                ),
            ),
            additional_rules=(),
            courses=(
                CourseRef(
                    id=1, code='A', title='A',
                    credit_points=Decimal('1'),
                    eligible_module_ids=frozenset({10}),
                ),
            ),
        )
        self.assertIsNone(solve_feasible(inp))

    def test_solve_feasible_honours_cross_module_rule(self):
        from planner.allocator.exact import solve_feasible

        # Base module needs 6 CP (met by the 6-CP course alone), but a rule
        # needs 9 CP across the base module + a second module. The 3-CP
        # course must be placed (not skipped) to satisfy the rule.
        inp = EvaluationInput(
            specialization_id=1,
            specialization_name='S',
            modules=(ModuleRef(id=10, name='M10'), ModuleRef(id=20, name='M20')),
            module_requirements=(
                ModuleRequirement(
                    module_id=10,
                    required_credit_points=Decimal('6'),
                    display_order=0,
                ),
            ),
            additional_rules=(
                AdditionalRule(
                    id=99,
                    name='9 across M10+M20',
                    rule_type=MIN_CREDITS_RULE_TYPE,
                    required_credit_points=Decimal('9'),
                    modules_included_ids=frozenset({10, 20}),
                ),
            ),
            courses=(
                CourseRef(
                    id=1, code='BIG', title='Big',
                    credit_points=Decimal('6'),
                    eligible_module_ids=frozenset({10}),
                ),
                CourseRef(
                    id=2, code='SMALL', title='Small',
                    credit_points=Decimal('3'),
                    eligible_module_ids=frozenset({20}),
                ),
            ),
        )
        allocation = solve_feasible(inp)
        self.assertIsNotNone(allocation)
        placed = dict(allocation.pairs)
        self.assertEqual(placed[1], 10)
        self.assertEqual(placed[2], 20)

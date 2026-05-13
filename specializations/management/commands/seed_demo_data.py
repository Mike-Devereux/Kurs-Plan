from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from courses.models import Course, CourseCategory, Module
from specializations.models import (
    AdditionalRequirementRule,
    AdditionalRequirementRuleType,
    Specialization,
    SpecializationModuleRequirement,
)


CATEGORIES = [
    {'name': 'Inorganic Chemistry', 'display_order': 10},
    {'name': 'Organic Chemistry', 'display_order': 20},
    {'name': 'Physical Chemistry', 'display_order': 30},
    {'name': 'Mathematics', 'display_order': 40},
    {'name': 'Computer Science', 'display_order': 50},
]


MODULES = [
    {'name': 'Foundations', 'description': 'Broad chemistry foundation.'},
    {'name': 'Synthesis', 'description': 'Practical and theoretical synthesis.'},
    {'name': 'Analysis', 'description': 'Analytical and characterization techniques.'},
    {'name': 'Methods', 'description': 'Mathematical methods for chemistry.'},
    {'name': 'Statistics', 'description': 'Statistical methods and data analysis.'},
]


COURSES = [
    {
        'code': 'CHE101',
        'title': 'General Chemistry I',
        'category': 'Inorganic Chemistry',
        'credit_points': Decimal('6.00'),
        'modules': ['Foundations'],
    },
    {
        'code': 'CHE201',
        'title': 'Organic Synthesis Basics',
        'category': 'Organic Chemistry',
        'credit_points': Decimal('6.00'),
        'modules': ['Foundations', 'Synthesis'],
    },
    {
        'code': 'CHE301',
        'title': 'Advanced Organic Synthesis',
        'category': 'Organic Chemistry',
        'credit_points': Decimal('4.50'),
        'modules': ['Synthesis'],
    },
    {
        'code': 'CHE220',
        'title': 'Spectroscopy & Characterization',
        'category': 'Physical Chemistry',
        'credit_points': Decimal('6.00'),
        'modules': ['Analysis'],
    },
    {
        'code': 'CHE240',
        'title': 'Instrumental Analysis Lab',
        'category': 'Physical Chemistry',
        'credit_points': Decimal('4.50'),
        'modules': ['Analysis', 'Synthesis'],
    },
    {
        'code': 'MAT210',
        'title': 'Mathematical Methods for Chemists',
        'category': 'Mathematics',
        'credit_points': Decimal('6.00'),
        'modules': ['Methods'],
    },
    {
        'code': 'MAT220',
        'title': 'Linear Algebra Applications',
        'category': 'Mathematics',
        'credit_points': Decimal('3.00'),
        'modules': ['Methods'],
    },
    {
        'code': 'STA210',
        'title': 'Statistics for Scientists',
        'category': 'Mathematics',
        'credit_points': Decimal('6.00'),
        'modules': ['Statistics'],
    },
    {
        'code': 'CSC210',
        'title': 'Data Analysis with Python',
        'category': 'Computer Science',
        'credit_points': Decimal('4.50'),
        'modules': ['Statistics', 'Methods'],
    },
]


SPECIALIZATIONS = [
    {
        'name': 'BSc Chemistry – Analytical Track',
        'description': 'Analytical-focused specialization within the BSc Chemistry programme.',
        'module_requirements': [
            {'module': 'Foundations', 'required_credit_points': Decimal('6.00'), 'display_order': 10},
            {'module': 'Synthesis', 'required_credit_points': Decimal('9.00'), 'display_order': 20},
            {'module': 'Analysis', 'required_credit_points': Decimal('6.00'), 'display_order': 30},
        ],
        'additional_rules': [
            {
                'name': 'Methods & Statistics minimum',
                'rule_type': AdditionalRequirementRuleType.MINIMUM_CREDITS_ACROSS_MODULES,
                'required_credit_points': Decimal('9.00'),
                'modules_included': ['Methods', 'Statistics'],
                'description': (
                    'At least 9 CP must come from courses counting toward '
                    'Methods or Statistics combined.'
                ),
            },
        ],
    },
    {
        'name': 'BSc Chemistry – Synthesis Track',
        'description': 'Synthesis-focused specialization within the BSc Chemistry programme.',
        'module_requirements': [
            {'module': 'Foundations', 'required_credit_points': Decimal('6.00'), 'display_order': 10},
            {'module': 'Synthesis', 'required_credit_points': Decimal('12.00'), 'display_order': 20},
            {'module': 'Analysis', 'required_credit_points': Decimal('3.00'), 'display_order': 30},
        ],
        'additional_rules': [],
    },
]


class Command(BaseCommand):
    help = (
        'Seed the database with a coherent demo dataset (categories, modules, '
        'courses, specializations, requirements, and rules) for testing the '
        'specialization checker. Safe to re-run; uses update_or_create.'
    )

    @transaction.atomic
    def handle(self, *args, **options):
        categories = self._seed_categories()
        modules = self._seed_modules()
        self._seed_courses(categories, modules)
        self._seed_specializations(modules)

        self.stdout.write(self.style.SUCCESS('Demo data seeded.'))

    def _seed_categories(self) -> dict[str, CourseCategory]:
        result: dict[str, CourseCategory] = {}
        for spec in CATEGORIES:
            obj, created = CourseCategory.objects.update_or_create(
                name=spec['name'],
                defaults={
                    'display_order': spec['display_order'],
                    'active': True,
                },
            )
            result[obj.name] = obj
            self._log('category', obj.name, created)
        return result

    def _seed_modules(self) -> dict[str, Module]:
        result: dict[str, Module] = {}
        for spec in MODULES:
            obj, created = Module.objects.update_or_create(
                name=spec['name'],
                defaults={
                    'description': spec['description'],
                    'active': True,
                },
            )
            result[obj.name] = obj
            self._log('module', obj.name, created)
        return result

    def _seed_courses(
        self,
        categories: dict[str, CourseCategory],
        modules: dict[str, Module],
    ) -> None:
        for spec in COURSES:
            course, created = Course.objects.update_or_create(
                code=spec['code'],
                defaults={
                    'title': spec['title'],
                    'description': '',
                    'credit_points': spec['credit_points'],
                    'category': categories[spec['category']],
                    'active': True,
                    'notes': '',
                },
            )
            course.modules.set([modules[name] for name in spec['modules']])
            self._log('course', course.code, created)

    def _seed_specializations(self, modules: dict[str, Module]) -> None:
        for spec in SPECIALIZATIONS:
            specialization, created = Specialization.objects.update_or_create(
                name=spec['name'],
                defaults={
                    'description': spec['description'],
                    'active': True,
                },
            )
            self._log('specialization', specialization.name, created)

            for req in spec['module_requirements']:
                _, req_created = SpecializationModuleRequirement.objects.update_or_create(
                    specialization=specialization,
                    module=modules[req['module']],
                    defaults={
                        'required_credit_points': req['required_credit_points'],
                        'display_order': req['display_order'],
                    },
                )
                self._log(
                    '  module requirement',
                    f'{specialization.name} / {req["module"]}',
                    req_created,
                )

            for rule_spec in spec['additional_rules']:
                rule, rule_created = AdditionalRequirementRule.objects.update_or_create(
                    specialization=specialization,
                    name=rule_spec['name'],
                    defaults={
                        'description': rule_spec['description'],
                        'rule_type': rule_spec['rule_type'],
                        'required_credit_points': rule_spec['required_credit_points'],
                        'active': True,
                    },
                )
                rule.modules_included.set(
                    [modules[name] for name in rule_spec['modules_included']]
                )
                self._log(
                    '  additional rule',
                    f'{specialization.name} / {rule.name}',
                    rule_created,
                )

    def _log(self, kind: str, name: str, created: bool) -> None:
        verb = 'created' if created else 'updated'
        style = self.style.SUCCESS if created else self.style.WARNING
        self.stdout.write(style(f'{verb:>7}  {kind}: {name}'))

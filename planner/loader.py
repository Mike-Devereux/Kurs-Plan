"""ORM → pure domain projection.

This module is the *only* place inside the engine that touches Django
models. Everything downstream (allocator, rules, scoring, evaluator)
operates on :class:`planner.domain.EvaluationInput` and friends, which
have no Django dependency.
"""

from __future__ import annotations

from typing import Iterable

from courses.models import Course
from specializations.models import Specialization

from .domain import (
    AdditionalRule,
    CourseRef,
    EvaluationInput,
    ModuleRef,
    ModuleRequirement,
)


def build_input(
    specialization: Specialization,
    courses: Iterable[Course],
) -> EvaluationInput:
    """Project a specialization and selected courses into an
    :class:`EvaluationInput`.

    The returned value is fully decoupled from the ORM session: it is
    safe to pass into the engine without holding any references to the
    underlying ``Specialization`` / ``Course`` / ``Module`` instances.
    """
    module_requirement_rows = list(
        specialization.module_requirements.select_related('module')
        .order_by('display_order', 'module__name')
    )

    rule_rows = list(
        specialization.additional_requirement_rules.filter(active=True)
        .prefetch_related('modules_included')
        .order_by('name')
    )

    universe_module_ids: set[int] = set()
    modules: dict[int, ModuleRef] = {}
    for row in module_requirement_rows:
        modules.setdefault(row.module_id, ModuleRef(
            id=row.module_id,
            name=row.module.name,
        ))
        universe_module_ids.add(row.module_id)
    for rule in rule_rows:
        for module in rule.modules_included.all():
            modules.setdefault(module.id, ModuleRef(
                id=module.id,
                name=module.name,
            ))
            universe_module_ids.add(module.id)

    module_requirements = tuple(
        ModuleRequirement(
            module_id=row.module_id,
            required_credit_points=row.required_credit_points,
            display_order=row.display_order,
        )
        for row in module_requirement_rows
    )

    additional_rules = tuple(
        AdditionalRule(
            id=rule.id,
            name=rule.name,
            rule_type=rule.rule_type,
            required_credit_points=rule.required_credit_points,
            modules_included_ids=frozenset(
                m.id for m in rule.modules_included.all()
            ),
        )
        for rule in rule_rows
    )

    course_refs: list[CourseRef] = []
    seen_course_ids: set[int] = set()
    for course in courses:
        if course.pk in seen_course_ids:
            continue
        seen_course_ids.add(course.pk)
        eligible_ids = frozenset(
            m.id for m in course.modules.all()
            if m.id in universe_module_ids
        )
        course_refs.append(CourseRef(
            id=course.pk,
            code=course.code,
            title=course.title,
            credit_points=course.credit_points,
            eligible_module_ids=eligible_ids,
        ))

    return EvaluationInput(
        specialization_id=specialization.pk,
        specialization_name=specialization.name,
        modules=tuple(sorted(modules.values(), key=lambda m: m.name)),
        module_requirements=module_requirements,
        additional_rules=additional_rules,
        courses=tuple(course_refs),
    )

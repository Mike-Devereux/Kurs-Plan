"""``minimum_credits_across_modules`` rule.

Sums each placed course's ``credit_points`` when its assigned module is in
``rule.modules_included_ids``. Courses on the *unused* branch
(``module_id is None``) and courses placed on modules outside the rule
are ignored.

This mirrors the ``MINIMUM_CREDITS_ACROSS_MODULES`` row of
``specializations.models.AdditionalRequirementRuleType`` but is kept as a
plain string to keep the rule layer Django-free; the loader projects the
ORM value into ``AdditionalRule.rule_type`` already.
"""

from __future__ import annotations

from decimal import Decimal

from ..domain import (
    AdditionalRule,
    AdditionalRuleStatus,
    Allocation,
    EvaluationInput,
)
from . import register

RULE_TYPE = 'minimum_credits_across_modules'


@register(RULE_TYPE)
def evaluate(
    rule: AdditionalRule,
    allocation: Allocation,
    input_: EvaluationInput,
) -> AdditionalRuleStatus:
    by_course = {c.id: c for c in input_.courses}
    achieved = Decimal('0')
    for course_id, module_id in allocation.pairs:
        if module_id is None:
            continue
        if module_id not in rule.modules_included_ids:
            continue
        course = by_course.get(course_id)
        if course is None:
            continue
        achieved += course.credit_points

    return AdditionalRuleStatus(
        rule_id=rule.id,
        required_credit_points=rule.required_credit_points,
        achieved_credit_points=achieved,
        satisfied=achieved >= rule.required_credit_points,
    )

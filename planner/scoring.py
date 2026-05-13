"""Lexicographic scoring of candidate allocations.

The evaluator (step 8) iterates over allocations produced by the
backtracking allocator and keeps the *best-so-far* by comparing scores
with the natural tuple ordering: **higher tuples win.**

The four components, in order of priority:

1. ``mandatory_modules_satisfied_count`` — count of module requirements
   whose ``satisfied`` flag is set. We don't yet have an ``is_mandatory``
   flag on :class:`~planner.domain.ModuleRequirement`; until then every
   requirement is treated as mandatory. Adding the flag later is a
   one-line change here.
2. ``rules_satisfied_count`` — count of additional rules satisfied.
3. ``negative_total_missing`` — the negated sum of unmet credit, both
   per module and per additional rule. A larger (less negative) value
   means less credit is missing overall; ``0`` is the optimum.
4. ``assigned_course_count`` — number of courses placed on some module
   (``module_id is not None``). Acts as a soft tie-breaker so we prefer
   allocations that *use* more of the student's selection.

The third component is the only one that distinguishes allocations
which are equally satisfied at the boolean level; in particular it lets
an over-filled module win over a perfectly-filled module **when the
extra credit satisfies an additional rule** (the explicit
already-satisfied-module behaviour from milestone 5).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Tuple

from .domain import (
    AdditionalRuleStatus,
    Allocation,
    EvaluationInput,
    ModuleStatus,
)

Score = Tuple[int, int, Decimal, int]


def score(
    allocation: Allocation,
    module_statuses: tuple[ModuleStatus, ...],
    rule_statuses: tuple[AdditionalRuleStatus, ...],
    input_: EvaluationInput,
) -> Score:
    """Compute a comparable :data:`Score` for ``allocation``.

    The returned tuple uses natural ordering: ``score_a > score_b`` means
    *a* is the better allocation. Pure arithmetic; no Django, no I/O.
    """
    mandatory_satisfied = sum(1 for s in module_statuses if s.satisfied)
    rules_satisfied = sum(1 for s in rule_statuses if s.satisfied)

    missing = Decimal('0')
    for s in module_statuses:
        deficit = s.required_credit_points - s.achieved_credit_points
        if deficit > 0:
            missing += deficit
    for s in rule_statuses:
        deficit = s.required_credit_points - s.achieved_credit_points
        if deficit > 0:
            missing += deficit

    assigned_courses = sum(
        1 for _course_id, module_id in allocation.pairs
        if module_id is not None
    )

    return (mandatory_satisfied, rules_satisfied, -missing, assigned_courses)

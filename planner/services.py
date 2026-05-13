"""Student-facing evaluation entry point.

``evaluate_selection`` loads a pure :class:`~planner.domain.EvaluationInput`,
runs :func:`planner.evaluator.evaluate`, and hydrates the outcome through
:func:`planner.presenter.build_check_result` for the checker template.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Iterable, Optional

from courses.models import Course, Module
from specializations.models import AdditionalRequirementRule, Specialization

from .loader import build_input


@dataclass(frozen=True)
class ModuleStatusView:
    """One module row for the result template."""

    module: Module
    required_credit_points: Decimal
    achieved_credit_points: Decimal
    satisfied: bool
    display_order: int


@dataclass(frozen=True)
class AdditionalRuleStatusView:
    """One additional-rule row for the result template."""

    rule: AdditionalRequirementRule
    rule_type_label: str
    required_credit_points: Decimal
    achieved_credit_points: Decimal
    satisfied: bool
    modules_included: tuple[Module, ...]


@dataclass(frozen=True)
class AllocationEntry:
    """One course placement in the chosen (or best-failed) allocation."""

    course: Course
    module: Optional[Module]


@dataclass(frozen=True)
class FailureReasonView:
    """Human-readable failure line + optional ORM anchors for richer UI."""

    code: str
    message: str
    module: Optional[Module] = None
    rule: Optional[AdditionalRequirementRule] = None
    course: Optional[Course] = None
    missing_credit_points: Optional[Decimal] = None
    attempted_modules: tuple[Module, ...] = ()


@dataclass(frozen=True)
class CheckResult:
    """Structured result returned to the view layer.

    ``status`` is one of:

    - ``"success"`` — requirements satisfied.
    - ``"failure"`` — best-effort allocation with reasons.
    - ``"pending"`` — reserved for defensive / transitional UI only.
    """

    status: str
    specialization: Specialization
    selected_courses: tuple[Course, ...]
    total_credit_points: Decimal
    messages: tuple[str, ...] = field(default_factory=tuple)
    module_statuses: tuple[ModuleStatusView, ...] = field(default_factory=tuple)
    additional_rule_statuses: tuple[AdditionalRuleStatusView, ...] = field(
        default_factory=tuple,
    )
    allocation: tuple[AllocationEntry, ...] = field(default_factory=tuple)
    unused_courses: tuple[Course, ...] = field(default_factory=tuple)
    failure_reasons: tuple[FailureReasonView, ...] = field(default_factory=tuple)


def evaluate_selection(
    specialization: Specialization,
    courses: Iterable[Course],
) -> CheckResult:
    """Evaluate ``courses`` against ``specialization``'s requirements."""
    from .evaluator import evaluate
    from .presenter import build_check_result

    selected = tuple(courses)
    total = sum(
        (course.credit_points for course in selected),
        start=Decimal('0'),
    )
    input_ = build_input(specialization, selected)
    result = evaluate(input_)
    return build_check_result(
        result,
        specialization,
        selected,
        total_credit_points=total,
    )

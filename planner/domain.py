"""Pure domain types for the specialization evaluation engine.

No Django imports — this module is safe to import from tests without DB
setup. The loader/evaluator/presenter use these types end-to-end.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional


# --- Engine input (wired by ``loader.build_input``) ----------


@dataclass(frozen=True)
class ModuleRef:
    """A module participating in this specialization check."""

    id: int
    name: str


@dataclass(frozen=True)
class CourseRef:
    """A course the student selected, projected for evaluation."""

    id: int
    code: str
    title: str
    credit_points: Decimal
    eligible_module_ids: frozenset[int]


@dataclass(frozen=True)
class ModuleRequirement:
    """Per-module credit requirement for the target specialization."""

    module_id: int
    required_credit_points: Decimal
    display_order: int


@dataclass(frozen=True)
class AdditionalRule:
    """Additional requirement row (cross-module, etc.)."""

    id: int
    name: str
    rule_type: str
    required_credit_points: Decimal
    modules_included_ids: frozenset[int]


@dataclass(frozen=True)
class EvaluationInput:
    """Immutable snapshot passed into ``evaluator.evaluate``."""

    specialization_id: int
    specialization_name: str
    modules: tuple[ModuleRef, ...]
    module_requirements: tuple[ModuleRequirement, ...]
    additional_rules: tuple[AdditionalRule, ...]
    courses: tuple[CourseRef, ...]


# --- Engine output (Milestone 5: built by ``evaluator.evaluate``) -----------


@dataclass(frozen=True)
class Allocation:
    """Course-to-module placement for one candidate solution.

    Each pair is ``(course_id, module_id)`` where ``module_id`` is ``None``
    when the course is unused in this allocation.
    """

    pairs: tuple[tuple[int, Optional[int]], ...]


@dataclass(frozen=True)
class ModuleStatus:
    """Achieved vs required credit for one module under an allocation."""

    module_id: int
    required_credit_points: Decimal
    achieved_credit_points: Decimal
    satisfied: bool


@dataclass(frozen=True)
class AdditionalRuleStatus:
    """Achieved vs required credit for one additional rule."""

    rule_id: int
    required_credit_points: Decimal
    achieved_credit_points: Decimal
    satisfied: bool


@dataclass(frozen=True)
class FailureReason:
    """Structured explanation for a failed or partial check.

    ``code`` is one of the constants in :mod:`planner.evaluator`
    (``MODULE_UNDERFILLED``, ``RULE_NOT_MET``, ``COURSE_UNUSABLE``,
    ``NO_VIABLE_ALLOCATION``); the other fields carry the payload
    relevant to that code (e.g. ``module_id`` + ``missing_credit_points``
    for ``MODULE_UNDERFILLED``). Unused payload fields stay ``None`` or
    empty so consumers can rely on identity-style checks.
    """

    code: str
    module_id: Optional[int] = None
    rule_id: Optional[int] = None
    course_id: Optional[int] = None
    missing_credit_points: Optional[Decimal] = None
    attempted_module_ids: tuple[int, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class EvaluationResult:
    """Full outcome of ``evaluator.evaluate`` (success or best failure)."""

    status: str
    allocation: Optional[Allocation] = None
    module_statuses: tuple[ModuleStatus, ...] = field(default_factory=tuple)
    additional_rule_statuses: tuple[AdditionalRuleStatus, ...] = field(
        default_factory=tuple,
    )
    unused_course_ids: frozenset[int] = field(default_factory=frozenset)
    failure_reasons: tuple[FailureReason, ...] = field(default_factory=tuple)

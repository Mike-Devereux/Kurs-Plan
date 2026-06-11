"""Evaluation orchestrator.

:func:`evaluate` walks every allocation produced by an allocator, dispatches
:mod:`planner.rules` evaluators against each, returns the **first complete
success** found, and otherwise the best-failed allocation scored by
:mod:`planner.scoring`. Failure reasons are constructed inline because the
orchestrator already has all the data; the presenter (step 9) should not
recompute them.

:func:`compute_module_statuses` (the step-6 helper) lives next to the
orchestrator since both operate on a single allocation.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from .allocator import default_allocator
from .allocator.base import AllocatorProtocol, credits_for_module, unused_course_ids
from .domain import (
    Allocation,
    AdditionalRuleStatus,
    EvaluationInput,
    EvaluationResult,
    FailureReason,
    ModuleStatus,
)
from .rules import REGISTRY as RULE_REGISTRY
from .scoring import Score, score

logger = logging.getLogger(__name__)

MODULE_UNDERFILLED = 'MODULE_UNDERFILLED'
RULE_NOT_MET = 'RULE_NOT_MET'
COURSE_UNUSABLE = 'COURSE_UNUSABLE'
NO_VIABLE_ALLOCATION = 'NO_VIABLE_ALLOCATION'
SEARCH_BUDGET_EXCEEDED = 'SEARCH_BUDGET_EXCEEDED'

SUCCESS = 'success'
FAILURE = 'failure'


def compute_module_statuses(
    allocation: Allocation,
    input_: EvaluationInput,
) -> tuple[ModuleStatus, ...]:
    """Per-module achieved vs required credit for ``allocation``.

    One :class:`ModuleStatus` is produced per
    :class:`~planner.domain.ModuleRequirement` row in
    ``input_.module_requirements``, in the order they appear (the loader
    sorts by ``display_order``).

    **Invariant:** a module may be *over-filled* — the engine treats
    ``achieved_credit_points >= required_credit_points`` as the
    satisfaction condition and never invalidates an allocation because a
    module exceeded its required CP. Surplus credit on a satisfied module
    is intentional: additional rules can require it (see
    :mod:`planner.rules.minimum_credits`).
    """
    statuses: list[ModuleStatus] = []
    for requirement in input_.module_requirements:
        achieved = credits_for_module(allocation, requirement.module_id, input_)
        statuses.append(ModuleStatus(
            module_id=requirement.module_id,
            required_credit_points=requirement.required_credit_points,
            achieved_credit_points=achieved,
            satisfied=achieved >= requirement.required_credit_points,
        ))
    return tuple(statuses)


def _compute_rule_statuses(
    allocation: Allocation,
    input_: EvaluationInput,
) -> tuple[AdditionalRuleStatus, ...]:
    """Dispatch each ``additional_rule`` through :data:`RULE_REGISTRY`."""
    return tuple(
        RULE_REGISTRY[rule.rule_type](rule, allocation, input_)
        for rule in input_.additional_rules
    )


def _build_failure_reasons(
    allocation: Allocation,
    module_statuses: tuple[ModuleStatus, ...],
    rule_statuses: tuple[AdditionalRuleStatus, ...],
    input_: EvaluationInput,
) -> tuple[FailureReason, ...]:
    """Construct per-row :class:`FailureReason` rows for ``allocation``.

    Module under-fills come first (in requirement order), then rule
    misses (in rule-iteration order), then unusable courses (in input
    order). Courses with an empty ``eligible_module_ids`` set are *not*
    reported as ``COURSE_UNUSABLE`` — they had no module to land on in
    this specialization and would only add noise.
    """
    reasons: list[FailureReason] = []
    for status in module_statuses:
        if not status.satisfied:
            reasons.append(FailureReason(
                code=MODULE_UNDERFILLED,
                module_id=status.module_id,
                missing_credit_points=(
                    status.required_credit_points
                    - status.achieved_credit_points
                ),
            ))
    for status in rule_statuses:
        if not status.satisfied:
            reasons.append(FailureReason(
                code=RULE_NOT_MET,
                rule_id=status.rule_id,
                missing_credit_points=(
                    status.required_credit_points
                    - status.achieved_credit_points
                ),
            ))
    placed = {cid: mid for cid, mid in allocation.pairs}
    for course in input_.courses:
        if not course.eligible_module_ids:
            continue
        if placed.get(course.id) is None:
            reasons.append(FailureReason(
                code=COURSE_UNUSABLE,
                course_id=course.id,
                attempted_module_ids=tuple(sorted(course.eligible_module_ids)),
            ))
    return tuple(reasons)


def evaluate(
    input_: EvaluationInput,
    allocator: Optional[AllocatorProtocol] = None,
) -> EvaluationResult:
    """Find the first complete success, or the best-scored failure.

    Walks ``allocator.search(input_)`` in DFS order. The first allocation
    whose module statuses **and** rule statuses are all satisfied wins
    and is returned immediately. Otherwise the best allocation by
    lexicographic :func:`planner.scoring.score` is returned with
    ``status=='failure'`` and a populated ``failure_reasons`` tuple.

    The ``allocator`` argument is injectable for unit tests; the default
    is :func:`planner.allocator.default_allocator`.
    """
    if allocator is None:
        allocator = default_allocator()

    start_ns = time.monotonic_ns()
    best: Optional[tuple[Score, Allocation, tuple[ModuleStatus, ...],
                         tuple[AdditionalRuleStatus, ...]]] = None

    for allocation in allocator.search(input_):
        module_statuses = compute_module_statuses(allocation, input_)
        rule_statuses = _compute_rule_statuses(allocation, input_)

        all_modules_ok = all(s.satisfied for s in module_statuses)
        all_rules_ok = all(s.satisfied for s in rule_statuses)
        if all_modules_ok and all_rules_ok:
            _log_summary(allocator, status=SUCCESS, start_ns=start_ns,
                         best_score=score(allocation, module_statuses,
                                          rule_statuses, input_))
            return EvaluationResult(
                status=SUCCESS,
                allocation=allocation,
                module_statuses=module_statuses,
                additional_rule_statuses=rule_statuses,
                unused_course_ids=unused_course_ids(allocation, input_),
                failure_reasons=(),
            )

        candidate_score = score(
            allocation,
            module_statuses,
            rule_statuses,
            input_,
        )
        if best is None or candidate_score > best[0]:
            best = (candidate_score, allocation, module_statuses, rule_statuses)

    budget_exhausted = bool(getattr(allocator, 'budget_exhausted', False))

    # The bounded DFS can exhaust its node budget before reaching a valid
    # allocation, producing a *false* failure. When that happens, fall back
    # to an exact ILP solve: if a fully-satisfying allocation exists it is
    # found here (no budget), otherwise the existing best-failed result
    # stands unchanged.
    if budget_exhausted:
        rescued = _attempt_exact_success(input_, start_ns)
        if rescued is not None:
            return rescued

    if best is None:
        reasons = [FailureReason(code=NO_VIABLE_ALLOCATION)]
        if budget_exhausted:
            reasons.append(_search_budget_reason(allocator))
        _log_summary(allocator, status=FAILURE, start_ns=start_ns,
                     best_score=None)
        return EvaluationResult(
            status=FAILURE,
            allocation=None,
            failure_reasons=tuple(reasons),
        )

    _, best_allocation, best_modules, best_rules = best
    reasons = list(_build_failure_reasons(
        best_allocation, best_modules, best_rules, input_,
    ))
    if budget_exhausted:
        reasons.append(_search_budget_reason(allocator))
    _log_summary(allocator, status=FAILURE, start_ns=start_ns,
                 best_score=best[0])
    return EvaluationResult(
        status=FAILURE,
        allocation=best_allocation,
        module_statuses=best_modules,
        additional_rule_statuses=best_rules,
        unused_course_ids=unused_course_ids(best_allocation, input_),
        failure_reasons=tuple(reasons),
    )


def _attempt_exact_success(
    input_: EvaluationInput,
    start_ns: int,
) -> Optional[EvaluationResult]:
    """Exact ILP rescue for budget-exhausted searches.

    Returns a ``SUCCESS`` :class:`EvaluationResult` when the solver finds a
    fully-satisfying allocation, or ``None`` when no satisfying allocation
    exists or the solver is unavailable (so the caller keeps its existing
    best-failed result). Only success can be rescued: a genuine failure
    verdict is left to the existing best-failed / budget-note path.
    """
    from .allocator.exact import solve_feasible

    allocation = solve_feasible(input_)
    if allocation is None:
        return None

    module_statuses = compute_module_statuses(allocation, input_)
    rule_statuses = _compute_rule_statuses(allocation, input_)
    if not all(s.satisfied for s in module_statuses):
        return None
    if not all(s.satisfied for s in rule_statuses):
        return None

    if logger.isEnabledFor(logging.DEBUG):
        elapsed_ms = (time.monotonic_ns() - start_ns) / 1_000_000
        logger.debug(
            'planner.evaluate status=%s via=exact_ilp time_ms=%.2f',
            SUCCESS,
            elapsed_ms,
        )
    return EvaluationResult(
        status=SUCCESS,
        allocation=allocation,
        module_statuses=module_statuses,
        additional_rule_statuses=rule_statuses,
        unused_course_ids=unused_course_ids(allocation, input_),
        failure_reasons=(),
    )


def _search_budget_reason(allocator: AllocatorProtocol) -> FailureReason:
    """Build a ``SEARCH_BUDGET_EXCEEDED`` reason; ``nodes_visited`` is
    surfaced through ``attempted_module_ids`` as a single-element tuple
    so existing :class:`FailureReason` consumers don't need a new field.
    """
    nodes = int(getattr(allocator, 'nodes_visited', 0))
    return FailureReason(
        code=SEARCH_BUDGET_EXCEEDED,
        attempted_module_ids=(nodes,),
    )


def _log_summary(
    allocator: AllocatorProtocol,
    *,
    status: str,
    start_ns: int,
    best_score: Optional[Score],
) -> None:
    """``logger.debug`` summary; ``logging.basicConfig`` is *not* called
    here — production wiring decides the level. Cheap when DEBUG is off
    because ``logger.isEnabledFor(DEBUG)`` short-circuits before any
    formatting.
    """
    if not logger.isEnabledFor(logging.DEBUG):
        return
    elapsed_ms = (time.monotonic_ns() - start_ns) / 1_000_000
    logger.debug(
        'planner.evaluate status=%s nodes_visited=%s budget_exhausted=%s '
        'time_ms=%.2f best_score=%s',
        status,
        getattr(allocator, 'nodes_visited', None),
        getattr(allocator, 'budget_exhausted', None),
        elapsed_ms,
        best_score,
    )

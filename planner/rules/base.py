"""Rule-evaluator protocol.

A :class:`RuleEvaluator` is any callable that maps an
:class:`~planner.domain.AdditionalRule` and a candidate
:class:`~planner.domain.Allocation` over an
:class:`~planner.domain.EvaluationInput` to an
:class:`~planner.domain.AdditionalRuleStatus`.

Implementations live next to one another in this package (one file per
rule type) and self-register via :func:`planner.rules.register`.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..domain import (
    AdditionalRule,
    AdditionalRuleStatus,
    Allocation,
    EvaluationInput,
)

__all__ = [
    'AdditionalRule',
    'AdditionalRuleStatus',
    'Allocation',
    'EvaluationInput',
    'RuleEvaluator',
]


@runtime_checkable
class RuleEvaluator(Protocol):
    def __call__(
        self,
        rule: AdditionalRule,
        allocation: Allocation,
        input_: EvaluationInput,
    ) -> AdditionalRuleStatus:
        ...

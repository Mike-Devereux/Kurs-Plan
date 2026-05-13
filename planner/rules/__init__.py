"""Additional-rule evaluator registry.

``REGISTRY`` is the single dispatch table from ``rule.rule_type`` string
(as produced by ``loader.build_input``) to a :class:`RuleEvaluator`.
Concrete rule modules import :func:`register` and decorate their
``evaluate`` function; importing ``planner.rules`` is sufficient to
populate the registry because we explicitly import every concrete rule
module at the bottom of this file.
"""

from __future__ import annotations

from typing import Callable

from .base import RuleEvaluator

__all__ = ['REGISTRY', 'RuleEvaluator', 'register']

REGISTRY: dict[str, RuleEvaluator] = {}


def register(rule_type: str) -> Callable[[RuleEvaluator], RuleEvaluator]:
    """Bind ``rule_type`` to a :class:`RuleEvaluator` in :data:`REGISTRY`.

    Used as a decorator on each rule module's ``evaluate`` function.
    Raises ``ValueError`` on duplicate registration so accidental
    shadowing is caught at import time.
    """

    def decorator(fn: RuleEvaluator) -> RuleEvaluator:
        if rule_type in REGISTRY:
            raise ValueError(
                f'rule_type {rule_type!r} is already registered',
            )
        REGISTRY[rule_type] = fn
        return fn

    return decorator


# Importing concrete rule modules triggers their ``@register`` decorators.
# Keep this list explicit (no auto-discovery) so the call graph is greppable.
from . import minimum_credits  # noqa: E402,F401  (registry side effect)

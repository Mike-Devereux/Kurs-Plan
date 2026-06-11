"""Allocator protocol and pure helpers over :class:`planner.domain.Allocation`.

``Allocation`` remains a frozen value object in ``domain.py``; callers use these
functions so credit arithmetic and “which module did this course land on?”
logic stay in one place for the backtracking implementation (step 4).
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from typing import Optional, Protocol, runtime_checkable

from ..domain import Allocation, CourseRef, EvaluationInput


@runtime_checkable
class AllocatorProtocol(Protocol):
    """Yields complete candidate allocations for an evaluation input."""

    def search(self, inp: EvaluationInput) -> Iterator[Allocation]:
        ...


def course_by_id(inp: EvaluationInput) -> dict[int, CourseRef]:
    """Stable lookup for :class:`CourseRef` rows on this input."""
    return {c.id: c for c in inp.courses}


def allocation_as_map(allocation: Allocation) -> dict[int, Optional[int]]:
    """``course_id -> module_id`` with ``None`` meaning unused / skipped.

    If ``pairs`` accidentally lists the same ``course_id`` more than once,
    the last occurrence wins (callers should not emit duplicates).
    """
    return dict(allocation.pairs)


def credits_for_module(
    allocation: Allocation,
    module_id: int,
    inp: EvaluationInput,
) -> Decimal:
    """Sum ``credit_points`` for every course placed on ``module_id``."""
    by_course = course_by_id(inp)
    total = Decimal('0')
    for cid, mid in allocation.pairs:
        if mid == module_id and cid in by_course:
            total += by_course[cid].credit_points
    return total


def unused_course_ids(allocation: Allocation, inp: EvaluationInput) -> frozenset[int]:
    """Course ids that are not contributing to any module (missing pair or
    ``module_id is None``).
    """
    m = allocation_as_map(allocation)
    return frozenset(c.id for c in inp.courses if m.get(c.id) is None)

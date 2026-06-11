"""Course→module allocation search (scaffolding in step 3, logic in step 4)."""

from __future__ import annotations

from .backtracking import MAX_NODES, BacktrackingAllocator
from .base import (
    AllocatorProtocol,
    allocation_as_map,
    course_by_id,
    credits_for_module,
    unused_course_ids,
)

__all__ = [
    'AllocatorProtocol',
    'BacktrackingAllocator',
    'MAX_NODES',
    'allocation_as_map',
    'course_by_id',
    'credits_for_module',
    'default_allocator',
    'unused_course_ids',
]


def default_allocator() -> BacktrackingAllocator:
    """Default search strategy for :func:`planner.evaluator.evaluate` (step 8)."""
    return BacktrackingAllocator()

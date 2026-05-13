"""Depth-first enumeration of full course→module assignments.

Each selected course is placed on exactly one branch: either on one of its
``eligible_module_ids`` (sorted ascending for determinism) or on the
explicit *unused* branch (``module_id is None``).

**Already-satisfied modules:** every eligible module id is branched on even
when earlier courses in the DFS order have already met that module's
``SpecializationModuleRequirement``. Skipping those branches would break
additional rules that need credit counted on a module that is already
“full” for the base requirement (see product spec / Milestone 5 plan).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Optional

from ..domain import Allocation, EvaluationInput

# Step 0 recommendation — shared cap for allocator search; evaluator may
# reuse or wrap this when wiring orchestration (step 8).
MAX_NODES = 100_000


class BacktrackingAllocator:
    """Depth-first enumeration of complete :class:`Allocation` candidates.

    After :meth:`search` is consumed (fully or via ``break``), two
    instance attributes are populated for diagnostics:

    - ``nodes_visited`` — number of DFS nodes entered during the last search.
    - ``budget_exhausted`` — ``True`` if the last search stopped because
      ``nodes_visited`` exceeded :attr:`max_nodes` rather than completing
      the tree. The orchestrator uses this to surface a
      ``SEARCH_BUDGET_EXCEEDED`` failure reason.
    """

    __slots__ = ('max_nodes', 'nodes_visited', 'budget_exhausted')

    def __init__(self, max_nodes: int = MAX_NODES) -> None:
        self.max_nodes = max_nodes
        self.nodes_visited = 0
        self.budget_exhausted = False

    def search(self, inp: EvaluationInput) -> Iterator[Allocation]:
        self.nodes_visited = 0
        self.budget_exhausted = False

        courses = tuple(sorted(inp.courses, key=lambda c: c.id))
        if not courses:
            yield Allocation(pairs=())
            return

        max_nodes = self.max_nodes

        def dfs(
            index: int,
            pairs: tuple[tuple[int, Optional[int]], ...],
        ) -> Iterator[Allocation]:
            self.nodes_visited += 1
            if self.nodes_visited > max_nodes:
                self.budget_exhausted = True
                return
            if index >= len(courses):
                yield Allocation(pairs=pairs)
                return

            course = courses[index]
            # Hygiene: sorted unique module ids (``frozenset`` is already unique;
            # sorting pins DFS order across runs).
            branch_modules = sorted(course.eligible_module_ids)
            for module_id in (*branch_modules, None):
                if self.nodes_visited > max_nodes:
                    self.budget_exhausted = True
                    return
                yield from dfs(
                    index + 1,
                    pairs + ((course.id, module_id),),
                )

        yield from dfs(0, ())

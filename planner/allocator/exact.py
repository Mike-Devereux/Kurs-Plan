"""Exact course→module feasibility solver (mixed-integer programming).

The :class:`~planner.allocator.backtracking.BacktrackingAllocator` enumerates
allocations depth-first under a node budget. On large selections it can exhaust
that budget before reaching a satisfying allocation and therefore report a
*false* failure (a valid allocation existed but was never visited).

This module provides an **exact** decision procedure used by the evaluator as a
rescue when the budget is exhausted: it models the allocation as a
mixed-integer program and asks an exact solver (:func:`scipy.optimize.milp`,
backed by HiGHS) whether a fully-satisfying allocation exists. Because the
solver searches the whole space, a "no" is a *proof* of infeasibility and a
"yes" comes with a concrete satisfying allocation — so the evaluator never
reports a false failure once this runs.

Model (binary ``x[c, m]`` = "course *c* counts toward module *m*"):

- each course is used at most once:        ``sum_m x[c, m] <= 1``
- each module meets its requirement:        ``sum_c cp_c * x[c, m] >= required_m``
- each cross-module rule meets its total:   ``sum_{m in rule} sum_c cp_c * x[c, m] >= required_rule``

Objective: maximise the number of placed courses. Every feasible point already
satisfies all requirements, so this only picks *which* satisfying allocation to
return — preferring one that uses more of the student's selection, matching the
``assigned_course_count`` tie-breaker in :mod:`planner.scoring`.

Credit points are scaled to integers (``* 100``) so the ``>=`` constraints are
exact for the two-decimal ``DecimalField`` credit values.

SciPy/NumPy are hard dependencies: they are imported at module load, so an
environment without them fails fast rather than silently degrading to a
non-exact result.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

from ..domain import Allocation, EvaluationInput

_SCALE = 100


def _scaled(value: Decimal) -> int:
    """Credit ``Decimal`` (<=2 dp) as an exact integer in hundredths."""
    return int((value * _SCALE).to_integral_value())


def solve_feasible(inp: EvaluationInput) -> Optional[Allocation]:
    """Return a fully-satisfying :class:`Allocation`, or ``None``.

    ``None`` means the solver *proved* that no satisfying allocation exists.
    A non-``None`` return is guaranteed to satisfy every module requirement
    and additional rule.
    """
    courses = tuple(sorted(inp.courses, key=lambda c: c.id))

    # Decision variables: one per (course, eligible module) pair.
    var_index: dict[tuple[int, int], int] = {}
    for course in courses:
        for module_id in sorted(course.eligible_module_ids):
            var_index[(course.id, module_id)] = len(var_index)
    n = len(var_index)

    # No variables: feasible only if nothing positive is required.
    if n == 0:
        needs = any(
            _scaled(r.required_credit_points) > 0
            for r in inp.module_requirements
        ) or any(
            _scaled(r.required_credit_points) > 0 for r in inp.additional_rules
        )
        if needs:
            return None
        return Allocation(pairs=tuple((c.id, None) for c in courses))

    cp_scaled = {c.id: _scaled(c.credit_points) for c in courses}

    rows: list[list[float]] = []
    lower: list[float] = []
    upper: list[float] = []

    # (1) Each course used at most once.
    for course in courses:
        cols = [
            var_index[(course.id, m)]
            for m in course.eligible_module_ids
        ]
        if not cols:
            continue
        row = [0.0] * n
        for col in cols:
            row[col] = 1.0
        rows.append(row)
        lower.append(0.0)
        upper.append(1.0)

    # (2) Each module requirement met.
    for req in inp.module_requirements:
        row = [0.0] * n
        present = False
        for course in courses:
            key = (course.id, req.module_id)
            if key in var_index:
                row[var_index[key]] = float(cp_scaled[course.id])
                present = True
        required = float(_scaled(req.required_credit_points))
        if not present and required > 0:
            return None  # nothing can feed this module
        rows.append(row)
        lower.append(required)
        upper.append(np.inf)

    # (3) Each additional rule met (credits across its modules).
    for rule in inp.additional_rules:
        row = [0.0] * n
        present = False
        for course in courses:
            for module_id in rule.modules_included_ids:
                key = (course.id, module_id)
                if key in var_index:
                    row[var_index[key]] = float(cp_scaled[course.id])
                    present = True
        required = float(_scaled(rule.required_credit_points))
        if not present and required > 0:
            return None
        rows.append(row)
        lower.append(required)
        upper.append(np.inf)

    constraints = LinearConstraint(
        np.array(rows, dtype=float),
        np.array(lower, dtype=float),
        np.array(upper, dtype=float),
    )

    # Maximise placed courses -> minimise the negated sum.
    objective = -np.ones(n, dtype=float)
    integrality = np.ones(n, dtype=float)
    bounds = Bounds(0, 1)

    result = milp(
        c=objective,
        constraints=constraints,
        integrality=integrality,
        bounds=bounds,
    )

    if not result.success or result.x is None:
        return None

    chosen = result.x
    index_to_key = {idx: key for key, idx in var_index.items()}
    placement: dict[int, Optional[int]] = {c.id: None for c in courses}
    for idx, value in enumerate(chosen):
        if round(value) == 1:
            course_id, module_id = index_to_key[idx]
            placement[course_id] = module_id

    pairs = tuple((c.id, placement[c.id]) for c in courses)
    return Allocation(pairs=pairs)

"""Map :class:`~planner.domain.EvaluationResult` to template-facing rows.

ORM lookups are batched here (:meth:`in_bulk`, ``prefetch_related``) so the
student view does not pay N+1 costs when rendering module names, rule
labels, and allocation tables.
"""

from __future__ import annotations

from decimal import Decimal

from courses.models import Course, Module
from specializations.models import AdditionalRequirementRule, Specialization

from .domain import EvaluationResult, FailureReason
from .evaluator import (
    COURSE_UNUSABLE,
    MODULE_UNDERFILLED,
    NO_VIABLE_ALLOCATION,
    RULE_NOT_MET,
    SEARCH_BUDGET_EXCEEDED,
    SUCCESS,
)
from .services import (
    AdditionalRuleStatusView,
    AllocationEntry,
    CheckResult,
    FailureReasonView,
    ModuleStatusView,
)


def _failure_reason_view(
    reason: FailureReason,
    *,
    modules_by_id: dict[int, Module],
    rules_by_id: dict[int, AdditionalRequirementRule],
    courses_by_id: dict[int, Course],
) -> FailureReasonView:
    if reason.code == MODULE_UNDERFILLED:
        mod = modules_by_id.get(reason.module_id) if reason.module_id else None
        label = mod.name if mod else f'module #{reason.module_id}'
        missing = reason.missing_credit_points or Decimal('0')
        return FailureReasonView(
            code=reason.code,
            message=(
                f'Module "{label}" is short by {missing} credit point(s).'
            ),
            module=mod,
            missing_credit_points=missing,
        )
    if reason.code == RULE_NOT_MET:
        rule = rules_by_id.get(reason.rule_id) if reason.rule_id else None
        label = rule.name if rule else f'rule #{reason.rule_id}'
        missing = reason.missing_credit_points or Decimal('0')
        return FailureReasonView(
            code=reason.code,
            message=(
                f'Additional rule "{label}" is short by {missing} '
                'credit point(s).'
            ),
            rule=rule,
            missing_credit_points=missing,
        )
    if reason.code == COURSE_UNUSABLE:
        course = courses_by_id.get(reason.course_id) if reason.course_id else None
        code = course.code if course else f'course #{reason.course_id}'
        mods = tuple(
            modules_by_id[mid]
            for mid in reason.attempted_module_ids
            if mid in modules_by_id
        )
        if mods:
            names = ', '.join(m.name for m in mods)
            msg = (
                f'Course "{code}" was not placed toward any module; '
                f'it is eligible for: {names}.'
            )
        else:
            msg = f'Course "{code}" was not placed toward any module.'
        return FailureReasonView(
            code=reason.code,
            message=msg,
            course=course,
            attempted_modules=mods,
        )
    if reason.code == NO_VIABLE_ALLOCATION:
        return FailureReasonView(
            code=reason.code,
            message='No candidate allocation could be enumerated.',
        )
    if reason.code == SEARCH_BUDGET_EXCEEDED:
        nodes = (
            reason.attempted_module_ids[0]
            if reason.attempted_module_ids else None
        )
        if nodes is not None:
            msg = (
                f'Search stopped after {nodes} candidate allocations; '
                'the result above is the best one found so far.'
            )
        else:
            msg = (
                'Search stopped before the full space was explored; '
                'the result above is the best one found so far.'
            )
        return FailureReasonView(code=reason.code, message=msg)
    return FailureReasonView(
        code=reason.code,
        message=f'Unknown issue ({reason.code}).',
    )


def build_check_result(
    result: EvaluationResult,
    specialization: Specialization,
    courses: tuple[Course, ...],
    *,
    total_credit_points: Decimal,
) -> CheckResult:
    """Hydrate ``result`` with ORM objects for the checker template."""
    courses_by_id: dict[int, Course] = {c.pk: c for c in courses}

    module_ids: set[int] = set()
    for st in result.module_statuses:
        module_ids.add(st.module_id)
    if result.allocation:
        for _cid, mid in result.allocation.pairs:
            if mid is not None:
                module_ids.add(mid)
    for r in result.failure_reasons:
        module_ids.update(r.attempted_module_ids)
        if r.module_id is not None:
            module_ids.add(r.module_id)

    rule_ids = {st.rule_id for st in result.additional_rule_statuses}
    for r in result.failure_reasons:
        if r.rule_id is not None:
            rule_ids.add(r.rule_id)

    rules_by_id: dict[int, AdditionalRequirementRule] = {}
    if rule_ids:
        rules_by_id = {
            r.pk: r
            for r in AdditionalRequirementRule.objects.filter(
                specialization_id=specialization.pk,
                pk__in=rule_ids,
            ).prefetch_related('modules_included')
        }

    for rule in rules_by_id.values():
        for m in rule.modules_included.all():
            module_ids.add(m.pk)

    modules_by_id = Module.objects.in_bulk(module_ids)

    req_by_module_id = {
        r.module_id: r
        for r in specialization.module_requirements.select_related('module')
    }

    module_rows: list[ModuleStatusView] = []
    for st in result.module_statuses:
        req = req_by_module_id.get(st.module_id)
        mod = modules_by_id.get(st.module_id) or (req.module if req else None)
        if mod is None:
            continue
        display_order = req.display_order if req else 0
        module_rows.append(ModuleStatusView(
            module=mod,
            required_credit_points=st.required_credit_points,
            achieved_credit_points=st.achieved_credit_points,
            satisfied=st.satisfied,
            display_order=display_order,
        ))
    module_rows.sort(key=lambda v: (v.display_order, v.module.name))

    rule_rows: list[AdditionalRuleStatusView] = []
    for st in result.additional_rule_statuses:
        rule = rules_by_id.get(st.rule_id)
        if rule is None:
            continue
        included = tuple(
            sorted(
                (modules_by_id[m.pk] for m in rule.modules_included.all()
                 if m.pk in modules_by_id),
                key=lambda m: m.name,
            )
        )
        rule_rows.append(AdditionalRuleStatusView(
            rule=rule,
            rule_type_label=rule.get_rule_type_display(),
            required_credit_points=st.required_credit_points,
            achieved_credit_points=st.achieved_credit_points,
            satisfied=st.satisfied,
            modules_included=included,
        ))
    rule_rows.sort(key=lambda v: v.rule.name)

    allocation_entries: list[AllocationEntry] = []
    if result.allocation:
        def _allocation_pair_sort_key(pair: tuple[int, int | None]) -> tuple[str, str]:
            course_id, mid = pair
            course = courses_by_id[course_id]
            if mid is None:
                module_name = '\uffff'  # unused rows after assigned modules
            else:
                mod = modules_by_id.get(mid)
                module_name = mod.name if mod else ''
            return (module_name, course.code)

        sorted_pairs = sorted(
            result.allocation.pairs,
            key=_allocation_pair_sort_key,
        )
        previous_module_id: object = ...
        for course_id, mid in sorted_pairs:
            c = courses_by_id.get(course_id)
            if c is None:
                continue
            mod = modules_by_id.get(mid) if mid is not None else None
            module_block_start = (
                previous_module_id is not ...
                and mid != previous_module_id
            )
            allocation_entries.append(AllocationEntry(
                course=c,
                module=mod,
                module_block_start=module_block_start,
            ))
            previous_module_id = mid

    unused: list[Course] = []
    for cid in sorted(
        result.unused_course_ids,
        key=lambda i: courses_by_id[i].code,
    ):
        c = courses_by_id.get(cid)
        if c is not None:
            unused.append(c)

    failure_views = tuple(
        _failure_reason_view(
            r,
            modules_by_id=modules_by_id,
            rules_by_id=rules_by_id,
            courses_by_id=courses_by_id,
        )
        for r in result.failure_reasons
    )

    if result.status == SUCCESS:
        messages = (
            'All specialization requirements checked for this selection '
            'are satisfied.',
        )
    else:
        messages = (
            'This selection does not satisfy all requirements. '
            'See the summary below.',
        )

    return CheckResult(
        status=result.status,
        specialization=specialization,
        selected_courses=courses,
        total_credit_points=total_credit_points,
        messages=messages,
        module_statuses=tuple(module_rows),
        additional_rule_statuses=tuple(rule_rows),
        allocation=tuple(allocation_entries),
        unused_courses=tuple(unused),
        failure_reasons=failure_views,
    )

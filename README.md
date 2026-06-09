# Kurs-Plan

A Django application that lets students check whether a selected set of courses can satisfy the requirements for a chosen degree specialization.

See [SPEC.md](SPEC.md) for product requirements and [DEVELOPMENT.md](DEVELOPMENT.md) for implementation decisions.

## Evaluation algorithm

When a student submits a specialization and a set of courses, the engine in `planner/` decides whether the requirements can be met. The logic is deterministic, data-driven, and separated from the web layer.

### Overview

The problem is **course-to-module assignment under constraints**. Each course awards a fixed number of credit points and may count toward one or more modules. A specialization defines:

1. **Per-module requirements** — minimum credit points required in each module.
2. **Additional rules** — cross-module requirements (for example, at least 9 credits across Methods and Statistics combined).

Because a course can be eligible for multiple modules, the engine must try different ways of assigning each course to exactly one module (or leaving it unused) and then check whether all requirements are satisfied.

### Step 1 — Build evaluation input

`loader.build_input` projects the ORM data into pure domain types (`EvaluationInput`):

- Load the specialization's module requirements (ordered by `display_order`) and active additional rules.
- Build the set of **relevant module IDs** — modules referenced by either kind of requirement.
- For each selected course, compute **eligible module IDs** as the intersection of the course's modules with that relevant set.
- Deduplicate courses by ID.

A course whose modules do not overlap the specialization's requirement universe has an empty eligible set and can never be placed.

### Step 2 — Enumerate allocations (backtracking search)

`BacktrackingAllocator` performs a depth-first search over complete assignments. Courses are processed in ascending ID order for determinism.

For each course, the allocator branches on:

- every eligible module ID (sorted ascending), or
- **unused** (`module_id = None`).

Each course appears at most once in an allocation. The search does **not** prune branches where a module's per-module requirement is already met — surplus credit on a satisfied module is allowed and may be needed to satisfy additional cross-module rules (see SPEC §6).

The search is capped at 100,000 visited nodes (`MAX_NODES`). If the budget is exceeded, evaluation continues with whatever allocations were explored and may attach a `SEARCH_BUDGET_EXCEEDED` failure reason.

### Step 3 — Score each allocation

For every complete allocation, the evaluator computes:

**Module statuses** (`compute_module_statuses`):

```
for each module_requirement:
    achieved = sum(credit_points for courses placed on that module)
    satisfied = (achieved >= required_credit_points)
```

A module is satisfied when achieved credits meet or exceed the requirement; over-filling is permitted.

**Additional rule statuses** (dispatched via `planner.rules.REGISTRY`):

The implemented rule type `minimum_credits_across_modules` sums credit points for courses placed on any module in the rule's `modules_included` set:

```
achieved = sum(credit_points for course placed on module in rule.modules_included)
satisfied = (achieved >= rule.required_credit_points)
```

Courses placed on modules outside the rule, or left unused, do not contribute.

### Step 4 — Decide success or best failure

The evaluator walks allocations in DFS order:

```
best = None

for each allocation in allocator.search(input):
    module_statuses = compute_module_statuses(allocation)
    rule_statuses = evaluate_additional_rules(allocation)

    if all module_statuses satisfied AND all rule_statuses satisfied:
        return SUCCESS with this allocation   # first complete solution wins

    candidate_score = score(allocation, module_statuses, rule_statuses)
    if best is None OR candidate_score > best.score:
        best = (candidate_score, allocation, module_statuses, rule_statuses)

if best is None:
    return FAILURE with NO_VIABLE_ALLOCATION

return FAILURE with best allocation and structured failure reasons
```

**Scoring** (`planner.scoring.score`) uses lexicographic tuple comparison — higher tuples are better:

| Priority | Component | Meaning |
|----------|-----------|---------|
| 1 | `mandatory_modules_satisfied_count` | Number of per-module requirements met |
| 2 | `rules_satisfied_count` | Number of additional rules met |
| 3 | `-total_missing_credits` | Negated sum of credit shortfalls across modules and rules |
| 4 | `assigned_course_count` | Number of courses placed on a module (tie-breaker) |

When no allocation fully satisfies all requirements, the allocation with the highest score is returned as the **best failed solution**.

### Step 5 — Explain failures

For the best failed allocation, the evaluator builds `failure_reasons`:

- `MODULE_UNDERFILLED` — a module's achieved credits fall short of its requirement (includes missing credit amount).
- `RULE_NOT_MET` — an additional rule's achieved credits fall short (includes missing credit amount).
- `COURSE_UNUSABLE` — a course had eligible modules but was left unused in the best allocation.
- `NO_VIABLE_ALLOCATION` — no allocations were produced (for example, empty course list with unsatisfiable requirements).
- `SEARCH_BUDGET_EXCEEDED` — the node budget was hit before the search completed.

### Entry point

The student-facing path is:

```
evaluate_selection(specialization, courses)
  → build_input(...)          # ORM → EvaluationInput
  → evaluate(input_)          # search + score + decide
  → build_check_result(...)   # hydrate for templates
```

### Design properties

- **Deterministic** — fixed course ordering, sorted module branches, first success returned in DFS order.
- **Explainable** — every outcome includes per-module and per-rule credit totals plus structured failure reasons.
- **Django-free core** — allocation, rules, scoring, and evaluation operate on pure domain types; only `loader.build_input` touches the ORM.

### Pseudocode (full pipeline)

```
function evaluate_selection(specialization, selected_courses):
    input = build_input(specialization, selected_courses)
    return evaluate(input)

function build_input(specialization, courses):
    module_requirements = specialization.module_requirements ordered by display_order
    additional_rules = specialization.active additional rules
    relevant_modules = modules referenced by either requirement type

    course_refs = []
    for course in unique(courses):
        eligible = intersection(course.modules, relevant_modules)
        course_refs.append(CourseRef(course, eligible))

    return EvaluationInput(module_requirements, additional_rules, course_refs)

function backtracking_search(courses sorted by id):
    function dfs(index, pairs):
        if budget_exceeded: return
        if index == len(courses):
            yield Allocation(pairs)
            return

        course = courses[index]
        for module_id in sorted(course.eligible_modules) + [None]:
            dfs(index + 1, pairs + [(course.id, module_id)])

    dfs(0, [])

function evaluate(input):
    best = None
    for allocation in backtracking_search(input.courses):
        module_statuses = per-module achieved vs required credits
        rule_statuses = apply each additional rule evaluator

        if all satisfied in module_statuses and rule_statuses:
            return success(allocation, module_statuses, rule_statuses)

        s = lexicographic_score(module_statuses, rule_statuses, allocation)
        if best is None or s > best.score:
            best = (s, allocation, module_statuses, rule_statuses)

    if best is None:
        return failure(NO_VIABLE_ALLOCATION)
    return failure(best.allocation, build_failure_reasons(best))
```

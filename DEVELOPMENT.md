# DEVELOPMENT.md

# Development Decisions

## 1. Technology Stack

### Backend Framework

Use:

- Django

Reason:

- Strong admin interface
- Good relational database support
- Well suited to rule-driven applications

---

### Programming Language

Use:

- Python

Reason:

- Good for rule evaluation logic
- Excellent Django support
- Easy to maintain

---

### Package and Environment Management

Use:

- uv

Example commands:

```bash
uv init
uv add django
uv run django-admin startproject config .
uv run python manage.py runserver
```

---

### Database

During development:

- SQLite

Production:

- PostgreSQL

Reason:

- SQLite is simple during early development.
- PostgreSQL is better for production reliability and scalability.

---

### Frontend

Use:

- Django templates
- HTMX (adopted)

Reason:

- Simple and fast to build
- Avoids unnecessary frontend complexity initially

HTMX is used in the admin dashboard (modal add/edit/delete with out-of-band
list refreshes) and on the student checker page (the category description
info-icon toggle).

---

## 2. Suggested Django App Structure

```text
Kurs-Plan/
├── kurs_plan/          # project package (settings, root urls, wsgi/asgi)
├── courses/            # CourseCategory, Module, Course
├── specializations/    # Specialization, requirements, additional rules, seed cmd
├── planner/            # evaluation engine + student checker
├── manage/             # custom admin dashboard (staff-only CRUD)
├── webtool_template/   # vendored shared site shell (header/footer/banner)
├── templates/
├── static/
├── manage.py
├── pyproject.toml
└── README.md
```

---

## 3. Data Modeling Decisions

### Credit Points

Use `DecimalField` instead of `FloatField`.

Recommended:

```python
credit_points = models.DecimalField(max_digits=5, decimal_places=2)
```

Reason:

- Supports values such as `4.5`
- Avoids floating point rounding errors

---

### Course Categories

Suggested model:

```python
class CourseCategory(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    display_order = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)
```

`display_order` has a uniqueness constraint
(`unique_course_category_display_order`); the model provides a
`lowest_unused_display_order()` helper to suggest the next free value.
`description` is optional and, when set, is surfaced to students via an
info-icon on the course-selection page.

Courses should reference categories using:

```python
category = models.ForeignKey(
    CourseCategory,
    on_delete=models.PROTECT
)
```

Reason:

- Allows admin-managed dropdown categories
- Supports visual grouping of courses

---

### Course-to-Module Relationship

Courses may count toward multiple modules.

Use:

```python
modules = models.ManyToManyField(Module)
```

---

### Specialization Requirements

Use separate requirement models instead of hardcoded rules.

Example:

```python
class SpecializationModuleRequirement(models.Model):
    specialization = models.ForeignKey(Specialization, on_delete=models.CASCADE)
    module = models.ForeignKey(Module, on_delete=models.PROTECT)
    required_credit_points = models.DecimalField(max_digits=5, decimal_places=2)
    display_order = models.PositiveIntegerField(default=0)
```

Cross-module rules are modelled separately by `AdditionalRequirementRule`,
which carries a many-to-many `modules_included` relation to `Module` so a
single rule can span several modules (e.g. "at least 9 credits across Methods
and Statistics").

---

## 4. Evaluation Engine Decisions

### Separate Logic from Views

Structure:

```text
planner/
├── domain.py        # pure dataclasses (EvaluationInput, Allocation, ...)
├── loader.py        # ORM → EvaluationInput projection
├── allocator/       # search strategies
│   ├── base.py          # protocol + credit helpers
│   ├── backtracking.py  # bounded depth-first enumeration
│   └── exact.py         # exact MILP rescue (scipy.optimize.milp)
├── rules/           # additional-rule evaluators (registry)
├── evaluator.py     # orchestration: search → score → decide
├── scoring.py       # lexicographic best-failed scoring
├── presenter.py     # EvaluationResult → template view models
└── services.py      # evaluate_selection entry point
```

---

### Deterministic Logic First

Do not use AI to decide whether requirements are met.

Reason:

- Validation must be reliable and explainable.

---

### Allocation Strategy

First pass (`allocator/backtracking.py`):

- Generate possible module assignments via depth-first enumeration
- Test combinations
- Return valid solution if found
- Otherwise return best failed solution
- Bounded by a node budget (`MAX_NODES`)

Exact rescue (`allocator/exact.py`):

- Integer linear programming **is now implemented**, using
  `scipy.optimize.milp` (HiGHS).
- It runs when the backtracking budget is exhausted, guaranteeing the
  pass/fail verdict is never a false "failure": the solver either finds a
  satisfying allocation (→ success) or proves infeasibility.
- SciPy is therefore a hard runtime dependency.

See README.md ("Evaluation algorithm", Step 4a) for the full model.

---

### Best Failed Solution

If no valid solution exists, return the closest failed solution.

Possible scoring criteria:

- Missing credit points
- Number of satisfied modules
- Number of satisfied additional rules
- Number of unused courses

---

## 5. Testing Decisions

Use Django's built-in testing framework.

Test:

- Decimal credit calculations
- Module allocation
- Additional grouped-credit rules
- Multi-module course assignment
- Best failed solution logic

---

## 6. Admin Interface Decisions

Create custom admin page to contain workflow

On the page admins can:

- See a box with a list of existing course categories
- Add/edit/delete course categories in the box

- See another box with a list of existing courses
- Add/edit/delete courses in the box

- See another box with a list of existing modules
- Add/edit/delete modules in the box

-See another box with a list of existing course specializations
- Add/edit/delete specializations

- See another box with a list of editable page texts (`SiteText`)
- Edit the content of each page text (e.g. the student checker subtitle)

The add/edit workflow should change depending on the object type, so:
- in the case of course categories the properties are set, including an optional `description`
- in the case of courses properties are set, plus there is a dropdown with a list of current course categories, where one must be selected, plus a dropdown for modules, where one or more modules must be selected
- in the case of modules only properties are set
- in the case of specializations properties are set, plus module requirements and additional requirement rules. For module requirements, it should be possible to add/edit/delete rows with one rule per row. In each row a unique module must be selected from a dropdown and a corresponding required_credit_points must be entered. For additional requirement rules, it should be possible to similarly add/edit/delete one per row.
- in the case of page texts only the content is edited; the key is a fixed identifier and is not user-editable.


---

## 7. Initial Development Milestones

1. Project setup
2. Core models
3. Admin management
4. Student course selection + result page
5. Evaluation engine
6. Automated tests

---

## 8. Development Principles

- Keep rules data-driven
- Avoid hardcoding specialization logic
- Use Decimal values for credit points
- Keep evaluation logic separate from views
- Prioritize explainable results
- Start simple and extend later

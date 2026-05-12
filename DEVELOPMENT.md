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

Initial version:

- Django templates

Optional enhancement:

- HTMX

Reason:

- Simple and fast to build
- Avoids unnecessary frontend complexity initially

---

## 2. Suggested Django App Structure

```text
degree_checker/
├── config/
├── courses/
├── specializations/
├── planner/
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
    name = models.CharField(max_length=255)
    display_order = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)
```

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
```

---

## 4. Evaluation Engine Decisions

### Separate Logic from Views

Recommended structure:

```text
planner/
├── evaluator.py
├── allocation.py
├── scoring.py
└── result.py
```

---

### Deterministic Logic First

Do not use AI to decide whether requirements are met.

Reason:

- Validation must be reliable and explainable.

---

### Allocation Strategy

Initial approach:

- Generate possible module assignments
- Test combinations
- Return valid solution if found
- Otherwise return best failed solution

Possible future optimization:

- Integer linear programming

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

Use Django Admin initially.

Reason:

- Fast to implement
- Good enough for trusted admin users

---

## 7. Initial Development Milestones

1. Project setup
2. Core models
3. Admin management
4. Student course selection page
5. Evaluation engine
6. Result page
7. Automated tests

---

## 8. Development Principles

- Keep rules data-driven
- Avoid hardcoding specialization logic
- Use Decimal values for credit points
- Keep evaluation logic separate from views
- Prioritize explainable results
- Start simple and extend later

# SPEC.md

# Course Specialization Checker Specification

## 1. Purpose

The tool allows students to check whether a selected set of courses can satisfy the requirements for a chosen degree specialization.

Students can use the tool without logging in. Admin users can log in to manage courses, modules, specializations, course categories, and specialization requirement rules.

---

## 2. User Roles

## 2.1 Student User

Students can:

- Access the tool without logging in.
- Select a target specialization.
- Select courses from a course list.
- Submit their selected courses for checking.
- View whether their selected courses satisfy the chosen specialization.
- View a valid course-to-module allocation if requirements are met.
- View the best failed solution and reasons for failure if requirements are not met.

Students cannot:

- Save official degree records.
- Edit course data.
- Edit modules.
- Edit specializations.
- Edit requirement rules.

---

## 2.2 Admin User

Admins can:

- Log in.
- Add, edit, and remove courses.
- Add, edit, and remove modules.
- Add, edit, and remove specializations.
- Add, edit, and remove course categories.
- Define which modules each course can count toward.
- Define specialization-specific module credit requirements.
- Define additional credit-point rules.
- Edit admin-managed page texts (for example, the student checker page subtitle).

---

# 3. Core Data Objects

## 3.1 Course

A course represents a selectable teaching unit.

Fields:

- `code`
- `title`
- `description`
- `credit_points`
- `category`
- `modules`
- `active`
- `notes`

Rules:

- `credit_points` must be stored as a fixed-precision decimal type (`DecimalField`, 2 decimal places) so that half credit points (e.g. `4.5`) are represented exactly without floating-point rounding error.
- `code`s are unique
- Each course belongs to one category.
- Each course can count toward one or more modules.
- In a specialization check, each course should normally be counted only once unless later rules explicitly allow otherwise.

---

## 3.2 Course Category

Course categories are used to visually group courses on the student-facing course selection page.

Fields:

- `name`
- `description`
- `display_order`
- `active`

Rules:

- Categories are managed by admins.
- Courses must select from existing categories using a dropdown.
- Categories should be fixed choices for normal course editing.
- Categories are used for display grouping only unless later rules explicitly use them for validation.
- `description` is optional. When present, the student course-selection page shows an information icon next to the category title that reveals the description when clicked.

Example categories:

- Physical Chemistry
- Organic Chemistry
- Inorganic Chemistry
- Medicinal Chemistry
- Mathematics
- Computer Science

---

## 3.3 Module

A module represents a requirement area into which courses may be assigned.

Fields:

- `name`
- `description`
- `active`

---

## 3.4 Specialization

A specialization represents the target degree pathway a student wants to satisfy.

Fields:

- `name`
- `description`
- `active`

---

## 3.5 Specialization Module Requirement

Defines how many credit points are required in a module for a specific specialization.

Fields:

- `specialization`
- `module`
- `required_credit_points`
- `display_order`

Rules:

- `required_credit_points` must support float values.
- Module requirements may vary by specialization.

---

## 3.6 Additional Requirement Rule

Represents rules beyond simple module credit totals.

Fields:

- `specialization`
- `name`
- `description`
- `rule_type`
- `modules_included`
- `required_credit_points`
- `active`

Rules:

- `required_credit_points` must support float values.
- Rules may apply across a subset of modules.
- Rules are evaluated after or alongside module-level requirements.

---

## 3.7 Site Text

Stores short admin-editable pieces of page copy that are not tied to a specific
domain object (for example, the subtitle shown on the student checker page).

Fields:

- `key` (fixed identifier, not user-editable)
- `content`

Rules:

- Texts are managed by admins from the dashboard.
- The `key` selects where the text appears; only the `content` is edited.
- A missing or empty text simply renders nothing on the page.

---

# 4. Student Workflow

1. Student selects a specialization.
2. Student selects courses from a categorized list.
3. Student submits selected courses.
4. System evaluates specialization requirements.
5. System displays:
   - passing solution, or
   - best failed solution with explanations.

---

# 5. Evaluation Logic

The evaluation engine must:

- Receive selected courses.
- Receive selected specialization.
- Retrieve specialization rules.
- Identify all modules each course may count toward.
- Try possible allocations of selected courses to eligible modules.
- Ensure each course is normally counted only once.
- Check specialization-and-module-specific credit requirements.
- Check additional cross-module credit requirements.
- Return either:
  - a passing solution, or
  - the best failed solution with reasons.

---

# 6. Allocation Logic

Because a course may count toward multiple modules, the system must test possible course-to-module assignments.

The tool should select the allocation that best satisfies the specialization requirements.

Course credit points can be allocated to modules that already have point requirements satisfied, in order to meet AddtionalRequirementRules

---

# 7. Successful Result Output

If the specialization requirements can be met, show:

- Success status.
- Selected specialization.
- Selected courses.
- Course-to-module allocation.
- Credit total per module.
- Required credit total per module.
- Satisfied additional rules.

---

# 8. Failed Result Output

If the specialization requirements cannot be met, show:

- Failure status.
- Best attempted allocation.
- Requirements that were satisfied.
- Requirements that failed.
- Missing credit points.
- Selected courses that could not be used.
- Explanation of why no valid allocation was found.

---

# 9. Admin Interface Requirements

Admins must be able to manage:

- Courses
- Course Categories
- Modules
- Specializations
- Rules
- Page texts (`SiteText`)

---

# 10. Non-Goals for Initial Version

The first version does not need to include:

- Student accounts.
- Saved study plans.
- Official degree certification.
- Timetable conflict checking.
- Prerequisite checking.
- AI-based course recommendations.
- PDF export.
- Integration with university systems.

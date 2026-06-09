# Migration Guide — webtool_template

This guide explains how to adopt `webtool_template` in Chem-E (or a new Django project) **without breaking existing pages**. Production code under `core/` and `chem_e/` is unchanged until you follow these steps deliberately.

## Phase 0 — Install the package (no production changes)

```bash
cd /path/to/Chem-E
pip install -e ./webtool_template
```

Verify import:

```bash
python -c "import webtool_template; print(webtool_template.__version__)"
```

## Phase 1 — Wire Django settings (drop-in middleware swap)

Add to `chem_e/settings.py`:

```python
import sys
from pathlib import Path

WEBTOOL_TEMPLATE_ROOT = BASE_DIR / "webtool_template"

# Development: ensure the package is importable before pip install
sys.path.insert(0, str(WEBTOOL_TEMPLATE_ROOT / "src"))

INSTALLED_APPS += [
    "webtool_template.apps.WebtoolTemplateConfig",
]

# Replace core.middleware.GlobalHeaderBarMiddleware with:
MIDDLEWARE = [
    # ...
    "webtool_template.middleware.GlobalShellMiddleware",  # was core.middleware.GlobalHeaderBarMiddleware
    # ...
]

TEMPLATES[0]["DIRS"] += [
    WEBTOOL_TEMPLATE_ROOT / "templates",
    WEBTOOL_TEMPLATE_ROOT / "components",
]

STATICFILES_DIRS += [
    WEBTOOL_TEMPLATE_ROOT / "static",
]

WEBTOOL_TEMPLATE = {
    "PRESET": "chem_e",
    "LAYOUT_MODE": "middleware",
}
```

**Result:** All existing standalone templates continue to work unchanged. Middleware injects the same shell as before.

### Remove old middleware (when ready)

Delete or stop registering `core.middleware.GlobalHeaderBarMiddleware` to avoid double injection. The new middleware skips pages that already contain the prefixed global header marker.

## Phase 2 — Point sanitization imports at the package

```python
# Before
from core.html_sanitizer import sanitize_rich_text

# After
from webtool_template.sanitizer import sanitize_rich_text
```

Keep `core/html_sanitizer.py` as a thin re-export during transition if desired:

```python
from webtool_template.sanitizer import sanitize_rich_text  # noqa: F401
```

## Phase 3 — Migrate templates to `base.html` (recommended)

Switch `LAYOUT_MODE` to `"template"` **only after** pages extend the base layout:

```python
WEBTOOL_TEMPLATE = {
    "PRESET": "chem_e",
    "LAYOUT_MODE": "template",
}
```

### Before (current Chem-E)

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Courses</title>
</head>
<body>
    <h1>Kursliste</h1>
    ...
</body>
</html>
```

### After

```html
{% extends "webtool_template/base.html" %}

{% block title %}Courses{% endblock %}

{% block content %}
    <h1>Kursliste</h1>
    ...
{% endblock %}
```

### View helper (optional)

```python
from webtool_template.bootstrap import render_page

def course_list(request):
    return render_page(
        request,
        "core/course_list.html",
        {"courses": courses},
        page_title="Courses",
    )
```

`render_page()` injects `wt`, `webtool_home_url`, banner logos, footer text, and other shell context automatically.

## Phase 4 — Migrate auth pages

Point Django auth views at package templates, or make local templates extend the package:

```python
# settings.py
LOGIN_TEMPLATE = "webtool_template/auth/login.html"
# Or in a custom LoginView:
# template_name = "webtool_template/auth/login.html"
```

Provide URL context expected by auth templates:

```python
return render_auth_page(
    request,
    "webtool_template/auth/login.html",
    {
        "form": form,
        "home_url": "/",
        "register_url": "/register/",
        "password_reset_url": "/password-reset/",
    },
    page_title="Login",
)
```

## Phase 5 — Adopt shared components

### Back link

```django
{% include "webtool_template/partials/back_link.html" with url=back_url label="Back to courses" %}
```

### File upload field

```django
{% load static %}
<link rel="stylesheet" href="{% static 'webtool_template/css/components.css' %}">

<form method="post" enctype="multipart/form-data" data-webtool-file-upload
      data-upload-confirm="Replace existing file and grade?">
    {% csrf_token %}
    {% include "webtool_template/file_upload_field.html" with
        input_id="upload_part_1"
        input_name="upload_part_1"
        field_label="Upload solution"
        trigger_label="Choose file"
        empty_label="No file selected"
        has_existing_upload=has_upload
    %}
    <button type="submit">Submit</button>
</form>
<script src="{% static 'webtool_template/js/file-upload.js' %}"></script>
```

### Status badge

```django
{% load webtool_template_tags %}
{% status_badge "graded" "Graded" %}
```

### Footer spacer

```django
{% include "webtool_template/footer_gap.html" %}
```

## Layout modes

| Mode | When to use | Middleware | Templates |
|------|-------------|------------|-----------|
| `middleware` | Legacy standalone HTML pages | Injects shell | No `{% extends %}` required |
| `template` | New/migrated pages | Disabled | Must `{% extends "webtool_template/base.html" %}` |

## Chem-E page migration checklist

| Page group | Action |
|------------|--------|
| `course_list.html`, `course_detail.html`, … | Extend `base.html`; remove reliance on middleware margins |
| `registration/*.html` | Switch to `webtool_template/auth/*` or extend `base_auth.html` |
| `tutorial_detail.html`, `exercise_detail.html` | Include `file_upload_field.html` + `file-upload.js`; use `components.css` |
| `supervisor_course_summary.html` | Link `status.css`; replace inline status rules |
| `supervisor_tree.html` | Keep in Chem-E (Quill/editor logic is project-specific) |

## New project (greenfield)

```python
# settings.py
INSTALLED_APPS = [
    # ...
    "webtool_template.apps.WebtoolTemplateConfig",
]

WEBTOOL_TEMPLATE = {
    "PREFIX": "webtool",
    "LAYOUT_MODE": "template",
    "FOOTER_TEXT": "My Tool — support@example.org",
    "BANNER_LOGOS": {
        "left": "/static/webtool_template/logos/uni-basel-logo.svg",
    },
    "HOME_URL": "/",
    "LOGOUT_URL": "/logout/",
}
```

```python
# views.py
from webtool_template.bootstrap import render_page

def dashboard(request):
    return render_page(request, "myapp/dashboard.html", page_title="Dashboard")
```

```html
{# myapp/dashboard.html #}
{% extends "webtool_template/base.html" %}
{% block content %}
  <h1>Dashboard</h1>
{% endblock %}
```

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Templates not found | Add `webtool_template/templates` and `webtool_template/components` to `TEMPLATES["DIRS"]` |
| CSS/JS 404 | Add `webtool_template/static` to `STATICFILES_DIRS`; run `collectstatic` in production |
| Double header/footer | Set `LAYOUT_MODE: "template"` OR remove shell from template; not both |
| Wrong Home link | Set `HOME_URL_RESOLVER` or `HOME_URL` in `WEBTOOL_TEMPLATE` |
| `wt_class` unknown tag | Ensure `webtool_template` is in `INSTALLED_APPS` |

See `examples/USAGE.md` for additional copy-paste snippets.

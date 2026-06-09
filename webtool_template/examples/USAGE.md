# Example Usage — webtool_template

Copy-paste snippets for common integration patterns.

## 1. Minimal settings (Chem-E compatible middleware)

```python
# chem_e/settings.py
WEBTOOL_TEMPLATE = {
    "PRESET": "chem_e",
    "LAYOUT_MODE": "middleware",
}

MIDDLEWARE = [
    # ...
    "webtool_template.middleware.GlobalShellMiddleware",
]
```

## 2. `bootstrap.render_page` — standard content page

```python
from webtool_template.bootstrap import render_page

class CourseListView(View):
    def get(self, request):
        return render_page(
            request,
            "core/course_list.html",
            {"courses": Course.objects.filter(is_active=True)},
            page_title="Courses",
        )
```

```html
{# core/templates/core/course_list.html #}
{% extends "webtool_template/base.html" %}

{% block title %}Courses{% endblock %}

{% block content %}
<h1>Kursliste</h1>
<ul>
  {% for course in courses %}
    <li><a href="{% url 'course_detail' course.pk %}">{{ course.title }}</a></li>
  {% endfor %}
</ul>
{% endblock %}
```

## 3. `bootstrap.render_auth_page` — login

```python
from webtool_template.bootstrap import render_auth_page

def login_view(request):
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        return redirect("home")
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

## 4. `shell_context` only — class-based views

```python
from django.views.generic import TemplateView
from webtool_template.bootstrap import shell_context

class SupervisorLandingView(TemplateView):
    template_name = "core/supervisor_landing.html"

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            **shell_context(self.request),
        }
```

## 5. Sanitize rich text before `|safe`

```python
from webtool_template.sanitizer import sanitize_rich_text

variant.exercise_text = sanitize_rich_text(raw_html)
variant.save()
```

```html
<div>{{ variant.exercise_text|safe }}</div>
```

## 6. File upload component

```html
{% extends "webtool_template/base.html" %}
{% load static %}

{% block extra_css %}
  <link rel="stylesheet" href="{% static 'webtool_template/css/components.css' %}">
{% endblock %}

{% block content %}
<form method="post" enctype="multipart/form-data"
      data-webtool-file-upload
      data-upload-empty-label="keine ausgewählte Datei"
      data-upload-confirm="Möchten Sie wirklich eine neue Datei hochladen?">
  {% csrf_token %}
  <input type="hidden" name="force_replace_graded_upload" value="0">
  {% include "webtool_template/file_upload_field.html" with
      input_id="upload_part_42"
      input_name="upload_part_42"
      field_label="Neue Datei hochladen"
      trigger_label="Auswählen"
      has_existing_upload=True
  %}
  <button type="submit">Senden</button>
</form>
{% endblock %}

{% block extra_js %}
  <script src="{% static 'webtool_template/js/file-upload.js' %}"></script>
{% endblock %}
```

## 7. Status colors in a grading table

```html
{% load static %}

{% block extra_css %}
  <link rel="stylesheet" href="{% static 'webtool_template/css/status.css' %}">
{% endblock %}

{% block content %}
<p>
  <span class="cell-missing">- = No submission</span> |
  <span class="cell-ungraded">Ungraded</span> |
  <span class="cell-graded">Graded</span>
</p>
<table class="webtool-table" border="1" cellpadding="4">
  <tr>
    <td class="cell-graded">8.50</td>
    <td class="cell-ungraded">Ungraded</td>
    <td class="cell-missing">-</td>
  </tr>
</table>
{% endblock %}
```

## 8. Template tags

```html
{% load webtool_template_tags %}

{% back_link "/supervisor/" "Back to supervisor home" %}
{% status_badge "ungraded" "Pending review" %}
```

## 9. Custom home URL resolver

```python
# myapp/navigation.py
def home_url_for_user(request):
    if request.user.is_staff:
        return "/admin/"
    return "/dashboard/"
```

```python
# settings.py
WEBTOOL_TEMPLATE = {
    "HOME_URL_RESOLVER": "myapp.navigation.home_url_for_user",
}
```

## 10. CSRF helper in custom JavaScript

```html
<script src="{% static 'webtool_template/js/csrf.js' %}"></script>
<script>
  fetch("/api/example/", {
    method: "POST",
    headers: {"X-CSRFToken": webtoolGetCsrfToken()},
  });
</script>
```

## 11. Example page template (bundled)

The package includes `webtool_template/examples/simple_page.html`:

```python
from webtool_template.bootstrap import render_page

return render_page(
    request,
    "webtool_template/examples/simple_page.html",
    {
        "page_title": "Demo",
        "back_url": "/",
        "back_label": "Home",
        "content_html": "<p>Hello from webtool_template.</p>",
    },
)
```

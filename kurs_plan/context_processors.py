"""Template context shared across the site."""

from __future__ import annotations

from django.templatetags.static import static

from webtool_template.bootstrap import shell_context


def webtool_shell(request):
    """Inject header, banner, footer, and theme variables."""
    context = shell_context(request)
    context['webtool_banner_logo_left'] = static(
        'webtool_template/logos/uni-basel-logo.svg'
    )
    return context

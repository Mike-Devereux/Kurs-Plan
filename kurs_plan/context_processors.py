"""Template context shared across the site."""

from __future__ import annotations

from webtool_template.bootstrap import shell_context


def webtool_shell(request):
    """Inject header, banner, footer, and theme variables."""
    return shell_context(request)

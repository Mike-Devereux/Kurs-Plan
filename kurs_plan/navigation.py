"""URL helpers for the shared webtool shell."""

from __future__ import annotations

from django.urls import reverse


def home_url_for_request(request) -> str:
    """Resolve the shell *Home* link for the current page."""
    if request.path.startswith('/manage/'):
        if request.user.is_authenticated:
            return reverse('manage:dashboard')
        return reverse('manage:login')
    return reverse('planner:checker')

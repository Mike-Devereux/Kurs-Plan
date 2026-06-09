"""Helpers for rendering pages with the standard webtool layout."""

from __future__ import annotations

from typing import Any

from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string

from .conf import TemplateNamespace, get_config, resolve_home_url


def shell_context(request, **extra: Any) -> dict[str, Any]:
    """Build template context shared by base layouts and partials."""
    config = get_config()
    ns = TemplateNamespace(config)
    logos = config.get("BANNER_LOGOS") or {}
    context = {
        "wt": ns,
        "webtool_config": config,
        "webtool_home_url": resolve_home_url(request),
        "webtool_logout_url": config.get("LOGOUT_URL", "/logout/"),
        "webtool_footer_text": config.get("FOOTER_TEXT", ""),
        "webtool_banner_logo_left": logos.get("left", ""),
        "webtool_banner_logo_right": logos.get("right", ""),
        "webtool_font_urls": config.get("FONT_URLS", []),
        "webtool_root_style": ns.root_style(),
    }
    context.update(extra)
    return context


def render_page(
    request,
    template_name: str,
    context: dict[str, Any] | None = None,
    *,
    page_title: str = "",
    status: int = 200,
) -> HttpResponse:
    """Render a template with standard shell context injected.

    Use with templates that extend ``webtool_template/base.html`` and set
    ``LAYOUT_MODE`` to ``"template"`` so middleware does not double-inject chrome.
    """
    merged = shell_context(request, **(context or {}))
    if page_title:
        merged.setdefault("page_title", page_title)
    return render(request, template_name, merged, status=status)


def render_page_string(
    request,
    template_name: str,
    context: dict[str, Any] | None = None,
    *,
    page_title: str = "",
) -> str:
    """Return rendered HTML for the standard page layout."""
    merged = shell_context(request, **(context or {}))
    if page_title:
        merged.setdefault("page_title", page_title)
    return render_to_string(template_name, merged, request=request)


def render_auth_page(
    request,
    template_name: str,
    context: dict[str, Any] | None = None,
    *,
    page_title: str = "",
    status: int = 200,
) -> HttpResponse:
    """Render an auth-focused page using ``base_auth.html`` conventions."""
    merged = shell_context(request, **(context or {}))
    merged["webtool_auth_layout"] = True
    if page_title:
        merged.setdefault("page_title", page_title)
    return render(request, template_name, merged, status=status)

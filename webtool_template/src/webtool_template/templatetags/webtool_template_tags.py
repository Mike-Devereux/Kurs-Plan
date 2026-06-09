from django import template
from django.utils.html import format_html

from webtool_template.conf import TemplateNamespace, get_config

register = template.Library()


@register.simple_tag(takes_context=True)
def wt_class(context, name):
    ns = context.get("wt") or TemplateNamespace()
    return ns.cls(name)


@register.simple_tag(takes_context=True)
def wt_var(context, name):
    ns = context.get("wt") or TemplateNamespace()
    return ns.var(name)


@register.simple_tag(takes_context=True)
def webtool_shell(context):
    ns = context.get("wt") or TemplateNamespace()
    config = context.get("webtool_config") or get_config()
    home_url = context.get("webtool_home_url", config.get("HOME_URL", "/"))
    logout_url = context.get("webtool_logout_url", config.get("LOGOUT_URL", "/logout/"))
    return format_html(
        (
            '<div class="{}">'
            '<div class="{}">'
            '<nav class="{}">'
            '<a class="{}" href="{}">Home</a>'
            '<a class="{}" href="{}">Logout</a>'
            "</nav></div></div>"
        ),
        ns.cls("global-header"),
        ns.cls("global-header-inner"),
        ns.cls("global-header-links"),
        ns.cls("global-header-home"),
        home_url,
        ns.cls("global-header-logout"),
        logout_url,
    )


@register.inclusion_tag("webtool_template/partials/status_badge.html")
def status_badge(kind, label):
    return {"kind": kind, "label": label}


@register.inclusion_tag("webtool_template/partials/back_link.html")
def back_link(url, label="Back"):
    return {"url": url, "label": label}

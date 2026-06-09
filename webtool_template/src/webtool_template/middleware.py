from django.utils.deprecation import MiddlewareMixin

from .conf import TemplateNamespace, build_shell_stylesheet, get_config, resolve_home_url


def build_page_banner(ns: TemplateNamespace, config: dict) -> str:
    logos = config.get("BANNER_LOGOS") or {}
    left_logo = logos.get("left", "")
    right_logo = logos.get("right", "")
    left_img = (
        f'<img class="{ns.cls("page-banner-left-logo")}" src="{left_logo}" alt="">'
        if left_logo
        else ""
    )
    right_img = (
        f'<img class="{ns.cls("page-banner-logo")}" src="{right_logo}" alt="">'
        if right_logo
        else ""
    )
    return (
        f'<div class="{ns.cls("page-banner")}" aria-hidden="true">'
        f'<div class="{ns.cls("page-banner-inner")}">'
        f'<div class="{ns.cls("page-banner-left")}">{left_img}</div>'
        f'<div class="{ns.cls("page-banner-right")}">{right_img}</div>'
        "</div>"
        "</div>"
    )


def build_footer_bar(ns: TemplateNamespace, config: dict) -> str:
    footer_text = config.get("FOOTER_TEXT", "")
    if not footer_text:
        return ""
    return (
        f'<footer class="{ns.cls("global-footer")}">'
        f'<span class="{ns.cls("global-footer-text")}">{footer_text}</span>'
        "</footer>"
    )


def build_header_bar(ns: TemplateNamespace, request, config: dict) -> str:
    home_href = resolve_home_url(request)
    logout_url = config.get("LOGOUT_URL", "/logout/")
    return (
        f'<div class="{ns.cls("global-header")}">'
        f'<div class="{ns.cls("global-header-inner")}">'
        f'<nav class="{ns.cls("global-header-links")}">'
        f'<a class="{ns.cls("global-header-home")}" href="{home_href}">Home</a>'
        f'<a class="{ns.cls("global-header-logout")}" href="{logout_url}">Logout</a>'
        "</nav>"
        "</div>"
        "</div>"
    )


class GlobalShellMiddleware(MiddlewareMixin):
    """Inject global header, banner, footer, and shell CSS into HTML responses.

  Preserves the original Chem-E middleware behavior when ``WEBTOOL_TEMPLATE``
  uses ``PRESET: "chem_e"`` or equivalent prefix/logo/footer settings.
    """

    def process_response(self, request, response):
        config = get_config()
        if config.get("LAYOUT_MODE") != "middleware":
            return response

        content_type = response.get("Content-Type", "")
        if "text/html" not in content_type or getattr(response, "streaming", False):
            return response

        try:
            html = response.content.decode(response.charset or "utf-8")
        except (AttributeError, UnicodeDecodeError):
            return response

        ns = TemplateNamespace(config)
        header_marker = ns.cls("global-header")
        if header_marker in html:
            return response

        header_bar = build_header_bar(ns, request, config)
        page_banner = build_page_banner(ns, config)
        footer_bar = build_footer_bar(ns, config)
        style_block = build_shell_stylesheet(config)

        if "</head>" in html:
            html = html.replace("</head>", f"{style_block}</head>", 1)
        if "<body>" in html:
            html = html.replace("<body>", f"<body>{header_bar}{page_banner}", 1)
        else:
            body_start = html.find("<body")
            if body_start != -1:
                body_end = html.find(">", body_start)
                if body_end != -1:
                    html = (
                        html[: body_end + 1]
                        + header_bar
                        + page_banner
                        + html[body_end + 1 :]
                    )
        if "</body>" in html and footer_bar:
            html = html.replace("</body>", f"{footer_bar}</body>", 1)

        response.content = html.encode(response.charset or "utf-8")
        if "Content-Length" in response:
            response["Content-Length"] = str(len(response.content))
        return response

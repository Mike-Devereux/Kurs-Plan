"""Theme and shell configuration for webtool_template."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from django.conf import settings

DEFAULTS: dict[str, Any] = {
    "PREFIX": "webtool",
    "HEADER_HEIGHT": "45px",
    "HEADER_BG": "#2d373c",
    "FOOTER_HEIGHT": "45px",
    "FOOTER_BG": "#2d373c",
    "BANNER_HEIGHT": "146px",
    "BANNER_BG": "#a5d7d2",
    "CONTENT_MARGIN": "100px",
    "BANNER_LOGOS": {
        "left": "",
        "right": "",
    },
    "FOOTER_TEXT": "",
    "LOGOUT_URL": "/logout/",
    "HOME_URL": "/",
    "HOME_URL_RESOLVER": None,
    "FONT_HEADING": '"PTSerif", serif',
    "FONT_BODY": "Inter, sans-serif",
    "FONT_BODY_SIZE": "15px",
    "FONT_LINK_SIZE": "13px",
    "FONT_URLS": [],
    "LAYOUT_MODE": "middleware",
    "AUTH_USE_ARIAL": True,
}

CHEM_E_PRESET: dict[str, Any] = {
    "PREFIX": "chem-e",
    "FOOTER_TEXT": "Chem-E: michael.devereux@unibas.ch",
    "BANNER_LOGOS": {
        "left": "/media/ui/uni-basel-logo.svg",
        "right": "/media/ui/DepChe_Logo_DE_Schwarz_RGB.png",
    },
    "LOGOUT_URL": "/logout/",
    "HOME_URL_RESOLVER": "webtool_template.compat.chem_e_home_url",
}


def package_root():
    from pathlib import Path

    return Path(__file__).resolve().parents[2]


def get_config() -> dict[str, Any]:
    user_config = getattr(settings, "WEBTOOL_TEMPLATE", {})
    config = {**DEFAULTS, **user_config}
    if config.get("PRESET") == "chem_e":
        merged = {**CHEM_E_PRESET, **user_config}
        merged.pop("PRESET", None)
        config = {**DEFAULTS, **merged}
    return config


def css_class(prefix: str, name: str) -> str:
    return f"{prefix}-{name}"


def css_var(prefix: str, name: str) -> str:
    return f"--{prefix}-{name}"


def resolve_home_url(request) -> str:
    config = get_config()
    resolver_path = config.get("HOME_URL_RESOLVER")
    if resolver_path:
        module_path, function_name = resolver_path.rsplit(".", 1)
        resolver = getattr(import_module(module_path), function_name)
        return resolver(request)
    return config["HOME_URL"]


class TemplateNamespace:
    """Expose prefixed CSS classes and variables to templates."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or get_config()
        self.prefix = self.config["PREFIX"]

    def cls(self, name: str) -> str:
        return css_class(self.prefix, name)

    def var(self, name: str) -> str:
        return css_var(self.prefix, name)

    def header_class(self) -> str:
        return self.cls("global-header")

    def root_style(self) -> str:
        p = self.prefix
        return (
            f"{css_var(p, 'header-height')}: {self.config['HEADER_HEIGHT']}; "
            f"{css_var(p, 'header-bg')}: {self.config['HEADER_BG']}; "
            f"{css_var(p, 'footer-height')}: {self.config['FOOTER_HEIGHT']}; "
            f"{css_var(p, 'footer-bg')}: {self.config['FOOTER_BG']}; "
            f"{css_var(p, 'banner-height')}: {self.config['BANNER_HEIGHT']}; "
            f"{css_var(p, 'banner-bg')}: {self.config['BANNER_BG']}; "
            f"{css_var(p, 'content-margin')}: {self.config['CONTENT_MARGIN']};"
        )


def build_shell_stylesheet(config: dict[str, Any] | None = None) -> str:
    """Return inline CSS matching the original Chem-E middleware injection."""
    config = config or get_config()
    ns = TemplateNamespace(config)
    p = ns.prefix
    v = ns.var
    c = ns.cls

    return f"""
<style>
    :root {{
        {v("header-height")}: {config["HEADER_HEIGHT"]};
        {v("header-bg")}: {config["HEADER_BG"]};
        {v("footer-height")}: {config["FOOTER_HEIGHT"]};
        {v("footer-bg")}: {config["FOOTER_BG"]};
        {v("banner-height")}: {config["BANNER_HEIGHT"]};
        {v("content-margin")}: {config["CONTENT_MARGIN"]};
        {v("banner-bg")}: {config["BANNER_BG"]};
    }}
    body {{
        margin: 0;
        max-width: none !important;
        width: 100%;
        min-height: 100vh;
        display: flex;
        flex-direction: column;
    }}
    h1, h2, h3, h4, h5, h6 {{
        font-family: {config["FONT_HEADING"]};
    }}
    p {{
        font-family: {config["FONT_BODY"]};
        font-size: {config["FONT_BODY_SIZE"]};
    }}
    li {{
        font-family: {config["FONT_BODY"]};
        font-size: {config["FONT_BODY_SIZE"]};
    }}
    label {{
        font-family: {config["FONT_BODY"]};
        font-size: {config["FONT_BODY_SIZE"]};
    }}
    .{c("global-header")} {{
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        height: var({v("header-height")});
        width: 100%;
        background: var({v("header-bg")});
        z-index: 9999;
    }}
    .{c("global-header-inner")} {{
        height: 100%;
        width: 100%;
        box-sizing: border-box;
        display: flex;
        justify-content: flex-end;
        align-items: center;
        padding-left: var({v("content-margin")});
        padding-right: var({v("content-margin")});
    }}
    .{c("global-header-links")} {{
        display: flex;
        align-items: center;
        gap: 20px;
    }}
    .{c("global-header-home")},
    .{c("global-header-logout")} {{
        color: #ffffff;
        font-family: {config["FONT_BODY"]};
        font-size: {config["FONT_LINK_SIZE"]};
        text-decoration: none;
    }}
    .{c("global-header-home")}:hover,
    .{c("global-header-home")}:focus,
    .{c("global-header-logout")}:hover,
    .{c("global-header-logout")}:focus {{
        text-decoration: underline;
    }}
    .{c("page-banner")} {{
        margin-top: var({v("header-height")});
        width: 100vw;
        height: var({v("banner-height")});
        background: var({v("banner-bg")});
        box-sizing: border-box;
    }}
    .{c("page-banner-inner")} {{
        height: 100%;
        width: 100%;
        display: flex;
        justify-content: space-between;
        align-items: center;
        box-sizing: border-box;
        padding-left: var({v("content-margin")});
        padding-right: var({v("content-margin")});
    }}
    .{c("page-banner-left")},
    .{c("page-banner-right")} {{
        display: flex;
        align-items: center;
    }}
    .{c("page-banner-left-logo")},
    .{c("page-banner-logo")} {{
        display: block;
        height: 73px;
        width: auto;
    }}
    .{c("global-footer")} {{
        width: 100%;
        height: var({v("footer-height")});
        background: var({v("footer-bg")});
        display: flex;
        align-items: center;
        justify-content: flex-end;
        box-sizing: border-box;
        padding-left: var({v("content-margin")});
        padding-right: var({v("content-margin")});
        margin-top: auto;
    }}
    .{c("global-footer-text")} {{
        color: #ffffff;
        font-family: {config["FONT_BODY"]};
        font-size: {config["FONT_LINK_SIZE"]};
    }}
    body > :not(.{c("global-header")}):not(.{c("page-banner")}):not(.{c("global-footer")}) {{
        margin-left: var({v("content-margin")});
        margin-right: var({v("content-margin")});
    }}
</style>
"""

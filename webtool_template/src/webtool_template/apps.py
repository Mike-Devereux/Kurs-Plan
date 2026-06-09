from django.apps import AppConfig

from .conf import package_root


class WebtoolTemplateConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "webtool_template"
    verbose_name = "Webtool Template"

    @staticmethod
    def template_dirs():
        root = package_root()
        return [root / "templates", root / "components"]

    @staticmethod
    def static_dirs():
        return [package_root() / "static"]

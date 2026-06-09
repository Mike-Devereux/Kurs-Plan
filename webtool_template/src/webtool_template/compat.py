"""Compatibility helpers for host projects adopting webtool_template."""


def chem_e_home_url(request):
    """Mirror core.middleware.GlobalHeaderBarMiddleware._home_href_for."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return "/"
    user_role = getattr(user, "role", None)
    if user.is_superuser or user_role in {"supervisor", "administrator"}:
        return "/supervisor"
    return "/"

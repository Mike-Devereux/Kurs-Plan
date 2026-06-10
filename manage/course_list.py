from django.db.models import QuerySet

from courses.models import Course

COURSE_SORT_FIELDS = {
    'code': 'code',
    'title': 'title',
    'category': 'category__name',
    'credit_points': 'credit_points',
}

DEFAULT_COURSE_SORT = 'code'
DEFAULT_COURSE_DIRECTION = 'asc'

SESSION_SORT_KEY = 'manage_course_sort'
SESSION_DIRECTION_KEY = 'manage_course_dir'


def course_sort_state(request) -> tuple[str, str]:
    """Return validated ``(sort_key, direction)`` for the courses table."""
    sort_key = request.GET.get('course_sort') or request.session.get(
        SESSION_SORT_KEY, DEFAULT_COURSE_SORT,
    )
    if sort_key not in COURSE_SORT_FIELDS:
        sort_key = DEFAULT_COURSE_SORT

    direction = request.GET.get('course_dir') or request.session.get(
        SESSION_DIRECTION_KEY, DEFAULT_COURSE_DIRECTION,
    )
    if direction not in ('asc', 'desc'):
        direction = DEFAULT_COURSE_DIRECTION

    return sort_key, direction


def persist_course_sort(request) -> None:
    """Store sort query params in the session when the dashboard is loaded."""
    if 'course_sort' not in request.GET:
        return
    sort_key, direction = course_sort_state(request)
    request.session[SESSION_SORT_KEY] = sort_key
    request.session[SESSION_DIRECTION_KEY] = direction


def course_sort_ordering(sort_key: str, direction: str) -> list[str]:
    field = COURSE_SORT_FIELDS[sort_key]
    if direction == 'desc':
        field = f'-{field}'
    return [field, 'pk']


def courses_queryset(request) -> QuerySet[Course]:
    sort_key, direction = course_sort_state(request)
    return (
        Course.objects.select_related('category')
        .order_by(*course_sort_ordering(sort_key, direction))
    )


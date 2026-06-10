from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.db.models import ProtectedError
from django.http import HttpResponse
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.views import View


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Allow only authenticated staff users.

    Unauthenticated users are redirected to ``LOGIN_URL``; authenticated users
    without ``is_staff`` get a 403 rather than a redirect loop back to login.
    """

    def test_func(self) -> bool:
        return self.request.user.is_staff

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied
        return super().handle_no_permission()


def is_htmx(request) -> bool:
    return request.headers.get('HX-Request') == 'true'


class DashboardListMixin:
    """Shared list context for dashboard boxes and OOB list refreshes."""

    list_box_id: str = ''
    list_template_name: str = ''
    bulk_delete_url_name: str = ''
    box_title: str = ''
    add_url_name: str = ''
    add_label: str = 'Add'

    def get_list_queryset(self):
        raise NotImplementedError

    def get_list_context(self) -> dict:
        return {
            'items': self.get_list_queryset(),
            'box_id': self.list_box_id,
            'title': self.box_title,
            'add_url_name': self.add_url_name,
            'add_label': self.add_label,
            'bulk_delete_url_name': self.bulk_delete_url_name,
        }


class ModalContextMixin:
    """Shared template/context behaviour for views rendered inside the modal.

    Subclasses set:
      - ``fragment_template_name`` – partial returned for HTMX requests.
      - ``list_template_name`` – partial used for the OOB list refresh.
      - ``list_box_id`` – ``id`` of the dashboard box being refreshed.
      - ``page_title`` – heading shown inside the modal card / fallback page.

    For non-HTMX requests, falls back to ``manage/_form_page.html`` which
    embeds the same fragment in a stand-alone page.
    """

    fragment_template_name: str = ''
    list_template_name: str = ''
    list_box_id: str = ''
    page_title: str = ''

    def get_template_names(self):
        if is_htmx(self.request):
            return [self.fragment_template_name]
        return ['manage/_form_page.html']

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form_action'] = self.request.path
        ctx['page_title'] = self.page_title
        ctx['form_fragment_template'] = self.fragment_template_name
        return ctx

    def get_list_queryset(self):
        raise NotImplementedError

    def refresh_response(self) -> HttpResponse:
        """Empty #modal (close) + refreshed list, both as OOB swaps."""
        list_html = render_to_string(
            self.list_template_name,
            self.get_list_context(),
            request=self.request,
        )
        body = (
            '<div id="modal" hx-swap-oob="innerHTML"></div>'
            f'<div id="{self.list_box_id}-list" class="box__list" '
            'hx-swap-oob="true">'
            f'{list_html}'
            '</div>'
        )
        return HttpResponse(body)


class ModalFormMixin(ModalContextMixin):
    """For Create / Update views opened in the modal."""

    def form_valid(self, form):
        self.object = form.save()
        if is_htmx(self.request):
            return self.refresh_response()
        return redirect('manage:dashboard')


class ModalDeleteMixin(ModalContextMixin):
    """For DeleteView opened in the modal.

    Handles ``ProtectedError`` by re-rendering the confirm template with a
    friendly error message and the list of referencing objects.
    """

    def form_valid(self, form):
        try:
            self.object.delete()
        except ProtectedError as exc:
            return self.render_protected(exc)
        if is_htmx(self.request):
            return self.refresh_response()
        return redirect('manage:dashboard')

    def render_protected(self, exc: ProtectedError) -> HttpResponse:
        context = self.get_context_data(
            object=self.object,
            protected_objects=list(exc.protected_objects),
        )
        return self.render_to_response(context)


class BulkDeleteMixin:
    """Delete multiple objects selected via ``ids`` checkboxes on the dashboard.

    Subclasses set ``list_box_id``, ``list_template_name``, and implement
    ``get_list_queryset()``. Deletable rows are removed; rows blocked by
    ``PROTECT`` are skipped and reported in the modal.
    """

    list_box_id: str = ''
    list_template_name: str = ''

    def render_list_oob(self, request, **extra_context) -> str:
        context = self.get_list_context()
        context.update(extra_context)
        list_html = render_to_string(
            self.list_template_name,
            context,
            request=request,
        )
        return (
            f'<div id="{self.list_box_id}-list" class="box__list" '
            f'hx-swap-oob="true">{list_html}</div>'
        )

    def post(self, request):
        ids = request.POST.getlist('ids')
        queryset = self.get_list_queryset().filter(pk__in=ids)

        deleted_count = 0
        protected_items: list[dict] = []

        for obj in queryset:
            try:
                obj.delete()
                deleted_count += 1
            except ProtectedError as exc:
                protected_items.append({
                    'object': obj,
                    'protected_objects': list(exc.protected_objects),
                })

        if is_htmx(request):
            parts = [self.render_list_oob(request)]
            if protected_items:
                modal_html = render_to_string(
                    'manage/partials/bulk_delete_protected.html',
                    {
                        'protected_items': protected_items,
                        'deleted_count': deleted_count,
                    },
                    request=request,
                )
                parts.insert(
                    0,
                    f'<div id="modal" hx-swap-oob="innerHTML">{modal_html}</div>',
                )
            return HttpResponse(''.join(parts))

        return redirect('manage:dashboard')


class BulkDeleteView(StaffRequiredMixin, BulkDeleteMixin, View):
    pass

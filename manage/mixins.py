from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied


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

from django.views.generic import TemplateView

from .mixins import StaffRequiredMixin


class DashboardView(StaffRequiredMixin, TemplateView):
    template_name = 'manage/dashboard.html'

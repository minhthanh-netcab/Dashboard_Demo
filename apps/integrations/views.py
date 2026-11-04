from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import Http404
from django.shortcuts import redirect
from django.views import View
from django.views.generic import TemplateView

from apps.accounts.roles import can_manage_integrations, can_view_integrations

from . import jobs
from .exceptions import IntegrationError
from .models import SyncRun, SyncState, SyncStatus

MESSAGE_LEVELS = {
    SyncStatus.SUCCESS: messages.SUCCESS,
    SyncStatus.PARTIAL: messages.WARNING,
    SyncStatus.FAILED: messages.ERROR,
}

class IntegrationStatusView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = "integrations/status.html"

    def test_func(self):
        return can_view_integrations(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            modes={"OplaCRM": settings.OPLACRM_MODE, "MISA": settings.MISA_MODE},
            jobs=jobs.all_jobs(),
            states=SyncState.objects.select_related("last_run"),
            runs=SyncRun.objects.select_related("triggered_by")[:30],
        )
        return context


class RunSyncJobView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return can_manage_integrations(self.request.user)

    def post(self, request, key):
        job = jobs.get_job(key)
        if job is None:
            raise Http404
        try:
            runs = job.run(user=request.user)
        except IntegrationError as exc:
            messages.error(request, f"{job.label}: {exc}")
            return redirect("integrations:status")

        for run in runs:
            messages.add_message(
                request,
                MESSAGE_LEVELS.get(run.status, messages.INFO),
                f"{run.get_system_display()} / {run.entity_label}: {run.get_status_display()} — "
                f"đọc {run.fetched}, thêm mới {run.created}, cập nhật {run.updated}, lỗi {run.failed}. {run.message}",
            )
        return redirect("integrations:status")

"""Read-only aggregations over the operational data.

The time windows and the project health (RAG) rules are working assumptions,
not approved business definitions (docs/OPEN_QUESTIONS.md A13); the PM page
states the rule next to the table.
"""

from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import F, Max, Q
from django.shortcuts import redirect
from django.utils import timezone
from django.views.generic import TemplateView

from apps.accounts.roles import is_project_manager
from apps.projects.models import (
    OPEN_ISSUE_STATUSES,
    OPEN_TASK_STATUSES,
    Project,
    ProjectIssue,
    ProjectTask,
    TaskStatus,
)
from apps.projects.permissions import visible_projects
from apps.projects.views import PMRequiredMixin, latest_project_percent

from . import overview

UPCOMING_TASK_DAYS = 7
STALE_PROGRESS_DAYS = 7


@login_required
def home(request):
    if is_project_manager(request.user):
        return redirect("dashboard:pm")
    return redirect("dashboard:my_work")


class PMDashboardView(PMRequiredMixin, TemplateView):
    template_name = "dashboard/pm_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()

        health = overview.project_health(today)
        overdue_tasks = overview.overdue_tasks(today)
        serious_issues = overview.serious_issues()
        milestones = overview.upcoming_milestones(today)
        week_ago = today - timedelta(days=6)  # the last 7 days, today included
        done_7d = overview.completed_between(week_ago, today + timedelta(days=1))
        done_prev_7d = overview.completed_between(week_ago - timedelta(days=7), week_ago)
        summary = overview.health_summary(health)

        context.update(
            today=today,
            generated_at=timezone.localtime(),
            kpis={
                "active_projects": len(health),
                "total_projects": Project.objects.count(),
                "needs_attention": sum(row.needs_attention for row in health),
                "red_projects": summary[0]["count"],
                "overdue_tasks": overdue_tasks.count(),
                "open_tasks": sum(row.open_tasks for row in health),
                "done_7d": done_7d,
                "done_prev_7d": done_prev_7d,
                "done_delta": abs(done_7d - done_prev_7d),
            },
            health_summary=summary,
            health_chart=overview.health_chart(summary),
            project_health=health,
            roadmap=overview.roadmap(health, today),
            workload_chart=overview.workload_by_assignee(today),
            throughput_chart=overview.weekly_throughput(today),
            cross_department=overview.cross_department(),
            action_tasks=overdue_tasks.select_related("project", "assignee").order_by("due_date")[
                : overview.MAX_ACTION_TASKS
            ],
            action_issues=serious_issues.select_related("project", "assignee")[: overview.MAX_ACTION_ISSUES],
            serious_issue_count=serious_issues.count(),
            upcoming_milestones=milestones[: overview.MAX_MILESTONES],
            upcoming_milestone_count=milestones.count(),
            upcoming_milestone_days=overview.UPCOMING_MILESTONE_DAYS,
        )
        return context


class MyWorkView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard/my_work.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        today = timezone.localdate()
        visible = visible_projects(user)

        my_tasks = list(
            ProjectTask.objects.filter(assignee=user, status__in=OPEN_TASK_STATUSES, project__in=visible)
            .select_related("project", "milestone")
            .annotate(last_update_at=Max("progress_updates__created_at"))
            .order_by(F("due_date").asc(nulls_last=True))
        )
        stale_before = timezone.now() - timedelta(days=STALE_PROGRESS_DAYS)
        upcoming_until = today + timedelta(days=UPCOMING_TASK_DAYS)

        context.update(
            today=today,
            my_projects=Project.objects.filter(Q(members__user=user) | Q(manager=user))
            .distinct()
            .select_related("manager")
            .annotate(latest_percent=latest_project_percent()),
            my_tasks=my_tasks,
            overdue_tasks=[t for t in my_tasks if t.is_overdue],
            upcoming_tasks=[t for t in my_tasks if t.due_date and today <= t.due_date <= upcoming_until],
            stale_tasks=[
                t
                for t in my_tasks
                if t.status == TaskStatus.IN_PROGRESS and (t.last_update_at is None or t.last_update_at < stale_before)
            ],
            my_issues=ProjectIssue.objects.filter(assignee=user, status__in=OPEN_ISSUE_STATUSES, project__in=visible)
            .select_related("project"),
            upcoming_task_days=UPCOMING_TASK_DAYS,
            stale_progress_days=STALE_PROGRESS_DAYS,
        )
        return context

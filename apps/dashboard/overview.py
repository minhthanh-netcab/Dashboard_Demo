"""Data for the PM overview page.

The page follows an inverted pyramid, answering in order:
1. How is the portfolio doing?           -> KPI strip + RAG health counts
2. When does each project land?          -> roadmap timeline (bars + milestones + today)
3. Which projects need attention, why?   -> health table
4. What needs action now / soon?         -> action list + upcoming milestones
5. Is delivery keeping pace?             -> workload per person + 8-week throughput trend
6. What is waiting on other departments? -> handover / purchase / payment follow-ups

The RAG rules and time windows below are working assumptions recorded in
docs/OPEN_QUESTIONS.md (A13), not approved business definitions.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import timedelta

from django.db.models import Case, Count, IntegerField, Max, Q, When
from django.utils import timezone

from apps.payments.models import PaymentRequest
from apps.procurement.models import PurchaseRequest
from apps.projects.models import (
    CLOSED_PROJECT_STATUSES,
    OPEN_ISSUE_STATUSES,
    OPEN_TASK_STATUSES,
    HandoverStatus,
    MilestoneStatus,
    Project,
    ProjectIssue,
    ProjectMilestone,
    ProjectTask,
    SalesHandover,
    Severity,
    TaskStatus,
)
from apps.projects.views import latest_project_percent

SERIOUS_SEVERITIES = (Severity.HIGH, Severity.CRITICAL)
OPEN_MILESTONE_STATUSES = (MilestoneStatus.PLANNED, MilestoneStatus.IN_PROGRESS)
UPCOMING_MILESTONE_DAYS = 14
STALE_STATUS_DAYS = 7
TREND_WEEKS = 8
RED_OVERDUE_TASKS = 3  # this many overdue tasks or more turns a project red
MAX_ACTION_TASKS = 5
MAX_ACTION_ISSUES = 3
MAX_MILESTONES = 6

# --------------------------------------------------------------------- Health

RED, AMBER, GREEN = "red", "amber", "green"
HEALTH_LABELS = {RED: "Nguy cơ cao", AMBER: "Cần theo dõi", GREEN: "Ổn định"}
HEALTH_ORDER = {RED: 0, AMBER: 1, GREEN: 2}


@dataclass
class ProjectHealth:
    project: Project
    open_tasks: int
    overdue_tasks: int
    blocked_tasks: int = 0
    critical_issues: int = 0
    high_issues: int = 0
    overdue_milestones: int = 0
    next_milestone: ProjectMilestone | None = None
    health: str = GREEN
    reasons: list = field(default_factory=list)

    @property
    def serious_issues(self):
        return self.critical_issues + self.high_issues

    @property
    def needs_attention(self):
        return self.health != GREEN

    @property
    def health_label(self):
        return HEALTH_LABELS[self.health]

    def flag(self, level, reason):
        self.reasons.append(reason)
        if HEALTH_ORDER[level] < HEALTH_ORDER[self.health]:
            self.health = level


def _active_projects():
    return Project.objects.exclude(status__in=CLOSED_PROJECT_STATUSES)


def project_health(today):
    """Open projects with a RAG level and the reasons behind it.

    Red:   past planned end date, an open CRITICAL issue, or >= RED_OVERDUE_TASKS overdue tasks.
    Amber: any overdue task, overdue milestone, blocked task or open HIGH issue.
    Green: none of the above.
    Sorted red -> amber -> green, then by planned end date.
    """
    open_tasks = Q(tasks__status__in=OPEN_TASK_STATUSES)
    open_issues = Q(issues__status__in=OPEN_ISSUE_STATUSES)
    projects = list(
        _active_projects()
        .select_related("manager")
        .annotate(
            latest_percent=latest_project_percent(),
            n_open=Count("tasks", filter=open_tasks, distinct=True),
            n_overdue=Count("tasks", filter=open_tasks & Q(tasks__due_date__lt=today), distinct=True),
            n_blocked=Count("tasks", filter=Q(tasks__status=TaskStatus.BLOCKED), distinct=True),
            n_critical=Count("issues", filter=open_issues & Q(issues__severity=Severity.CRITICAL), distinct=True),
            n_high=Count("issues", filter=open_issues & Q(issues__severity=Severity.HIGH), distinct=True),
            n_late_ms=Count(
                "milestones",
                filter=Q(milestones__status__in=OPEN_MILESTONE_STATUSES, milestones__due_date__lt=today),
                distinct=True,
            ),
        )
    )
    next_milestones = {}
    for milestone in ProjectMilestone.objects.filter(
        project__in=projects, status__in=OPEN_MILESTONE_STATUSES, due_date__gte=today
    ).order_by("due_date"):
        next_milestones.setdefault(milestone.project_id, milestone)

    rows = []
    for p in projects:
        row = ProjectHealth(
            p, p.n_open, p.n_overdue, p.n_blocked, p.n_critical, p.n_high, p.n_late_ms, next_milestones.get(p.pk)
        )
        if p.is_overdue:
            row.flag(RED, "Quá ngày kết thúc")
        if row.critical_issues:
            row.flag(RED, f"{row.critical_issues} vấn đề nghiêm trọng")
        if row.overdue_tasks:
            row.flag(RED if row.overdue_tasks >= RED_OVERDUE_TASKS else AMBER, f"{row.overdue_tasks} việc quá hạn")
        if row.overdue_milestones:
            row.flag(AMBER, f"{row.overdue_milestones} mốc trễ hạn")
        if row.high_issues:
            row.flag(AMBER, f"{row.high_issues} vấn đề mức cao")
        if row.blocked_tasks:
            row.flag(AMBER, f"{row.blocked_tasks} việc vướng mắc")
        rows.append(row)
    far_future = today + timedelta(days=36500)
    rows.sort(key=lambda r: (HEALTH_ORDER[r.health], r.project.planned_end_date or far_future))
    return rows


def health_summary(rows):
    counts = {level: 0 for level in HEALTH_ORDER}
    for row in rows:
        counts[row.health] += 1
    return [{"level": level, "label": HEALTH_LABELS[level], "count": counts[level]} for level in HEALTH_ORDER]


def health_chart(summary):
    """Doughnut payload; `keys` lets the page map a clicked slice back to a health level."""
    return {
        "labels": [h["label"] for h in summary],
        "keys": [h["level"] for h in summary],
        "datasets": [
            {"label": "Dự án", "colors": [f"health-{h['level']}" for h in summary], "data": [h["count"] for h in summary]}
        ],
    }


# ------------------------------------------------------------------- Timeline


def _month_start(day, offset=0):
    month_index = day.year * 12 + day.month - 1 + offset
    return day.replace(year=month_index // 12, month=month_index % 12 + 1, day=1)


def _pct(value):
    # Formatted here: Vietnamese localisation would render 12.5 as "12,5" in templates, which breaks CSS.
    return f"{value:.2f}"


def roadmap(rows, today, months_before=1, months_after=4):
    """Gantt-style rows for the active projects over a fixed window of whole months."""
    start = _month_start(today, -months_before)
    end = _month_start(today, months_after + 1)
    span = (end - start).days

    def position(day):
        return max(0.0, min(100.0, (day - start).days * 100 / span))

    milestones = defaultdict(list)
    for m in ProjectMilestone.objects.filter(
        project__in=[r.project for r in rows], due_date__gte=start, due_date__lt=end
    ).exclude(status=MilestoneStatus.CANCELLED):
        milestones[m.project_id].append(
            {
                "left": _pct(position(m.due_date)),
                "name": m.name,
                "due_date": m.due_date,
                "done": m.status == MilestoneStatus.DONE,
                "overdue": m.is_overdue,
            }
        )

    timeline_rows = []
    for row in rows:
        p = row.project
        bar = None
        first = p.planned_start_date or p.planned_end_date
        last = p.planned_end_date or p.planned_start_date
        if first and last and last >= start and first < end:
            left, right = position(first), position(last)
            bar = {
                "left": _pct(left),
                "width": _pct(max(right - left, 1.0)),
                "cut_start": first < start,
                "cut_end": last >= end,
            }
        timeline_rows.append(
            {"row": row, "bar": bar, "milestones": sorted(milestones[p.pk], key=lambda m: m["due_date"])}
        )

    months = []
    for i in range(months_before + months_after + 1):
        month = _month_start(start, i)
        months.append({"label": f"T{month.month}/{month.year}", "left": _pct(position(month))})
    return {"rows": timeline_rows, "months": months, "today": _pct(position(today))}


# ------------------------------------------------------------------ Delivery


def _open_tasks():
    return ProjectTask.objects.filter(status__in=OPEN_TASK_STATUSES).exclude(project__status__in=CLOSED_PROJECT_STATUSES)


WORKLOAD_SERIES = (
    ("overdue", "Quá hạn", "overdue"),
    (TaskStatus.BLOCKED, "Vướng mắc", "warn"),
    (TaskStatus.IN_PROGRESS, "Đang làm", "task-in-progress"),
    (TaskStatus.TODO, "Chưa làm", "task-todo"),
)


def workload_by_assignee(today):
    """Stacked bar of open tasks per person. Each task counts once (overdue
    takes precedence over its status), so a bar adds up to the open total."""
    buckets = defaultdict(lambda: defaultdict(int))
    names = {}
    for task in _open_tasks().select_related("assignee"):
        key = task.assignee_id or 0
        names[key] = str(task.assignee) if task.assignee else "Chưa giao"
        bucket = "overdue" if task.due_date and task.due_date < today else task.status
        buckets[key][bucket] += 1
    people = sorted(buckets, key=lambda k: (-sum(buckets[k].values()), names[k]))
    return {
        "labels": [names[k] for k in people],
        "datasets": [
            {"label": label, "color": role, "data": [buckets[k][key] for k in people]}
            for key, label, role in WORKLOAD_SERIES
        ],
    }


def weekly_throughput(today, weeks=TREND_WEEKS):
    """Tasks completed vs. tasks created per calendar week (Mon–Sun), oldest first."""
    this_week = today - timedelta(days=today.weekday())
    starts = [this_week - timedelta(weeks=i) for i in reversed(range(weeks))]
    counters = {}
    for i, week in enumerate(starts):
        until = week + timedelta(days=7)
        counters[f"d{i}"] = Count("id", filter=Q(completed_at__date__gte=week, completed_at__date__lt=until))
        counters[f"c{i}"] = Count("id", filter=Q(created_at__date__gte=week, created_at__date__lt=until))
    counts = ProjectTask.objects.aggregate(**counters)
    return {
        "labels": [f"{w:%d/%m}" for w in starts],
        "titles": [
            "tuần này, chưa kết thúc" if w == this_week else f"tuần đến {w + timedelta(days=6):%d/%m}" for w in starts
        ],
        "datasets": [
            {"label": "Hoàn thành", "color": "task-done", "data": [counts[f"d{i}"] for i in range(weeks)]},
            {"label": "Việc mới", "color": "neutral", "data": [counts[f"c{i}"] for i in range(weeks)]},
        ],
    }


def completed_between(start, end):
    """Tasks completed on days in [start, end)."""
    return ProjectTask.objects.filter(completed_at__date__gte=start, completed_at__date__lt=end).count()


# -------------------------------------------------------------- Action lists


def overdue_tasks(today):
    return _open_tasks().filter(due_date__lt=today)


def serious_issues():
    """Open HIGH/CRITICAL issues, CRITICAL first (severity is text, so rank it)."""
    return (
        ProjectIssue.objects.filter(status__in=OPEN_ISSUE_STATUSES, severity__in=SERIOUS_SEVERITIES)
        .exclude(project__status__in=CLOSED_PROJECT_STATUSES)
        .annotate(
            severity_rank=Case(When(severity=Severity.CRITICAL, then=0), default=1, output_field=IntegerField())
        )
        .order_by("severity_rank", "created_at")
    )


def upcoming_milestones(today):
    return (
        ProjectMilestone.objects.filter(
            status__in=OPEN_MILESTONE_STATUSES,
            due_date__gte=today,
            due_date__lte=today + timedelta(days=UPCOMING_MILESTONE_DAYS),
        )
        .exclude(project__status__in=CLOSED_PROJECT_STATUSES)
        .select_related("project")
        .order_by("due_date")
    )


# ---------------------------------------------------------- Cross-department


def _tracking_summary(model):
    """Open tracking records, and those with no status entry in STALE_STATUS_DAYS.
    These are internal follow-up records, not official MISA approvals."""
    stale_before = timezone.now() - timedelta(days=STALE_STATUS_DAYS)
    qs = (
        model.objects.filter(tracking_closed=False)
        .exclude(project__status__in=CLOSED_PROJECT_STATUSES)
        .annotate(last_status_at=Max("status_entries__recorded_at"))
    )
    return {
        "open": qs.count(),
        "stale": qs.filter(Q(last_status_at__isnull=True) | Q(last_status_at__lt=stale_before)).count(),
    }


def cross_department():
    handovers = SalesHandover.objects.filter(status__in=(HandoverStatus.PENDING, HandoverStatus.NEEDS_INFO))
    return {
        "handovers": {
            "open": handovers.count(),
            "needs_info": handovers.filter(status=HandoverStatus.NEEDS_INFO).count(),
        },
        "purchases": _tracking_summary(PurchaseRequest),
        "payments": _tracking_summary(PaymentRequest),
        "stale_days": STALE_STATUS_DAYS,
    }

from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts import roles
from apps.core.testing import TEST_PASSWORD, make_user
from apps.projects.models import Project, ProjectMember, ProjectTask, SalesHandover, TaskStatus


class DashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.pm = make_user("pm", roles.PROJECT_MANAGER)
        cls.member = make_user("member", roles.PROJECT_MEMBER)
        cls.other = make_user("other", roles.PROJECT_MEMBER)
        yesterday = timezone.localdate() - timedelta(days=1)
        cls.project = Project.objects.create(name="Alpha", customer_name="C", manager=cls.pm)
        cls.hidden = Project.objects.create(name="Beta", customer_name="C", manager=cls.pm)
        ProjectMember.objects.create(project=cls.project, user=cls.member)
        ProjectTask.objects.create(project=cls.project, title="Mine overdue", assignee=cls.member, due_date=yesterday)
        ProjectTask.objects.create(project=cls.project, title="Done", assignee=cls.member, status=TaskStatus.DONE)
        ProjectTask.objects.create(project=cls.hidden, title="Not mine", assignee=cls.other, due_date=yesterday)

    def login(self, user):
        self.client.login(username=user.username, password=TEST_PASSWORD)

    def test_home_redirects_by_role(self):
        self.login(self.pm)
        self.assertRedirects(self.client.get(reverse("dashboard:home")), reverse("dashboard:pm"))
        self.login(self.member)
        self.assertRedirects(self.client.get(reverse("dashboard:home")), reverse("dashboard:my_work"))

    def test_pm_dashboard(self):
        self.login(self.pm)
        response = self.client.get(reverse("dashboard:pm"))
        self.assertEqual(response.status_code, 200)
        kpis = response.context["kpis"]
        self.assertEqual((kpis["active_projects"], kpis["needs_attention"]), (2, 2))
        self.assertEqual((kpis["overdue_tasks"], kpis["open_tasks"]), (2, 2))
        self.assertEqual({t.title for t in response.context["action_tasks"]}, {"Mine overdue", "Not mine"})

        health = {row.project: row for row in response.context["project_health"]}
        self.assertEqual(health[self.project].open_tasks, 1)
        self.assertEqual(health[self.project].reasons, ["1 việc quá hạn"])

        # One overdue task each -> amber, not red.
        self.assertEqual(health[self.project].health, "amber")
        summary = {h["level"]: h["count"] for h in response.context["health_summary"]}
        self.assertEqual(summary, {"red": 0, "amber": 2, "green": 0})

        workload = response.context["workload_chart"]
        self.assertEqual(set(workload["labels"]), {str(self.member), str(self.other)})
        overdue = next(d for d in workload["datasets"] if d["label"] == "Quá hạn")
        self.assertEqual(sum(overdue["data"]), 2)
        total = sum(sum(d["data"]) for d in workload["datasets"])
        self.assertEqual(total, 2)  # every open task lands in exactly one bucket

        trend = response.context["throughput_chart"]
        self.assertEqual(len(trend["labels"]), 8)
        created = next(d for d in trend["datasets"] if d["label"] == "Việc mới")
        self.assertEqual(created["data"][-1], 3)  # all three tasks were created this week

        self.assertEqual(len(response.context["roadmap"]["rows"]), 2)

    def test_health_turns_red_for_overdue_project_and_critical_issue(self):
        from apps.projects.models import ProjectIssue, Severity

        late = Project.objects.create(
            name="Late", customer_name="C", manager=self.pm, planned_end_date=timezone.localdate() - timedelta(days=3)
        )
        ProjectIssue.objects.create(project=self.hidden, title="Critical", severity=Severity.CRITICAL, reported_by=self.pm)
        self.login(self.pm)
        health = {row.project: row for row in self.client.get(reverse("dashboard:pm")).context["project_health"]}
        self.assertEqual(health[late].health, "red")
        self.assertEqual(health[late].reasons, ["Quá ngày kết thúc"])
        self.assertEqual(health[self.hidden].health, "red")
        rows = self.client.get(reverse("dashboard:pm")).context["project_health"]
        self.assertEqual(rows[-1].project, self.project)  # red projects sort first

    def test_critical_issues_are_listed_before_high(self):
        from apps.projects.models import ProjectIssue, Severity

        ProjectIssue.objects.create(project=self.project, title="High", severity=Severity.HIGH, reported_by=self.pm)
        ProjectIssue.objects.create(project=self.project, title="Critical", severity=Severity.CRITICAL, reported_by=self.pm)
        self.login(self.pm)
        issues = self.client.get(reverse("dashboard:pm")).context["action_issues"]
        self.assertEqual([i.title for i in issues], ["Critical", "High"])

    def test_member_cannot_open_pm_dashboard(self):
        self.login(self.member)
        self.assertEqual(self.client.get(reverse("dashboard:pm")).status_code, 403)

    def test_my_work_shows_only_my_open_tasks(self):
        self.login(self.member)
        response = self.client.get(reverse("dashboard:my_work"))
        self.assertEqual([t.title for t in response.context["my_tasks"]], ["Mine overdue"])
        self.assertEqual(len(response.context["overdue_tasks"]), 1)
        self.assertNotContains(response, "Not mine")


class SeedCommandTests(TestCase):
    @override_settings(DEBUG=True)
    def test_seed_is_idempotent_and_flags_demo_data(self):
        call_command("seed_demo_data", password="Demo-pass-123", stdout=StringIO())
        call_command("seed_demo_data", password="Demo-pass-123", stdout=StringIO())
        self.assertEqual(Project.objects.count(), 3)
        self.assertFalse(Project.objects.filter(is_demo_data=False).exists())
        self.assertFalse(SalesHandover.objects.filter(is_demo_data=False).exists())

        call_command("seed_demo_data", password="Demo-pass-123", reset=True, stdout=StringIO())
        self.assertEqual(Project.objects.count(), 3)

    def test_seed_refuses_without_debug(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command("seed_demo_data", password="x", stdout=StringIO())

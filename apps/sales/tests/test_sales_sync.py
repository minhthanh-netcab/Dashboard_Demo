from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.accounts import roles
from apps.core.models import AuditLog, SourceSystem
from apps.core.testing import TEST_PASSWORD, make_user
from apps.integrations.models import ExternalSystem, SyncState, SyncStatus
from apps.integrations.oplacrm.mock import MockOplaCRMProvider
from apps.integrations.runner import run_sync
from apps.projects.models import HandoverStatus, Project, SalesHandover
from apps.sales import services
from apps.sales.models import SalesAccount, SalesOpportunity
from apps.sales.sync import run_oplacrm_sync

T1 = "2026-10-01T09:00:00+07:00"
T2 = "2026-10-02T09:00:00+07:00"


def fixture(opportunities, accounts=None):
    return {
        "accounts": accounts if accounts is not None else [{"external_id": "ACC-1", "name": "Khách A", "updated_at": T1}],
        "opportunities": opportunities,
    }


def opportunity(**overrides):
    row = {
        "external_id": "OPP-1",
        "name": "Deal 1",
        "account_external_id": "ACC-1",
        "amount": "1000",
        "stage_name": "Won",
        "is_won": True,
        "owner_name": "Sales A",
        "updated_at": T1,
    }
    row.update(overrides)
    return row


def sync(provider):
    return [
        run_sync(ExternalSystem.OPLACRM, entity, provider.mode, lambda ctx, fn=fn: fn(provider, ctx))
        for entity, fn in (("accounts", services.sync_accounts), ("opportunities", services.sync_opportunities))
    ]


class OplaCRMSyncTests(TestCase):
    def test_mock_sync_end_to_end_and_incremental(self):
        first = run_oplacrm_sync()
        self.assertTrue(all(r.status == SyncStatus.SUCCESS and r.is_simulated for r in first))
        self.assertEqual(SalesAccount.objects.count(), 4)
        self.assertEqual(SalesOpportunity.objects.count(), 5)
        self.assertEqual(SalesOpportunity.objects.filter(is_simulated=True).count(), 5)

        # Won opportunities -> pending handovers, never projects.
        handovers = SalesHandover.objects.filter(source_system=SourceSystem.OPLACRM)
        self.assertEqual(handovers.count(), 2)
        self.assertTrue(all(h.status == HandoverStatus.PENDING and h.is_demo_data for h in handovers))
        self.assertFalse(Project.objects.exists())

        # Cursor advanced: the second run fetches nothing new.
        second = run_oplacrm_sync()
        self.assertEqual([r.fetched for r in second], [0, 0])
        self.assertEqual(SalesHandover.objects.filter(source_system=SourceSystem.OPLACRM).count(), 2)

    def test_full_resync_is_idempotent(self):
        provider = MockOplaCRMProvider()
        sync(provider)
        SyncState.objects.update(cursor="")
        runs = sync(provider)
        self.assertEqual([(r.created, r.updated) for r in runs], [(0, 0), (0, 0)])
        self.assertEqual([r.unchanged for r in runs], [4, 5])

    def test_pending_handover_follows_sales_changes(self):
        sync(MockOplaCRMProvider(fixture([opportunity()])))
        sync(MockOplaCRMProvider(fixture([opportunity(amount="2500", updated_at=T2)])))
        handover = SalesHandover.objects.get(external_opportunity_id="OPP-1")
        self.assertEqual(handover.committed_value, Decimal("2500"))
        self.assertEqual(handover.customer_name, "Khách A")
        self.assertTrue(AuditLog.objects.filter(object_id=str(handover.pk), action=AuditLog.Action.UPDATE).exists())

    def test_accepted_handover_is_not_overwritten(self):
        sync(MockOplaCRMProvider(fixture([opportunity()])))
        SalesHandover.objects.update(status=HandoverStatus.ACCEPTED)

        runs = sync(MockOplaCRMProvider(fixture([opportunity(amount="9999", updated_at=T2)])))
        handover = SalesHandover.objects.get(external_opportunity_id="OPP-1")
        self.assertEqual(handover.committed_value, Decimal("1000"))
        self.assertEqual(SalesOpportunity.objects.get().amount, Decimal("9999"))  # mirror still updated
        self.assertIn("committed_value", runs[1].warnings[0]["message"])

    def test_invalid_record_is_reported_without_blocking_others(self):
        runs = sync(MockOplaCRMProvider(fixture([opportunity(name=""), opportunity(external_id="OPP-2")])))
        opp_run = runs[1]
        self.assertEqual(opp_run.status, SyncStatus.PARTIAL)
        self.assertEqual(opp_run.errors[0]["ref"], "OPP-1")
        self.assertTrue(SalesOpportunity.objects.filter(external_id="OPP-2").exists())

    def test_lost_opportunity_creates_no_handover(self):
        sync(MockOplaCRMProvider(fixture([opportunity(is_won=False)])))
        self.assertFalse(SalesHandover.objects.exists())

    def test_command(self):
        out = StringIO()
        call_command("sync_oplacrm", stdout=out)
        self.assertIn("MÔ PHỎNG", out.getvalue())


class SalesViewsTests(TestCase):
    def test_access_and_amount_visibility(self):
        run_oplacrm_sync()
        sales = make_user("sales", roles.SALES_VIEWER)
        member = make_user("member", roles.PROJECT_MEMBER)
        url = reverse("sales:opportunity_list")

        self.client.login(username=member.username, password=TEST_PASSWORD)
        self.assertEqual(self.client.get(url).status_code, 403)

        self.client.login(username=sales.username, password=TEST_PASSWORD)
        response = self.client.get(url, {"won": "1"})
        self.assertEqual(len(response.context["opportunities"]), 2)
        self.assertContains(response, "Hệ thống báo cháy tự động kho A")
        self.assertNotContains(response, "860.000.000")  # amount hidden without finance role


class IntegrationViewsTests(TestCase):
    def test_only_system_admin_can_run_jobs(self):
        pm = make_user("pm", roles.PROJECT_MANAGER)
        admin = make_user("sysadmin", roles.SYSTEM_ADMIN)
        run_url = reverse("integrations:run", args=["oplacrm"])

        self.client.login(username=pm.username, password=TEST_PASSWORD)
        self.assertEqual(self.client.get(reverse("integrations:status")).status_code, 200)
        self.assertEqual(self.client.post(run_url).status_code, 403)

        self.client.login(username=admin.username, password=TEST_PASSWORD)
        self.assertRedirects(self.client.post(run_url), reverse("integrations:status"))
        self.assertEqual(SalesAccount.objects.count(), 4)
        self.assertEqual(self.client.post(reverse("integrations:run", args=["nope"])).status_code, 404)

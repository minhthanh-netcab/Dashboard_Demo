"""Create clearly-labelled sample data for local demos.

Every customer/supplier name here is fictional and every record is flagged
`is_demo_data=True`. Never run against a production database.
"""

import os
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts import roles
from apps.core.models import StatusSource
from apps.payments.models import PaymentRequest, PaymentStatusEntry
from apps.procurement.models import PurchaseItem, PurchaseRequest, PurchaseStatusEntry
from apps.projects.models import (
    ContractStatus,
    DocumentType,
    HandoverStatus,
    IssueKind,
    IssueStatus,
    KickoffRecord,
    MilestoneStatus,
    Priority,
    ProgressUpdate,
    Project,
    ProjectContract,
    ProjectDocument,
    ProjectIssue,
    ProjectMember,
    ProjectMilestone,
    ProjectStatus,
    ProjectTask,
    SalesHandover,
    Severity,
    TaskStatus,
)

DEMO_USERS = [
    # username, first (họ + tên đệm), last (tên), roles — get_full_name() ghép thành họ tên đầy đủ
    ("ql.duan", "Lê Hoàng", "Nam", [roles.PROJECT_MANAGER]),
    ("an.nguyen", "Nguyễn Văn", "An", [roles.PROJECT_MEMBER]),
    ("binh.tran", "Trần Thị", "Bình", [roles.PROJECT_MEMBER]),
    ("kinhdoanh", "Phạm Minh", "Đức", [roles.SALES_VIEWER]),
    ("ketoan", "Võ Thu", "Hà", [roles.FINANCE_VIEWER, roles.PROJECT_MEMBER]),
    ("quantri", "Đỗ Quang", "Huy", [roles.SYSTEM_ADMIN]),
]


class Command(BaseCommand):
    help = "Tạo dữ liệu mẫu (đánh dấu is_demo_data) và tài khoản demo cho môi trường local."

    def add_arguments(self, parser):
        parser.add_argument("--password", help="Mật khẩu cho tài khoản demo (mặc định: biến DEMO_USER_PASSWORD).")
        parser.add_argument("--reset", action="store_true", help="Xoá dữ liệu mẫu cũ trước khi tạo lại.")
        parser.add_argument("--force", action="store_true", help="Cho phép chạy khi DEBUG=False.")

    def handle(self, *args, password=None, reset=False, force=False, **options):
        if not settings.DEBUG and not force:
            raise CommandError("DEBUG=False: từ chối tạo dữ liệu mẫu. Dùng --force nếu chắc chắn đây là môi trường demo.")
        password = password or os.environ.get("DEMO_USER_PASSWORD")
        if not password:
            raise CommandError("Cần --password hoặc biến môi trường DEMO_USER_PASSWORD.")

        with transaction.atomic():
            users = self._ensure_users(password)
            if reset:
                self._delete_demo_data()
            elif Project.objects.filter(is_demo_data=True).exists():
                self.stdout.write(self.style.WARNING("Đã có dữ liệu mẫu; bỏ qua. Dùng --reset để tạo lại."))
                return
            self._create_demo_data(users)

        self.stdout.write(self.style.SUCCESS("Đã tạo dữ liệu mẫu. Tài khoản: " + ", ".join(u[0] for u in DEMO_USERS)))

    def _ensure_users(self, password):
        User = get_user_model()
        users = {}
        for username, first, last, role_names in DEMO_USERS:
            user, _ = User.objects.get_or_create(username=username, defaults={"first_name": first, "last_name": last})
            user.set_password(password)
            user.save()
            user.groups.set([Group.objects.get_or_create(name=r)[0] for r in role_names])
            users[username] = user
        return users

    def _delete_demo_data(self):
        PaymentRequest.objects.filter(is_demo_data=True).delete()
        PurchaseRequest.objects.filter(is_demo_data=True).delete()
        Project.objects.filter(is_demo_data=True).delete()
        SalesHandover.objects.filter(is_demo_data=True).delete()

    def _create_demo_data(self, users):
        pm, an, binh, finance = users["ql.duan"], users["an.nguyen"], users["binh.tran"], users["ketoan"]
        today = timezone.localdate()

        def d(days):
            return today + timedelta(days=days)

        # --- Handovers -----------------------------------------------------
        accepted = SalesHandover.objects.create(
            external_opportunity_id="OPP-2026-018",
            customer_name="Công ty TNHH Cơ khí Chính xác Tân Phú",
            deal_name="Hệ thống camera giám sát nhà xưởng",
            sales_owner_name="Phạm Minh Đức",
            committed_value=Decimal("1250000000"),
            committed_start_date=d(-45),
            committed_end_date=d(60),
            committed_scope="Cung cấp và lắp đặt 120 camera IP, 01 trung tâm giám sát.",
            boq_reference="BOQ-2026-018",
            status=HandoverStatus.ACCEPTED,
            review_note="Đủ thông tin để triển khai.",
            reviewed_by=pm,
            reviewed_at=timezone.now() - timedelta(days=40),
            is_demo_data=True,
            created_by=pm,
        )
        SalesHandover.objects.create(
            external_opportunity_id="OPP-2026-023",
            customer_name="Công ty CP Logistics Đông Dương",
            deal_name="Nâng cấp hạ tầng mạng văn phòng",
            sales_owner_name="Phạm Minh Đức",
            committed_value=Decimal("380000000"),
            committed_start_date=d(10),
            committed_end_date=d(70),
            committed_scope="Thay thế switch lõi và hệ thống Wi-Fi cho 3 tầng.",
            status=HandoverStatus.PENDING,
            is_demo_data=True,
            created_by=pm,
        )
        SalesHandover.objects.create(
            external_opportunity_id="OPP-2026-027",
            customer_name="Công ty TNHH Dược phẩm Minh Khang",
            deal_name="Trang bị phòng họp trực tuyến",
            committed_value=Decimal("210000000"),
            status=HandoverStatus.NEEDS_INFO,
            review_note="Thiếu BOQ chi tiết và ngày bàn giao cam kết.",
            reviewed_by=pm,
            reviewed_at=timezone.now() - timedelta(days=2),
            is_demo_data=True,
            created_by=pm,
        )

        # --- Projects ------------------------------------------------------
        p1 = Project.objects.create(
            name="Hệ thống camera giám sát nhà xưởng",
            customer_name="Công ty TNHH Cơ khí Chính xác Tân Phú",
            description="Dự án lập từ hồ sơ bàn giao OPP-2026-018.",
            status=ProjectStatus.IN_PROGRESS,
            manager=pm,
            planned_start_date=d(-40),
            planned_end_date=d(50),
            handover=accepted,
            is_demo_data=True,
            created_by=pm,
        )
        p2 = Project.objects.create(
            name="Triển khai phần mềm quản lý kho",
            customer_name="Công ty CP Thực phẩm An Lạc",
            status=ProjectStatus.IN_PROGRESS,
            manager=pm,
            planned_start_date=d(-90),
            planned_end_date=d(-5),
            is_demo_data=True,
            created_by=pm,
        )
        p3 = Project.objects.create(
            name="Bảo trì hạ tầng CNTT định kỳ",
            customer_name="Công ty TNHH Quản lý Bất động sản Hải Âu",
            status=ProjectStatus.READY,
            manager=pm,
            planned_start_date=d(7),
            planned_end_date=d(120),
            is_demo_data=True,
            created_by=pm,
        )
        for project, user, role in [
            (p1, an, "Kỹ thuật triển khai"),
            (p1, binh, "Mua hàng"),
            (p1, finance, "Theo dõi tài chính"),
            (p2, binh, "Triển khai phần mềm"),
            (p3, an, "Kỹ thuật"),
        ]:
            ProjectMember.objects.create(project=project, user=user, project_role=role, created_by=pm)

        # --- Records -------------------------------------------------------
        KickoffRecord.objects.create(
            project=p1,
            meeting_date=d(-38),
            location="Phòng họp tầng 3",
            attendees="Phòng Dự án, Phòng Kinh doanh, Phòng Kế toán, Bộ phận Kho",
            minutes="Thống nhất phạm vi công việc, mốc khảo sát và kế hoạch giao hàng.",
            follow_up="Phòng Kinh doanh gửi bản BOQ chốt.",
            created_by=pm,
        )
        contract_doc = ProjectDocument.objects.create(
            project=p1,
            doc_type=DocumentType.CONTRACT,
            title="Hợp đồng số HD-2026-018 (bản scan)",
            external_reference=r"\\fileserver\du-an\HD-2026-018\hop-dong.pdf",
            created_by=pm,
        )
        ProjectContract.objects.create(
            project=p1,
            contract_number="HD-2026-018",
            title="Hợp đồng cung cấp và lắp đặt hệ thống camera giám sát",
            status=ContractStatus.SIGNED,
            signed_date=d(-35),
            contract_value=Decimal("1250000000"),
            document=contract_doc,
            created_by=pm,
        )

        # --- Plan ----------------------------------------------------------
        m1 = ProjectMilestone.objects.create(
            project=p1, name="Hoàn thành khảo sát", due_date=d(-20), status=MilestoneStatus.DONE, completed_date=d(-22), sort_order=1
        )
        m2 = ProjectMilestone.objects.create(
            project=p1, name="Giao hàng thiết bị", due_date=d(7), status=MilestoneStatus.IN_PROGRESS, sort_order=2
        )
        ProjectMilestone.objects.create(project=p1, name="Nghiệm thu", due_date=d(50), sort_order=3)
        m4 = ProjectMilestone.objects.create(
            project=p2, name="Vận hành chính thức", due_date=d(-5), status=MilestoneStatus.IN_PROGRESS, sort_order=1
        )
        ProjectMilestone.objects.create(project=p3, name="Họp khởi động", due_date=d(10), sort_order=1)

        def task(project, title, assignee, due, status=TaskStatus.TODO, milestone=None, priority=Priority.MEDIUM):
            return ProjectTask.objects.create(
                project=project,
                milestone=milestone,
                title=title,
                assignee=assignee,
                start_date=d(-30),
                due_date=due,
                status=status,
                priority=priority,
                completed_at=timezone.now() if status == TaskStatus.DONE else None,
                created_by=pm,
            )

        t1 = task(p1, "Khảo sát mặt bằng", an, d(-25), TaskStatus.DONE, m1)
        t2 = task(p1, "Đặt hàng camera và đầu ghi", binh, d(3), TaskStatus.IN_PROGRESS, m2, Priority.HIGH)
        task(p1, "Lập bản vẽ đi dây", an, d(-2), TaskStatus.IN_PROGRESS, m2, Priority.HIGH)
        task(p1, "Chuẩn bị hồ sơ nghiệm thu", an, d(45))
        t5 = task(p2, "Đào tạo người dùng kho", binh, d(-8), TaskStatus.BLOCKED, m4, Priority.HIGH)
        task(p2, "Chuyển dữ liệu tồn kho", binh, d(-3), TaskStatus.IN_PROGRESS, m4)
        task(p3, "Lập lịch bảo trì quý", an, d(12))
        task(p1, "Đối chiếu hoá đơn đầu vào", finance, d(5))
        task(p2, "Bàn giao tài liệu vận hành", an, d(4))
        task(p3, "Khảo sát hiện trạng thiết bị", None, d(9))

        # Completed work spread over the past weeks, so the 8-week trend has history.
        # created_at / completed_at are set after insert (created_at is auto_now_add).
        def backdate(t, created_days_ago, done_days_ago=None):
            now = timezone.now()
            fields = {"created_at": now - timedelta(days=created_days_ago)}
            if done_days_ago is not None:
                fields["completed_at"] = now - timedelta(days=done_days_ago)
            ProjectTask.objects.filter(pk=t.pk).update(**fields)

        backdate(t1, 50, 22)
        for project, title, who, created_ago, done_ago in [
            (p1, "Thu thập yêu cầu kỹ thuật", an, 54, 46),
            (p1, "Chốt danh mục thiết bị", binh, 48, 38),
            (p1, "Họp khởi động với khách hàng", an, 41, 38),
            (p2, "Cài đặt máy chủ ứng dụng", binh, 56, 49),
            (p2, "Cấu hình danh mục hàng hoá", binh, 47, 33),
            (p2, "Kiểm thử nghiệp vụ nhập kho", binh, 35, 25),
            (p2, "Kiểm thử nghiệp vụ xuất kho", an, 30, 17),
            (p1, "Thiết kế sơ đồ vị trí camera", an, 27, 12),
            (p1, "Thống nhất bản vẽ với khách hàng", an, 19, 9),
            (p2, "Hướng dẫn sử dụng cho thủ kho", binh, 12, 4),
            (p1, "Kiểm tra hàng mẫu", binh, 8, 2),
        ]:
            backdate(task(project, title, who, d(-done_ago), TaskStatus.DONE), created_ago, done_ago)
        open_seeded = ProjectTask.objects.filter(project__in=(p1, p2, p3)).exclude(status=TaskStatus.DONE).order_by("pk")
        for t, created_ago in zip(open_seeded, (44, 36, 30, 26, 20, 15, 10, 6, 3, 1)):
            backdate(t, created_ago)

        # --- Progress history ---------------------------------------------
        ProgressUpdate.objects.create(
            project=p1, task=t1, author=an, percent=100, note="Đã khảo sát xong.",
            status_from=TaskStatus.IN_PROGRESS, status_to=TaskStatus.DONE,
        )
        ProgressUpdate.objects.create(project=p1, task=t2, author=binh, percent=40, note="Đã nhận báo giá từ 2 nhà cung cấp.")
        ProgressUpdate.objects.create(project=p1, author=pm, percent=35, note="Đánh giá tiến độ chung của Quản lý dự án.")
        stale = ProgressUpdate.objects.create(project=p2, task=t5, author=binh, note="Chờ khách hàng xếp lịch đào tạo.")
        ProgressUpdate.objects.filter(pk=stale.pk).update(created_at=timezone.now() - timedelta(days=10))
        ProgressUpdate.objects.create(project=p2, author=pm, percent=70, note="Đánh giá tiến độ chung của Quản lý dự án.")

        # --- Issues --------------------------------------------------------
        ProjectIssue.objects.create(
            project=p1, task=t2, kind=IssueKind.RISK, title="Nhà cung cấp có thể giao hàng trễ 1 tuần",
            severity=Severity.MEDIUM, assignee=binh, reported_by=binh, created_by=binh,
        )
        ProjectIssue.objects.create(
            project=p2, task=t5, kind=IssueKind.ISSUE, title="Khách hàng chưa bố trí người học",
            severity=Severity.HIGH, status=IssueStatus.IN_PROGRESS, assignee=pm, reported_by=binh, created_by=binh,
        )

        # --- Purchase / payment tracking ----------------------------------
        pr = PurchaseRequest.objects.create(
            project=p1, title="Mua camera và đầu ghi", requester=binh, request_date=d(-10),
            supplier_name="Công ty TNHH Thiết bị An ninh Việt Phát", is_demo_data=True, created_by=binh,
        )
        PurchaseItem.objects.create(purchase_request=pr, description="Camera IP 4MP", quantity=120, unit="cái", unit_cost=Decimal("2500000"))
        PurchaseItem.objects.create(purchase_request=pr, description="Đầu ghi 64 kênh", quantity=2, unit="bộ", unit_cost=Decimal("45000000"))
        PurchaseStatusEntry.objects.create(
            purchase_request=pr, status_label="Đã trình Quản lý dự án", status_source=StatusSource.DEMO,
            evidence_note="Ghi nhận nội bộ, chưa đối chiếu với MISA.", recorded_by=binh,
        )
        pr2 = PurchaseRequest.objects.create(
            project=p2, title="Mua máy quét mã vạch", requester=binh, request_date=d(-20),
            supplier_name="Công ty CP Thiết bị Mã vạch Kim Long", is_demo_data=True, created_by=binh,
        )
        PurchaseItem.objects.create(purchase_request=pr2, description="Máy quét mã vạch", quantity=10, unit="cái", unit_cost=Decimal("3200000"))

        pay = PaymentRequest.objects.create(
            project=p1, payee_name="Công ty TNHH Thiết bị An ninh Việt Phát", amount=Decimal("150000000"),
            reason="Tạm ứng 50% giá trị đơn hàng camera", purchase_request=pr, requester=pm,
            request_date=d(-5), is_demo_data=True, created_by=pm,
        )
        PaymentStatusEntry.objects.create(
            payment_request=pay, status_label="Giám đốc dự án đã xem xét", status_source=StatusSource.DEMO,
            evidence_note="Ghi nhận nội bộ, chưa đối chiếu với MISA.", recorded_by=pm,
        )

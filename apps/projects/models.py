"""Project operational data — owned by this application (CLAUDE.md §3.4).

All status values below are demo labels (CLAUDE.md §6.3) and are kept in
TextChoices so they can be renamed once the company confirms them.
"""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from apps.core.models import SourceSystem, TrackedModel
from apps.core.utils import next_sequential_code


def _check_date_order(start_field, end_field, start, end):
    if start and end and end < start:
        raise ValidationError({end_field: "Ngày kết thúc phải sau ngày bắt đầu."})


# --------------------------------------------------------------------------
# Sales handover
# --------------------------------------------------------------------------


class HandoverStatus(models.TextChoices):
    PENDING = "PENDING", "Chờ tiếp nhận"
    NEEDS_INFO = "NEEDS_INFO", "Cần bổ sung thông tin"
    ACCEPTED = "ACCEPTED", "Đã chấp nhận"
    REJECTED = "REJECTED", "Đã từ chối"


class SalesHandover(TrackedModel):
    """What Sales sold/promised. Fields prefixed `committed_` are Sales
    commitments and are deliberately separate from the Project execution plan
    (CLAUDE.md §4.1). Entered manually in Phase 1; OplaCRM sync comes later.
    """

    FINANCE_FIELDS = ("committed_value",)

    source_system = models.CharField(
        "Nguồn dữ liệu", max_length=20, choices=SourceSystem.choices, default=SourceSystem.MANUAL
    )
    external_opportunity_id = models.CharField("Mã cơ hội (OplaCRM)", max_length=100, blank=True)
    external_account_id = models.CharField("Mã khách hàng (OplaCRM)", max_length=100, blank=True)
    customer_name = models.CharField("Khách hàng", max_length=255)
    deal_name = models.CharField("Tên thương vụ", max_length=255)
    sales_owner_name = models.CharField("Nhân viên kinh doanh", max_length=255, blank=True)
    committed_value = models.DecimalField(
        "Giá trị bán (cam kết)", max_digits=18, decimal_places=2, null=True, blank=True
    )
    currency = models.CharField("Tiền tệ", max_length=3, default="VND")
    committed_start_date = models.DateField("Ngày bắt đầu cam kết", null=True, blank=True)
    committed_end_date = models.DateField("Ngày hoàn thành cam kết", null=True, blank=True)
    committed_scope = models.TextField("Phạm vi / hàng hoá cam kết", blank=True)
    boq_reference = models.CharField("Tham chiếu BOQ / báo giá", max_length=255, blank=True)

    status = models.CharField(
        "Trạng thái tiếp nhận", max_length=20, choices=HandoverStatus.choices, default=HandoverStatus.PENDING
    )
    review_note = models.TextField("Ghi chú tiếp nhận", blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Người tiếp nhận",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    reviewed_at = models.DateTimeField("Tiếp nhận lúc", null=True, blank=True)
    is_demo_data = models.BooleanField("Dữ liệu mẫu", default=False)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Bàn giao từ Sales"
        verbose_name_plural = "Bàn giao từ Sales"
        constraints = [
            models.UniqueConstraint(
                fields=["source_system", "external_opportunity_id"],
                condition=~Q(external_opportunity_id=""),
                name="uniq_handover_external_opportunity",
            )
        ]

    def __str__(self):
        return f"{self.deal_name} – {self.customer_name}"

    def clean(self):
        super().clean()
        _check_date_order(
            "committed_start_date", "committed_end_date", self.committed_start_date, self.committed_end_date
        )

    def get_absolute_url(self):
        return reverse("projects:handover_detail", args=[self.pk])

    @property
    def linked_project(self):
        try:
            return self.project
        except Project.DoesNotExist:
            return None


# --------------------------------------------------------------------------
# Project
# --------------------------------------------------------------------------


class ProjectStatus(models.TextChoices):
    PENDING_HANDOVER = "PENDING_HANDOVER", "Chờ bàn giao"
    READY = "READY", "Sẵn sàng triển khai"
    IN_PROGRESS = "IN_PROGRESS", "Đang thực hiện"
    ON_HOLD = "ON_HOLD", "Tạm dừng"
    COMPLETED = "COMPLETED", "Hoàn thành"
    CANCELLED = "CANCELLED", "Đã huỷ"


CLOSED_PROJECT_STATUSES = (ProjectStatus.COMPLETED, ProjectStatus.CANCELLED)


class Project(TrackedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField("Mã dự án", max_length=30, unique=True, blank=True)
    name = models.CharField("Tên dự án", max_length=255)
    customer_name = models.CharField("Khách hàng", max_length=255)
    description = models.TextField("Mô tả", blank=True)
    status = models.CharField("Trạng thái", max_length=20, choices=ProjectStatus.choices, default=ProjectStatus.READY)
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Quản lý dự án",
        on_delete=models.PROTECT,
        related_name="managed_projects",
    )
    planned_start_date = models.DateField("Ngày bắt đầu (kế hoạch)", null=True, blank=True)
    planned_end_date = models.DateField("Ngày kết thúc (kế hoạch)", null=True, blank=True)
    handover = models.OneToOneField(
        SalesHandover,
        verbose_name="Bàn giao từ Sales",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="project",
    )
    is_demo_data = models.BooleanField("Dữ liệu mẫu", default=False)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Dự án"
        verbose_name_plural = "Dự án"

    def __str__(self):
        return f"{self.code} – {self.name}" if self.code else self.name

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = next_sequential_code(Project, "code", "PRJ")
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        _check_date_order("planned_start_date", "planned_end_date", self.planned_start_date, self.planned_end_date)

    def get_absolute_url(self):
        return reverse("projects:detail", args=[self.pk])

    @property
    def is_overdue(self):
        return (
            self.planned_end_date is not None
            and self.planned_end_date < timezone.localdate()
            and self.status not in CLOSED_PROJECT_STATUSES
        )


class ProjectMember(TrackedModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Thành viên",
        on_delete=models.CASCADE,
        related_name="project_memberships",
    )
    project_role = models.CharField("Vai trò trong dự án", max_length=100, blank=True)

    class Meta:
        ordering = ["user__username"]
        verbose_name = "Thành viên dự án"
        verbose_name_plural = "Thành viên dự án"
        constraints = [models.UniqueConstraint(fields=["project", "user"], name="uniq_project_member")]

    def __str__(self):
        return f"{self.user} @ {self.project.code}"


class KickoffRecord(TrackedModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="kickoffs")
    meeting_date = models.DateField("Ngày họp")
    location = models.CharField("Địa điểm / hình thức", max_length=255, blank=True)
    attendees = models.TextField("Thành phần tham dự", blank=True, help_text="Người / phòng ban tham dự.")
    minutes = models.TextField("Nội dung / biên bản")
    follow_up = models.TextField("Việc cần theo dõi", blank=True)

    class Meta:
        ordering = ["-meeting_date"]
        verbose_name = "Biên bản kickoff"
        verbose_name_plural = "Biên bản kickoff"

    def __str__(self):
        return f"Kickoff {self.meeting_date:%d/%m/%Y}"


class DocumentType(models.TextChoices):
    CONTRACT = "CONTRACT", "Hợp đồng"
    HANDOVER = "HANDOVER", "Hồ sơ bàn giao"
    KICKOFF = "KICKOFF", "Biên bản kickoff"
    QUOTATION = "QUOTATION", "Báo giá / BOQ"
    DELIVERY = "DELIVERY", "Giao hàng"
    ACCEPTANCE = "ACCEPTANCE", "Nghiệm thu"
    OTHER = "OTHER", "Khác"


class ProjectDocument(TrackedModel):
    """Document metadata + a reference to where the file lives.

    Phase 1 does not store uploaded files (assumption, see OPEN_QUESTIONS.md).
    """

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="documents")
    doc_type = models.CharField("Loại tài liệu", max_length=20, choices=DocumentType.choices)
    title = models.CharField("Tên tài liệu", max_length=255)
    external_reference = models.CharField(
        "Vị trí lưu trữ",
        max_length=500,
        blank=True,
        help_text="Đường dẫn thư mục / link nội bộ nơi lưu file gốc.",
    )
    note = models.TextField("Ghi chú", blank=True)

    class Meta:
        ordering = ["doc_type", "title"]
        verbose_name = "Tài liệu dự án"
        verbose_name_plural = "Tài liệu dự án"

    def __str__(self):
        return self.title


class ContractStatus(models.TextChoices):
    DRAFT = "DRAFT", "Đang soạn"
    IN_REVIEW = "IN_REVIEW", "Đang xem xét"
    SIGNED = "SIGNED", "Đã ký"
    CANCELLED = "CANCELLED", "Đã huỷ"


class ProjectContract(TrackedModel):
    FINANCE_FIELDS = ("contract_value",)

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="contracts")
    contract_number = models.CharField("Số hợp đồng", max_length=100, blank=True)
    title = models.CharField("Tên hợp đồng", max_length=255)
    status = models.CharField("Trạng thái", max_length=20, choices=ContractStatus.choices, default=ContractStatus.DRAFT)
    signed_date = models.DateField("Ngày ký", null=True, blank=True)
    contract_value = models.DecimalField("Giá trị hợp đồng", max_digits=18, decimal_places=2, null=True, blank=True)
    currency = models.CharField("Tiền tệ", max_length=3, default="VND")
    document = models.ForeignKey(
        ProjectDocument,
        verbose_name="Tài liệu liên quan",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="contracts",
    )
    note = models.TextField("Ghi chú", blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Hợp đồng"
        verbose_name_plural = "Hợp đồng"

    def __str__(self):
        return self.contract_number or self.title


# --------------------------------------------------------------------------
# Plan: milestones and tasks
# --------------------------------------------------------------------------


class MilestoneStatus(models.TextChoices):
    PLANNED = "PLANNED", "Chưa bắt đầu"
    IN_PROGRESS = "IN_PROGRESS", "Đang thực hiện"
    DONE = "DONE", "Hoàn thành"
    CANCELLED = "CANCELLED", "Đã huỷ"


class ProjectMilestone(TrackedModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="milestones")
    name = models.CharField("Tên mốc", max_length=255)
    description = models.TextField("Mô tả", blank=True)
    due_date = models.DateField("Hạn")
    status = models.CharField(
        "Trạng thái", max_length=20, choices=MilestoneStatus.choices, default=MilestoneStatus.PLANNED
    )
    completed_date = models.DateField("Ngày hoàn thành", null=True, blank=True)
    sort_order = models.PositiveIntegerField("Thứ tự", default=0)

    class Meta:
        ordering = ["sort_order", "due_date"]
        verbose_name = "Mốc tiến độ"
        verbose_name_plural = "Mốc tiến độ"

    def __str__(self):
        return self.name

    @property
    def is_overdue(self):
        return self.due_date < timezone.localdate() and self.status in (
            MilestoneStatus.PLANNED,
            MilestoneStatus.IN_PROGRESS,
        )


class TaskStatus(models.TextChoices):
    TODO = "TODO", "Chưa bắt đầu"
    IN_PROGRESS = "IN_PROGRESS", "Đang làm"
    BLOCKED = "BLOCKED", "Đang vướng mắc"
    DONE = "DONE", "Hoàn thành"
    CANCELLED = "CANCELLED", "Đã huỷ"


OPEN_TASK_STATUSES = (TaskStatus.TODO, TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED)


class Priority(models.TextChoices):
    LOW = "LOW", "Thấp"
    MEDIUM = "MEDIUM", "Trung bình"
    HIGH = "HIGH", "Cao"


class ProjectTask(TrackedModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tasks")
    milestone = models.ForeignKey(
        ProjectMilestone,
        verbose_name="Mốc tiến độ",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tasks",
    )
    title = models.CharField("Công việc", max_length=255)
    description = models.TextField("Mô tả", blank=True)
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Người thực hiện",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_tasks",
    )
    start_date = models.DateField("Ngày bắt đầu", null=True, blank=True)
    due_date = models.DateField("Hạn hoàn thành", null=True, blank=True)
    status = models.CharField("Trạng thái", max_length=20, choices=TaskStatus.choices, default=TaskStatus.TODO)
    priority = models.CharField("Ưu tiên", max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    completed_at = models.DateTimeField("Hoàn thành lúc", null=True, blank=True, editable=False)

    class Meta:
        ordering = ["due_date", "id"]
        verbose_name = "Công việc"
        verbose_name_plural = "Công việc"

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        _check_date_order("start_date", "due_date", self.start_date, self.due_date)

    @property
    def is_overdue(self):
        return self.due_date is not None and self.due_date < timezone.localdate() and self.status in OPEN_TASK_STATUSES


# --------------------------------------------------------------------------
# Progress history and issues
# --------------------------------------------------------------------------


class ProgressUpdate(models.Model):
    """Append-only progress history (CLAUDE.md §7.3).

    `percent` is what the author reports. No project-level progress formula
    is applied because none has been approved (CLAUDE.md §4.2).
    """

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="progress_updates")
    task = models.ForeignKey(
        ProjectTask,
        verbose_name="Công việc",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="progress_updates",
        help_text="Bỏ trống nếu là cập nhật tiến độ chung của dự án.",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="Người cập nhật", on_delete=models.PROTECT, related_name="+"
    )
    percent = models.PositiveSmallIntegerField(
        "% hoàn thành (tự báo cáo)", null=True, blank=True, validators=[MaxValueValidator(100)]
    )
    note = models.TextField("Nội dung cập nhật")
    status_from = models.CharField("Trạng thái trước", max_length=20, blank=True)
    status_to = models.CharField("Trạng thái sau", max_length=20, blank=True)
    created_at = models.DateTimeField("Thời điểm", auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "Cập nhật tiến độ"
        verbose_name_plural = "Cập nhật tiến độ"

    def __str__(self):
        return f"{self.author} – {self.created_at:%d/%m/%Y %H:%M}"

    @property
    def status_from_label(self):
        return TaskStatus(self.status_from).label if self.status_from in TaskStatus.values else self.status_from

    @property
    def status_to_label(self):
        return TaskStatus(self.status_to).label if self.status_to in TaskStatus.values else self.status_to


class IssueKind(models.TextChoices):
    ISSUE = "ISSUE", "Vấn đề"
    RISK = "RISK", "Rủi ro"


class Severity(models.TextChoices):
    LOW = "LOW", "Thấp"
    MEDIUM = "MEDIUM", "Trung bình"
    HIGH = "HIGH", "Cao"
    CRITICAL = "CRITICAL", "Nghiêm trọng"


class IssueStatus(models.TextChoices):
    OPEN = "OPEN", "Đang mở"
    IN_PROGRESS = "IN_PROGRESS", "Đang xử lý"
    RESOLVED = "RESOLVED", "Đã xử lý"
    CLOSED = "CLOSED", "Đã đóng"


OPEN_ISSUE_STATUSES = (IssueStatus.OPEN, IssueStatus.IN_PROGRESS)


class ProjectIssue(TrackedModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="issues")
    task = models.ForeignKey(
        ProjectTask,
        verbose_name="Công việc liên quan",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="issues",
    )
    kind = models.CharField("Loại", max_length=10, choices=IssueKind.choices, default=IssueKind.ISSUE)
    title = models.CharField("Tiêu đề", max_length=255)
    description = models.TextField("Mô tả", blank=True)
    severity = models.CharField("Mức độ", max_length=10, choices=Severity.choices, default=Severity.MEDIUM)
    status = models.CharField("Trạng thái", max_length=20, choices=IssueStatus.choices, default=IssueStatus.OPEN)
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Người xử lý",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_issues",
    )
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="Người báo cáo", on_delete=models.PROTECT, related_name="+"
    )
    resolved_at = models.DateTimeField("Xử lý lúc", null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Vấn đề / rủi ro"
        verbose_name_plural = "Vấn đề / rủi ro"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.status in OPEN_ISSUE_STATUSES:
            self.resolved_at = None
        elif self.resolved_at is None:
            self.resolved_at = timezone.now()
        super().save(*args, **kwargs)

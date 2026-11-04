from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models


class SourceSystem(models.TextChoices):
    """Where a record's data came from (CLAUDE.md §7.2).

    Phase 1 only writes MANUAL. The other values are reserved for the
    OplaCRM/MISA phases and must not be set until those integrations exist.
    """

    MANUAL = "MANUAL", "Nhập thủ công"
    OPLACRM = "OPLACRM", "OplaCRM"
    MISA_ACT_API = "MISA_ACT_API", "MISA ACT API"
    FINANCE_CSV = "FINANCE_CSV", "File tài chính (CSV/XLSX)"


class StatusSource(models.TextChoices):
    """Provenance of a purchase/payment status entry (CLAUDE.md §4.4).

    Nothing in Phase 1 reads MISA, so no value means "official MISA status".
    MISA_REFERENCED only records that a user says they saw it in MISA, and
    requires evidence.
    """

    DEMO = "DEMO", "Dữ liệu khởi tạo"
    INTERNAL = "INTERNAL", "Ghi nhận nội bộ"
    MISA_REFERENCED = "MISA_REFERENCED", "Đã đối chiếu với MISA (có chứng từ)"


class TrackedModel(models.Model):
    created_at = models.DateTimeField("Tạo lúc", auto_now_add=True)
    updated_at = models.DateTimeField("Cập nhật lúc", auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Người tạo",
        null=True,
        blank=True,
        editable=False,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Người cập nhật",
        null=True,
        blank=True,
        editable=False,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        abstract = True


class StatusEntryBase(models.Model):
    """Append-only status history row with explicit provenance.

    The approval chain is unconfirmed (CLAUDE.md §4.3–4.4), so the status is a
    free-text label rather than a hard-coded workflow.
    """

    status_label = models.CharField("Trạng thái", max_length=120)
    status_source = models.CharField(
        "Nguồn trạng thái",
        max_length=20,
        choices=StatusSource.choices,
        default=StatusSource.INTERNAL,
    )
    evidence_note = models.TextField("Bằng chứng / ghi chú", blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Người ghi nhận",
        on_delete=models.PROTECT,
        related_name="+",
    )
    recorded_at = models.DateTimeField("Ghi nhận lúc", auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ["-recorded_at", "-id"]

    def clean(self):
        super().clean()
        if self.status_source == StatusSource.MISA_REFERENCED and not self.evidence_note.strip():
            raise ValidationError(
                {
                    "evidence_note": "Cần ghi rõ bằng chứng (số chứng từ, người xác nhận...) "
                    "khi ghi nhận trạng thái theo MISA."
                }
            )

    def __str__(self):
        return self.status_label


class AuditLog(models.Model):
    class Action(models.TextChoices):
        CREATE = "CREATE", "Tạo mới"
        UPDATE = "UPDATE", "Cập nhật"
        DELETE = "DELETE", "Xoá"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Người thực hiện",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
    )
    action = models.CharField("Hành động", max_length=10, choices=Action.choices)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=64)
    object_repr = models.CharField("Đối tượng", max_length=255)
    changes = models.JSONField("Thay đổi", default=dict, blank=True)
    created_at = models.DateTimeField("Thời điểm", auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["content_type", "object_id"])]
        verbose_name = "Nhật ký thay đổi"
        verbose_name_plural = "Nhật ký thay đổi"

    def __str__(self):
        return f"{self.get_action_display()} {self.object_repr}"

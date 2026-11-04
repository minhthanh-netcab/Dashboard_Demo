from django.conf import settings
from django.db import models
from django.utils import timezone


# Display names for the `entity` keys used by sync jobs. Unknown keys fall back to the raw key.
ENTITY_LABELS = {
    "accounts": "Khách hàng",
    "opportunities": "Cơ hội bán hàng",
    "debt_balances": "Công nợ theo đối tượng",
    "inventory_balances": "Tồn kho theo kho",
}


class ExternalSystem(models.TextChoices):
    OPLACRM = "OPLACRM", "OplaCRM"
    MISA_ACT = "MISA_ACT", "MISA AMIS (ACT Open API)"


class SyncMode(models.TextChoices):
    MOCK = "MOCK", "Ngoại tuyến"
    LIVE = "LIVE", "Trực tuyến"


class SyncStatus(models.TextChoices):
    RUNNING = "RUNNING", "Đang chạy"
    SUCCESS = "SUCCESS", "Thành công"
    PARTIAL = "PARTIAL", "Thành công một phần"
    FAILED = "FAILED", "Thất bại"


class SyncRun(models.Model):
    """One execution of one sync job. Errors hold record refs and messages
    only — never credentials or raw payloads."""

    system = models.CharField("Hệ thống", max_length=20, choices=ExternalSystem.choices)
    entity = models.CharField("Loại dữ liệu", max_length=50)
    mode = models.CharField("Chế độ", max_length=10, choices=SyncMode.choices)
    status = models.CharField("Trạng thái", max_length=10, choices=SyncStatus.choices, default=SyncStatus.RUNNING)
    started_at = models.DateTimeField("Bắt đầu", default=timezone.now)
    finished_at = models.DateTimeField("Kết thúc", null=True, blank=True)
    fetched = models.PositiveIntegerField("Đọc được", default=0)
    created = models.PositiveIntegerField("Tạo mới", default=0)
    updated = models.PositiveIntegerField("Cập nhật", default=0)
    unchanged = models.PositiveIntegerField("Không đổi", default=0)
    failed = models.PositiveIntegerField("Lỗi", default=0)
    message = models.TextField("Thông báo", blank=True)
    errors = models.JSONField("Chi tiết lỗi", default=list, blank=True)
    warnings = models.JSONField("Cảnh báo", default=list, blank=True)
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Người chạy",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        ordering = ["-started_at", "-id"]
        verbose_name = "Lượt đồng bộ"
        verbose_name_plural = "Lượt đồng bộ"

    def __str__(self):
        return f"{self.get_system_display()} / {self.entity} @ {self.started_at:%d/%m/%Y %H:%M}"

    @property
    def entity_label(self):
        return ENTITY_LABELS.get(self.entity, self.entity)

    @property
    def is_simulated(self):
        return self.mode == SyncMode.MOCK


class SyncState(models.Model):
    """Where the next incremental sync should resume from.

    The cursor only advances after a fully successful run, so records that
    failed in a PARTIAL run are fetched again next time.
    """

    system = models.CharField("Hệ thống", max_length=20, choices=ExternalSystem.choices)
    entity = models.CharField("Loại dữ liệu", max_length=50)
    cursor = models.CharField("Mốc đồng bộ tăng dần", max_length=100, blank=True)
    last_success_at = models.DateTimeField("Thành công gần nhất", null=True, blank=True)
    last_run = models.ForeignKey(SyncRun, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["system", "entity"]
        verbose_name = "Trạng thái đồng bộ"
        verbose_name_plural = "Trạng thái đồng bộ"
        constraints = [models.UniqueConstraint(fields=["system", "entity"], name="uniq_sync_state")]

    def __str__(self):
        return f"{self.get_system_display()} / {self.entity}"

    @property
    def entity_label(self):
        return ENTITY_LABELS.get(self.entity, self.entity)

"""Read-only mirror of Sales data owned by OplaCRM (CLAUDE.md §3.4).

Rows are written only by the sync; users never edit them here.
"""

from django.db import models

from apps.core.models import SourceSystem


class SyncedRecord(models.Model):
    source_system = models.CharField(
        "Nguồn", max_length=20, choices=SourceSystem.choices, default=SourceSystem.OPLACRM
    )
    external_id = models.CharField("Mã nguồn", max_length=100)
    source_updated_at = models.DateTimeField("Cập nhật tại nguồn", null=True, blank=True)
    last_synced_at = models.DateTimeField("Đồng bộ lần cuối")
    is_simulated = models.BooleanField("Dữ liệu mô phỏng", default=False)

    class Meta:
        abstract = True


class SalesAccount(SyncedRecord):
    name = models.CharField("Tên khách hàng", max_length=255)

    class Meta:
        ordering = ["name"]
        verbose_name = "Khách hàng (OplaCRM)"
        verbose_name_plural = "Khách hàng (OplaCRM)"
        constraints = [
            models.UniqueConstraint(fields=["source_system", "external_id"], name="uniq_sales_account_source")
        ]

    def __str__(self):
        return self.name


class SalesOpportunity(SyncedRecord):
    FINANCE_FIELDS = ("amount",)

    account = models.ForeignKey(
        SalesAccount,
        verbose_name="Khách hàng",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="opportunities",
    )
    account_external_id = models.CharField("Mã khách hàng (nguồn)", max_length=100, blank=True)
    name = models.CharField("Tên cơ hội", max_length=255)
    amount = models.DecimalField("Giá trị", max_digits=18, decimal_places=2, null=True, blank=True)
    currency = models.CharField("Tiền tệ", max_length=3, default="VND")
    stage_name = models.CharField("Giai đoạn", max_length=100, blank=True)
    is_won = models.BooleanField("Đã thắng", default=False)
    expected_close_date = models.DateField("Ngày chốt dự kiến", null=True, blank=True)
    owner_name = models.CharField("Nhân viên kinh doanh", max_length=255, blank=True)

    class Meta:
        ordering = ["-source_updated_at", "name"]
        verbose_name = "Cơ hội bán hàng (OplaCRM)"
        verbose_name_plural = "Cơ hội bán hàng (OplaCRM)"
        constraints = [
            models.UniqueConstraint(fields=["source_system", "external_id"], name="uniq_sales_opportunity_source")
        ]

    def __str__(self):
        return self.name

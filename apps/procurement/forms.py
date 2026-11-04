from apps.core.models import StatusSource
from apps.projects.forms import ScopedModelForm

from .models import PurchaseItem, PurchaseRequest, PurchaseStatusEntry


class PurchaseRequestForm(ScopedModelForm):
    class Meta:
        model = PurchaseRequest
        fields = ["request_number", "title", "request_date", "supplier_name", "currency", "note", "tracking_closed"]


class PurchaseItemForm(ScopedModelForm):
    finance_fields = PurchaseItem.FINANCE_FIELDS

    class Meta:
        model = PurchaseItem
        fields = ["description", "quantity", "unit", "unit_cost"]


class StatusEntryFormMixin:
    """Users cannot pick DEMO; that value is reserved for seeded sample rows."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status_source"].choices = [c for c in StatusSource.choices if c[0] != StatusSource.DEMO]
        self.fields["status_label"].help_text = "Ví dụ: Đã trình Quản lý dự án, Đã lập chứng từ trên MISA…"


class PurchaseStatusEntryForm(StatusEntryFormMixin, ScopedModelForm):
    class Meta:
        model = PurchaseStatusEntry
        fields = ["status_label", "status_source", "evidence_note"]

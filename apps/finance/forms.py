from pathlib import Path

from django import forms
from django.utils import timezone

from apps.core.forms import BootstrapFormMixin

from .csv_import import MAX_FILE_BYTES
from .models import FinanceDataKind


class FinanceCsvImportForm(BootstrapFormMixin, forms.Form):
    data_kind = forms.ChoiceField(label="Loại dữ liệu", choices=FinanceDataKind.choices)
    as_of_date = forms.DateField(label="Số liệu tại ngày", initial=timezone.localdate)
    period_label = forms.CharField(label="Kỳ dữ liệu", required=False, help_text="Ví dụ: Tháng 10/2026.")
    file = forms.FileField(label="File CSV", help_text="Đúng biểu mẫu quy định, dung lượng tối đa 2 MB, mã hoá UTF-8.")

    def clean_file(self):
        upload = self.cleaned_data["file"]
        if Path(upload.name).suffix.lower() != ".csv":
            raise forms.ValidationError("Chỉ nhận file .csv.")
        if upload.size > MAX_FILE_BYTES:
            raise forms.ValidationError(f"File lớn hơn {MAX_FILE_BYTES // 1024} KB.")
        return upload

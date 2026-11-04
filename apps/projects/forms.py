from django import forms
from django.contrib.auth import get_user_model

from apps.accounts.roles import can_view_finance, is_project_manager, project_manager_users
from apps.core.forms import BootstrapFormMixin

from .models import (
    HandoverStatus,
    KickoffRecord,
    Project,
    ProjectContract,
    ProjectDocument,
    ProjectIssue,
    ProjectMember,
    ProjectMilestone,
    ProjectTask,
    ProgressUpdate,
    SalesHandover,
    TaskStatus,
)
from .permissions import project_participants


class ScopedModelForm(BootstrapFormMixin, forms.ModelForm):
    """ModelForm that knows the project and user it is used for.

    Fields listed in `finance_fields` are removed for users who may not see
    money values, so they are neither rendered nor accepted on POST.
    """

    finance_fields = ()

    def __init__(self, *args, project=None, user=None, **kwargs):
        self.project = project
        self.user = user
        super().__init__(*args, **kwargs)
        if user is not None and not can_view_finance(user):
            for name in self.finance_fields:
                self.fields.pop(name, None)


class ProjectForm(ScopedModelForm):
    class Meta:
        model = Project
        fields = [
            "name",
            "customer_name",
            "description",
            "status",
            "manager",
            "planned_start_date",
            "planned_end_date",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["manager"].queryset = project_manager_users()


class SalesHandoverForm(ScopedModelForm):
    finance_fields = SalesHandover.FINANCE_FIELDS

    class Meta:
        model = SalesHandover
        fields = [
            "deal_name",
            "customer_name",
            "external_opportunity_id",
            "external_account_id",
            "sales_owner_name",
            "committed_value",
            "currency",
            "committed_start_date",
            "committed_end_date",
            "committed_scope",
            "boq_reference",
        ]
        help_texts = {
            "external_opportunity_id": "Không bắt buộc. Mỗi cơ hội chỉ được lập một hồ sơ bàn giao.",
        }

    def clean_external_opportunity_id(self):
        # source_system is not a form field, so Django skips the DB constraint
        # during validation; check it here to show a form error instead of a 500.
        value = self.cleaned_data["external_opportunity_id"].strip()
        if value:
            duplicates = SalesHandover.objects.filter(
                source_system=self.instance.source_system, external_opportunity_id=value
            ).exclude(pk=self.instance.pk)
            if duplicates.exists():
                raise forms.ValidationError("Cơ hội này đã có hồ sơ bàn giao.")
        return value


class HandoverReviewForm(BootstrapFormMixin, forms.Form):
    status = forms.ChoiceField(
        label="Kết quả tiếp nhận",
        choices=[c for c in HandoverStatus.choices if c[0] != HandoverStatus.PENDING],
    )
    review_note = forms.CharField(label="Ghi chú", widget=forms.Textarea, required=False)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("status") in (HandoverStatus.NEEDS_INFO, HandoverStatus.REJECTED) and not cleaned.get(
            "review_note", ""
        ).strip():
            self.add_error("review_note", "Vui lòng ghi rõ thông tin cần bổ sung hoặc lý do từ chối.")
        return cleaned


class ProjectMemberForm(ScopedModelForm):
    class Meta:
        model = ProjectMember
        fields = ["user", "project_role"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["user"].queryset = (
            get_user_model()
            .objects.filter(is_active=True)
            .exclude(project_memberships__project=self.project)
            .order_by("username")
        )


class MilestoneForm(ScopedModelForm):
    class Meta:
        model = ProjectMilestone
        fields = ["name", "description", "due_date", "status", "completed_date", "sort_order"]


class TaskForm(ScopedModelForm):
    """Status is not editable here: status changes go through
    TaskStatusForm so that every change leaves a ProgressUpdate."""

    class Meta:
        model = ProjectTask
        fields = ["title", "description", "milestone", "assignee", "priority", "start_date", "due_date"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["milestone"].queryset = ProjectMilestone.objects.filter(project=self.project)
        self.fields["assignee"].queryset = project_participants(self.project)
        self.fields["assignee"].help_text = "Chỉ chọn được thành viên của dự án."


class TaskStatusForm(BootstrapFormMixin, forms.Form):
    status = forms.ChoiceField(label="Trạng thái mới", choices=TaskStatus.choices)
    percent = forms.IntegerField(label="% hoàn thành (tự báo cáo)", min_value=0, max_value=100, required=False)
    note = forms.CharField(label="Ghi chú", widget=forms.Textarea, required=False)


class ProgressUpdateForm(ScopedModelForm):
    class Meta:
        model = ProgressUpdate
        fields = ["task", "percent", "note"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tasks = ProjectTask.objects.filter(project=self.project)
        if not is_project_manager(self.user):
            tasks = tasks.filter(assignee=self.user)
        self.fields["task"].queryset = tasks


class IssueForm(ScopedModelForm):
    class Meta:
        model = ProjectIssue
        fields = ["kind", "title", "description", "severity", "status", "task", "assignee"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["task"].queryset = ProjectTask.objects.filter(project=self.project)
        self.fields["assignee"].queryset = project_participants(self.project)


class KickoffForm(ScopedModelForm):
    class Meta:
        model = KickoffRecord
        fields = ["meeting_date", "location", "attendees", "minutes", "follow_up"]


class ContractForm(ScopedModelForm):
    finance_fields = ProjectContract.FINANCE_FIELDS

    class Meta:
        model = ProjectContract
        fields = ["title", "contract_number", "status", "signed_date", "contract_value", "currency", "document", "note"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["document"].queryset = ProjectDocument.objects.filter(project=self.project)


class DocumentForm(ScopedModelForm):
    class Meta:
        model = ProjectDocument
        fields = ["doc_type", "title", "external_reference", "note"]

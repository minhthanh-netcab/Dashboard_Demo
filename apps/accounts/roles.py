"""Role names and role checks.

Role names follow CLAUDE.md §6.1 and are still proposals; each role is a
Django Group. The policy below is the Phase 1 assumption recorded in
docs/OPEN_QUESTIONS.md — change it here, not in views.
"""

from django.contrib.auth import get_user_model
from django.db.models import Q

PROJECT_MANAGER = "PROJECT_MANAGER"
PROJECT_MEMBER = "PROJECT_MEMBER"
SALES_VIEWER = "SALES_VIEWER"
FINANCE_VIEWER = "FINANCE_VIEWER"
SYSTEM_ADMIN = "SYSTEM_ADMIN"

ALL_ROLES = (PROJECT_MANAGER, PROJECT_MEMBER, SALES_VIEWER, FINANCE_VIEWER, SYSTEM_ADMIN)

ROLE_LABELS = {
    PROJECT_MANAGER: "Quản lý dự án",
    PROJECT_MEMBER: "Thành viên dự án",
    SALES_VIEWER: "Kinh doanh (chỉ xem)",
    FINANCE_VIEWER: "Tài chính – Kế toán",
    SYSTEM_ADMIN: "Quản trị hệ thống",
}


def role_names(user):
    if not user.is_authenticated:
        return set()
    if not hasattr(user, "_role_names"):
        user._role_names = set(user.groups.values_list("name", flat=True))
    return user._role_names


def role_display(user):
    if user.is_superuser:
        return "Quản trị (superuser)"
    labels = [ROLE_LABELS[role] for role in ALL_ROLES if role in role_names(user)]
    return ", ".join(labels) or "Chưa được phân quyền"


def has_role(user, role):
    return role in role_names(user)


def is_project_manager(user):
    """Project managers see and manage every project (assumption)."""
    return user.is_authenticated and (user.is_superuser or has_role(user, PROJECT_MANAGER))


def can_view_finance(user):
    """Money fields: PMs and FINANCE_VIEWER only; hidden from members (assumption)."""
    return is_project_manager(user) or has_role(user, FINANCE_VIEWER)


def can_view_handovers(user):
    return is_project_manager(user) or has_role(user, SALES_VIEWER)


def can_view_sales_data(user):
    """Synced OplaCRM read model (accounts, opportunities)."""
    return can_view_handovers(user)


def can_manage_integrations(user):
    """Start sync jobs (assumption: system admins only)."""
    return user.is_authenticated and (user.is_superuser or has_role(user, SYSTEM_ADMIN))


def can_view_integrations(user):
    return can_manage_integrations(user) or is_project_manager(user)


def can_import_finance(user):
    """Upload finance CSV reports (assumption: FINANCE_VIEWER only).

    Importers must also be able to see the result, so this stays a subset of
    can_view_finance.
    """
    return user.is_authenticated and (user.is_superuser or has_role(user, FINANCE_VIEWER))


def project_manager_users():
    return (
        get_user_model()
        .objects.filter(is_active=True)
        .filter(Q(groups__name=PROJECT_MANAGER) | Q(is_superuser=True))
        .distinct()
    )

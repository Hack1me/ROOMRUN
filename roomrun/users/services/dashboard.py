from __future__ import annotations

from dataclasses import dataclass

from core.utils.enums import UserRole
from django.utils.translation import gettext_lazy as _
from users.services.dashboards import GuardDashboardService
from users.services.dashboards import LandlordDashboardContext
from users.services.dashboards import LandlordDashboardService
from users.services.dashboards import MaintenanceDashboardService
from users.services.dashboards import TenantDashboardContext
from users.services.dashboards import TenantDashboardService


@dataclass(frozen=True)
class DashboardData:
    user: object
    role: str
    title: str
    available_roles: list[str]


class DashboardService:
    ROLE_DETECTION = [
        ("landlord_profile", UserRole.LANDLORD, _("Landlord Dashboard")),
        ("tenant_profile", UserRole.TENANT, _("Tenant Dashboard")),
    ]

    EMPLOYEE_ROLE_DETECTION = [
        ("guard_profile", UserRole.GUARD, _("Guard Dashboard")),
        ("maintenance_agent_profile", UserRole.MAINTENANCE, _("Maintenance Dashboard")),
    ]

    @staticmethod
    def get_available_dashboards(user) -> list[str]:
        dashboards: list[str] = []
        for attr_path, role, _title in DashboardService.ROLE_DETECTION:
            if DashboardService._has_attribute(user, attr_path):
                dashboards.append(role.value)

        if hasattr(user, "employee_profile"):
            employee = user.employee_profile
            for attr_path, role, _ in DashboardService.EMPLOYEE_ROLE_DETECTION:
                if DashboardService._has_attribute(employee, attr_path):
                    dashboards.append(role.value)

        return dashboards

    @staticmethod
    def get_primary_role(user) -> str:
        dashboards = DashboardService.get_available_dashboards(user)
        return dashboards[0] if dashboards else UserRole.USER.value

    @staticmethod
    def get_dashboard(user) -> DashboardData:
        available_roles = DashboardService.get_available_dashboards(user)
        primary_role = DashboardService.get_primary_role(user)
        title = DashboardService._get_title_for_role(primary_role)

        return DashboardData(
            user=user,
            role=primary_role,
            title=title,
            available_roles=available_roles,
        )

    @staticmethod
    def has_dashboard(user, role: str) -> bool:
        return role in DashboardService.get_available_dashboards(user)

    @staticmethod
    def get_title_for_role(role: str) -> str:
        return DashboardService._get_title_for_role(role)

    @staticmethod
    def _has_attribute(obj, attr_path: str) -> bool:
        parts = attr_path.split(".")
        current = obj
        for part in parts:
            if hasattr(current, part):
                current = getattr(current, part)
            else:
                return False
        return True

    @staticmethod
    def _get_title_for_role(role: str) -> str:
        for _attr_path, r, title in DashboardService.ROLE_DETECTION:
            if r.value == role:
                return title
        for _attr_path, r, title in DashboardService.EMPLOYEE_ROLE_DETECTION:
            if r.value == role:
                return title
        return _("Dashboard")


__all__ = [
    "DashboardData",
    "DashboardService",
    "GuardDashboardService",
    "LandlordDashboardContext",
    "LandlordDashboardService",
    "MaintenanceDashboardService",
    "TenantDashboardContext",
    "TenantDashboardService",
]

from __future__ import annotations

from dataclasses import dataclass

from billing.models import Payment
from django.db.models import Count
from django.db.models import Q
from django.db.models import Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from maintenance.models import MaintenanceRequest
from rentals.models import RentalApplication
from rentals.models import RentalContract
from users.models import User
from utils.enums import UserRole


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
        for attr_path, role, _ in DashboardService.ROLE_DETECTION:
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
        for _, r, title in DashboardService.ROLE_DETECTION:
            if r.value == role:
                return title
        for _, r, title in DashboardService.EMPLOYEE_ROLE_DETECTION:
            if r.value == role:
                return title
        return _("Dashboard")


@dataclass
class LandlordDashboardContext:
    landlord: object
    total_properties: int
    total_units: int
    occupancy_rate: float
    pending_maintenance: int
    recent_applications: list
    recent_properties: list
    recent_payments: list
    recent_maintenance_requests: list
    monthly_revenue: float
    property_count_by_status: dict
    tenant_count: int
    active_contracts: int


class LandlordDashboardService:
    RECENT_LIMIT = 5
    DEFAULT_DAYS = 30

    @classmethod
    def get_context(cls, user: User) -> dict:
        if not hasattr(user, "landlord_profile"):
            raise ValueError(_("User does not have a landlord profile."))

        landlord = user.landlord_profile
        return cls._build_landlord_data(landlord)

    @classmethod
    def _build_landlord_data(cls, landlord) -> dict:
        properties = landlord.properties.prefetch_related("buildings__units").all()
        recent_properties = properties.order_by("-created_at")[:cls.RECENT_LIMIT]
        total_properties = properties.count()
        total_units = sum(p.total_units for p in properties)

        total_occupied = sum(
            p.buildings.aggregate(
                occupied=Count("units", filter=Q(units__status="OCCUPIED"))
            )["occupied"] or 0
            for p in properties
        )
        occupancy_rate = (total_occupied / total_units * 100) if total_units > 0 else 0

        pending_maintenance = MaintenanceRequest.objects.filter(
            unit__building__property_ref__landlord=landlord,
            status="PENDING",
        ).count()

        recent_applications = RentalApplication.objects.filter(
            unit__building__property_ref__landlord=landlord,
        ).select_related(
            "tenant__user",
            "unit__building__property_ref",
        ).order_by("-created_at")[: cls.RECENT_LIMIT]

        recent_payments = Payment.objects.filter(
            charge__contract__unit__building__property_ref__landlord=landlord,
            status="COMPLETED",
        ).select_related("charge").order_by("-paid_at")[: cls.RECENT_LIMIT]

        recent_maintenance_requests = MaintenanceRequest.objects.filter(
            unit__building__property_ref__landlord=landlord,
        ).select_related(
            "tenant__user",
            "unit__building__property_ref",
        ).order_by("-created_at")[: cls.RECENT_LIMIT]

        monthly_revenue = RentalContract.objects.filter(
            unit__building__property_ref__landlord=landlord,
            status="ACTIVE",
        ).aggregate(total=Sum("monthly_rent"))["total"] or 0

        property_count_by_status = {
            "active": properties.filter(status="ACTIVE").count(),
            "inactive": properties.filter(status="INACTIVE").count(),
            "under_construction": properties.filter(
                status="UNDER_CONSTRUCTION"
            ).count(),
        }

        tenant_count = RentalContract.objects.filter(
            unit__building__property_ref__landlord=landlord,
            status="ACTIVE",
        ).values("tenant").distinct().count()

        active_contracts = RentalContract.objects.filter(
            unit__building__property_ref__landlord=landlord,
            status="ACTIVE",
        ).count()

        return {
            "landlord": landlord,
            "total_properties": total_properties,
            "total_units": total_units,
            "occupancy_rate": round(occupancy_rate, 1),
            "pending_maintenance": pending_maintenance,
            "recent_applications": recent_applications,
            "recent_properties": recent_properties,
            "recent_payments": recent_payments,
            "recent_maintenance_requests": recent_maintenance_requests,
            "monthly_revenue": monthly_revenue,
            "property_count_by_status": property_count_by_status,
            "tenant_count": tenant_count,
            "active_contracts": active_contracts,
        }

    @classmethod
    def get_context_structured(cls, user: User) -> LandlordDashboardContext:
        data = cls.get_context(user)
        return LandlordDashboardContext(
            landlord=data["landlord"],
            total_properties=data["total_properties"],
            total_units=data["total_units"],
            occupancy_rate=data["occupancy_rate"],
            pending_maintenance=data["pending_maintenance"],
            recent_applications=data["recent_applications"],
            recent_properties=data["recent_properties"],
            recent_payments=data["recent_payments"],
            recent_maintenance_requests=data["recent_maintenance_requests"],
            monthly_revenue=data["monthly_revenue"],
            property_count_by_status=data["property_count_by_status"],
            tenant_count=data["tenant_count"],
            active_contracts=data["active_contracts"],
        )


@dataclass
class TenantDashboardContext:
    tenant: object
    active_contract: object | None
    signing_contract: object | None
    unit: object | None
    property: object | None
    landlord: object | None
    upcoming_payments: list
    recent_maintenance_requests: list
    recent_payments: list
    rent_amount: float
    lease_start: object | None
    lease_end: object | None


class TenantDashboardService:
    RECENT_LIMIT = 5
    DAYS_UPCOMING = 30

    @classmethod
    def get_context(cls, user: User) -> dict:
        if not hasattr(user, "tenant_profile"):
            raise ValueError(_("User does not have a tenant profile."))

        tenant = user.tenant_profile
        return cls._build_tenant_data(tenant)

    @classmethod
    def _build_tenant_data(cls, tenant) -> dict:
        active_contract = (
            tenant.rental_contracts
            .filter(status="ACTIVE")
            .select_related(
                "unit__building__property_ref",
                "unit__building__property_ref__landlord",
            )
            .first()
        )
        signing_contract = (
            tenant.rental_contracts
            .filter(status="SIGNING")
            .select_related("unit__building__property_ref")
            .first()
        )

        unit = active_contract.unit if active_contract else None
        property_obj = unit.building.property_ref if unit else None
        landlord = property_obj.landlord if property_obj else None

        now = timezone.now()
        upcoming_cutoff = now + timezone.timedelta(days=cls.DAYS_UPCOMING)

        upcoming_payments = []
        if active_contract:
            upcoming_payments = (
                active_contract.charges
                .filter(
                    status="PENDING",
                    due_date__gte=now.date(),
                    due_date__lte=upcoming_cutoff.date(),
                )
                .order_by("due_date")
                [:cls.RECENT_LIMIT]
            )

        recent_maintenance = (
            tenant.maintenance_requests
            .order_by("-created_at")
            .select_related("unit__building__property_ref")
            [:cls.RECENT_LIMIT]
        )

        recent_payments = []
        if active_contract:
            recent_payments = (
                Payment.objects
                .filter(charge__contract=active_contract)
                .select_related("charge")
                .order_by("-paid_at")
                [:cls.RECENT_LIMIT]
            )

        lease_start = active_contract.start_date if active_contract else None
        lease_end = active_contract.end_date if active_contract else None
        rent_amount = active_contract.monthly_rent if active_contract else 0

        return {
            "tenant": tenant,
            "active_contract": active_contract,
            "signing_contract": signing_contract,
            "unit": unit,
            "property": property_obj,
            "landlord": landlord,
            "upcoming_payments": upcoming_payments,
            "recent_maintenance_requests": recent_maintenance,
            "recent_payments": recent_payments,
            "rent_amount": rent_amount,
            "lease_start": lease_start,
            "lease_end": lease_end,
        }

    @classmethod
    def get_context_structured(cls, user: User) -> TenantDashboardContext:
        data = cls.get_context(user)
        return TenantDashboardContext(
            tenant=data["tenant"],
            active_contract=data["active_contract"],
            unit=data["unit"],
            property=data["property"],
            landlord=data["landlord"],
            upcoming_payments=data["upcoming_payments"],
            recent_maintenance_requests=data["recent_maintenance_requests"],
            recent_payments=data["recent_payments"],
            rent_amount=data["rent_amount"],
            lease_start=data["lease_start"],
            lease_end=data["lease_end"],
        )


class MaintenanceDashboardService:
    RECENT_LIMIT = 5

    @staticmethod
    def get_context(user) -> dict:
        if not hasattr(user, "employee_profile"):
            raise ValueError(_("User does not have an employee profile."))

        employee = user.employee_profile
        if not hasattr(employee, "maintenance_agent_profile"):
            raise ValueError(_("Employee is not a maintenance agent."))

        agent = employee.maintenance_agent_profile
        return MaintenanceDashboardService._build_context(agent)

    @staticmethod
    def _build_context(agent) -> dict:
        tasks = agent.tasks.all()
        total_tasks = tasks.count()
        pending_tasks = tasks.filter(status="PENDING").count()
        in_progress_tasks = tasks.filter(status="IN_PROGRESS").count()
        completed_tasks = tasks.filter(status="COMPLETED").count()

        urgent_requests = MaintenanceRequest.objects.filter(
            tasks__maintenance_agent=agent,
            priority="URGENT",
            status="PENDING",
        ).distinct().count()

        recent_tasks = tasks.order_by("-created_at")[:MaintenanceDashboardService.RECENT_LIMIT]
        recent_requests = MaintenanceRequest.objects.filter(
            tasks__maintenance_agent=agent,
        ).distinct().order_by("-created_at")[:MaintenanceDashboardService.RECENT_LIMIT]

        completion_rate = (
            round((completed_tasks / total_tasks) * 100, 1)
            if total_tasks > 0
            else 0
        )

        return {
            "agent": agent,
            "total_tasks": total_tasks,
            "pending_tasks": pending_tasks,
            "in_progress_tasks": in_progress_tasks,
            "completed_tasks": completed_tasks,
            "urgent_requests": urgent_requests,
            "recent_tasks": recent_tasks,
            "recent_requests": recent_requests,
            "completion_rate": completion_rate,
        }

    @staticmethod
    def get_pending_tasks(user) -> list:
        if not hasattr(user, "employee_profile"):
            return []

        employee = user.employee_profile
        if not hasattr(employee, "maintenance_agent_profile"):
            return []

        agent = employee.maintenance_agent_profile
        return agent.tasks.filter(status="PENDING").order_by("-created_at")


class GuardDashboardService:
    RECENT_LIMIT = 5

    @staticmethod
    def get_context(user) -> dict:
        if not hasattr(user, "employee_profile"):
            raise ValueError(_("User does not have an employee profile."))

        employee = user.employee_profile
        if not hasattr(employee, "guard_profile"):
            raise ValueError(_("Employee is not a security guard."))

        guard = employee.guard_profile
        return GuardDashboardService._build_context(guard)

    @staticmethod
    def _build_context(guard) -> dict:
        now = timezone.now()
        today = now.date()
        logs = guard.logs.all() if hasattr(guard, "logs") else None

        total_logs = logs.count() if logs is not None else 0
        today_logs = logs.filter(created_at__date=today).count() if logs is not None else 0

        active_visitors = []
        if hasattr(guard, "visitors"):
            active_visitors = guard.visitors.filter(
                status="ACTIVE"
            ).count()

        recent_logs = logs.order_by("-created_at")[:GuardDashboardService.RECENT_LIMIT] if logs is not None else []

        expected_visitors = 0
        if hasattr(guard, "scheduled_visits"):
            expected_visitors = guard.scheduled_visits.filter(
                visit_date=today,
                status="SCHEDULED"
            ).count()

        shift_info = {
            "shift": guard.shift,
            "start_time": guard.shift_start_time if hasattr(guard, "shift_start_time") else None,
            "end_time": guard.shift_end_time if hasattr(guard, "shift_end_time") else None,
        }

        return {
            "guard": guard,
            "total_logs": total_logs,
            "today_logs": today_logs,
            "active_visitors": active_visitors,
            "expected_visitors": expected_visitors,
            "recent_logs": recent_logs,
            "shift_info": shift_info,
            "current_time": now,
            "today": today,
        }

    @staticmethod
    def get_today_logs(user):
        if not hasattr(user, "employee_profile"):
            return []

        employee = user.employee_profile
        if not hasattr(employee, "guard_profile"):
            return []

        guard = employee.guard_profile
        today = timezone.now().date()

        if hasattr(guard, "logs"):
            return guard.logs.filter(created_at__date=today).order_by("-created_at")

        return []

    @staticmethod
    def get_active_visitors(user):
        if not hasattr(user, "employee_profile"):
            return []

        employee = user.employee_profile
        if not hasattr(employee, "guard_profile"):
            return []

        guard = employee.guard_profile

        if hasattr(guard, "visitors"):
            return guard.visitors.filter(status="ACTIVE")

        return []

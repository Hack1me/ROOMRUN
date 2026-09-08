from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass

from billing.models import Payment
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count
from django.db.models import Q
from django.db.models import Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from maintenance.models import MaintenanceRequest
from rentals.models import RentalApplication
from rentals.models import RentalContract
from users.models import Otp
from users.tasks import send_otp_email_task
from utils.enums import OtpPurpose
from utils.enums import UserRole
from utils.otp import check_cooldown
from utils.otp import create_otp_token
from utils.otp import generate_otp_code
from utils.otp import hash_otp_code
from utils.otp import set_cooldown
from utils.otp import validate_otp_token

User = get_user_model()


class OtpRateLimitError(ValueError):
    pass


class OtpVerificationError(ValueError):
    pass


class OtpService:
    @staticmethod
    def create(user, purpose: str) -> tuple[Otp, str]:
        limited, _remaining = check_cooldown(str(user.pk), purpose)
        if limited:
            raise OtpRateLimitError(_("Please wait before requesting another code."))

        validity = int(getattr(settings, "OTP_VALID_MINUTES", 10))
        raw_code = generate_otp_code()
        expiration_at = timezone.now() + datetime.timedelta(minutes=validity)

        with transaction.atomic():
            Otp.objects.filter(user=user, purpose=purpose, is_used=False).update(
                is_used=True
            )
            otp = Otp.objects.create(
                user=user,
                purpose=purpose,
                code_hash=hash_otp_code(raw_code),
                expiration_at=expiration_at,
            )
            set_cooldown(str(user.pk), purpose)

        otp._raw_code = raw_code  # noqa: SLF001
        token = create_otp_token(str(otp.pk), str(user.pk), purpose)
        return otp, token


class OtpEmailService:
    @staticmethod
    def send(user, otp: Otp, language: str | None = None) -> None:
        raw_code = getattr(otp, "_raw_code", None)
        if not raw_code:
            msg = "Raw OTP code is required."
            raise ValueError(msg)

        full_name = user.full_name or user.email
        validity = int(getattr(settings, "OTP_VALID_MINUTES", 10))
        lang = language or getattr(user, "language", None) or settings.LANGUAGE_CODE

        transaction.on_commit(
            lambda: send_otp_email_task.delay(
                email=user.email,
                full_name=full_name,
                code=raw_code,
                validity=validity,
                language=lang,
            ),
        )


class OtpVerifyService:
    @staticmethod
    def _resolve_otp(token: str, purpose: str) -> Otp:
        token_data = validate_otp_token(token, purpose)
        try:
            return (
                Otp.objects.select_for_update()
                .select_related("user")
                .get(
                    pk=token_data["otp_id"],
                    user_id=token_data["user_id"],
                    purpose=purpose,
                )
            )
        except Otp.DoesNotExist as err:
            raise OtpVerificationError(
                _("This verification code could not be found.")
            ) from err

    @staticmethod
    def verify(token: str, code: str, purpose: str) -> Otp:
        with transaction.atomic():
            otp = OtpVerifyService._resolve_otp(token, purpose)
            if otp.is_used or otp.is_expired():
                raise OtpVerificationError(
                    _("This code has expired. Request a new one.")
                )
            if not otp.can_attempt():
                raise OtpVerificationError(_("Too many attempts. Request a new code."))

            otp.increment_attempts()
            if not otp.is_valid_code(code):
                raise OtpVerificationError(_("The code you entered is incorrect."))

            otp.mark_verified()
            if purpose in {OtpPurpose.SIGNUP, OtpPurpose.LOGIN}:
                user = otp.user
                user.email_verified = True
                user.save(update_fields=["email_verified"])
            return otp


class PasswordResetTokenService:
    timeout = getattr(settings, "RESET_TOKEN_TIMEOUT", 900)

    @staticmethod
    def generate(user) -> str:
        token = str(uuid.uuid4())
        cache.set(
            f"password_reset_token:{token}",
            str(user.pk),
            timeout=PasswordResetTokenService.timeout,
        )
        return token

    @staticmethod
    def get_user_id(token: str) -> str | None:
        if not token:
            return None
        return cache.get(f"password_reset_token:{token}")

    @staticmethod
    def delete(token: str) -> None:
        cache.delete(f"password_reset_token:{token}")

#===================== Dashboard Service ====================
@dataclass(frozen=True)
class DashboardData:
    """
    Structured dashboard data returned by DashboardService.

    Attributes:
        user: The authenticated user instance.
        role: The user's primary role as a string (from DashboardRole enum).
        title: The translated dashboard title.
        available_roles: List of all roles available to this user.
    """
    user: object
    role: str
    title: str
    available_roles: list[str]


class DashboardService:
    """
    Service responsible for determining which dashboards are available
    to a user and managing role-based redirections.

    The service detects user roles by checking for the existence of
    profile attributes (e.g., `landlord_profile`, `tenant_profile`).
    """

    # =====================================================================
    # Configuration: Role Detection Rules
    # =====================================================================

    # Configuration list: (profile_attribute_path, role, title)
    # The order determines priority for the primary role.
    ROLE_DETECTION = [
        ("landlord_profile", UserRole.LANDLORD, _("Landlord Dashboard")),
        ("tenant_profile", UserRole.TENANT, _("Tenant Dashboard")),
    ]

    # Specialized roles nested under employee_profile
    EMPLOYEE_ROLE_DETECTION = [
        ("guard_profile", UserRole.GUARD, _("Guard Dashboard")),
        ("maintenance_agent_profile", UserRole.MAINTENANCE, _("Maintenance Dashboard")),
    ]

    # =====================================================================
    # Public Methods
    # =====================================================================

    @staticmethod
    def get_available_dashboards(user) -> list[str]:
        """
        Return a list of all dashboard roles available to the user.

        Args:
            user: The authenticated user instance.

        Returns:
            A list of role strings (e.g., ['landlord', 'tenant']).
            Returns an empty list if no profiles are found.
        """
        dashboards: list[str] = []

        # Check primary profiles
        for attr_path, role, _ in DashboardService.ROLE_DETECTION:  # noqa: F402
            if DashboardService._has_attribute(user, attr_path):
                dashboards.append(role.value)

        # Check employee sub-profiles (nested)
        if hasattr(user, "employee_profile"):
            employee = user.employee_profile
            for attr_path, role, _ in DashboardService.EMPLOYEE_ROLE_DETECTION:
                if DashboardService._has_attribute(employee, attr_path):
                    dashboards.append(role.value)

        return dashboards

    @staticmethod
    def get_primary_role(user) -> str:
        """
        Return the primary (first) dashboard role for the user.

        Args:
            user: The authenticated user.

        Returns:
            The primary role string, or 'user' if no roles are available.
        """
        dashboards = DashboardService.get_available_dashboards(user)
        return dashboards[0] if dashboards else UserRole.USER.value

    @staticmethod
    def get_dashboard(user) -> DashboardData:
        """
        Get complete dashboard data for the user.

        Args:
            user: The authenticated user.

        Returns:
            DashboardData with user, role, title, and available roles.
        """
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
        """
        Check if a user has access to a specific dashboard role.

        Args:
            user: The authenticated user.
            role: The role string (e.g., 'landlord').

        Returns:
            True if the user has that dashboard, False otherwise.
        """
        return role in DashboardService.get_available_dashboards(user)

    @staticmethod
    def get_title_for_role(role: str) -> str:
        """
        Get the translated title for a given role.

        Args:
            role: The role string (e.g., 'landlord').

        Returns:
            The translated title, or 'Dashboard' if the role is unknown.
        """
        return DashboardService._get_title_for_role(role)

    # =====================================================================
    # Internal Helpers
    # =====================================================================

    @staticmethod
    def _has_attribute(obj, attr_path: str) -> bool:
        """
        Check if an object has a nested attribute path.

        Args:
            obj: The object to check.
            attr_path: Dot-separated path (e.g., 'employee_profile.guard_profile').

        Returns:
            True if all attributes exist, False otherwise.
        """
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
        """
        Get the translated title for a given role.

        Args:
            role: The role string.

        Returns:
            The translated title, or 'Dashboard' if the role is unknown.
        """
        # Check primary roles
        for _, r, title in DashboardService.ROLE_DETECTION:
            if r.value == role:
                return title

        # Check employee roles
        for _, r, title in DashboardService.EMPLOYEE_ROLE_DETECTION:
            if r.value == role:
                return title

        # Fallback
        return _("Dashboard")


# ===================== Landlord Dashboard Service ====================
@dataclass
class LandlordDashboardContext:
    """
    Structured data for the landlord dashboard.

    Attributes:
        landlord: The landlord profile instance.
        total_properties: Total number of properties owned.
        total_units: Total number of rental units across all properties.
        occupancy_rate: Percentage of occupied units (0-100).
        pending_maintenance: Number of pending maintenance requests.
        recent_applications: Recent rental applications (up to 5).
        recent_properties: Recent properties (up to 5).
        monthly_revenue: Total monthly rent collected.
        property_count_by_status: Count of properties grouped by status.
        tenant_count: Total number of tenants.
        active_contracts: Number of active rental contracts.
    """
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
    """
    Service responsible for preparing landlord-specific dashboard data.
    Includes statistics, recent activity, and aggregated metrics.
    """

    # Configurable limits
    RECENT_LIMIT = 5
    DEFAULT_DAYS = 30

    @classmethod
    def get_context(cls, user: User) -> dict:
        """
        Prepare the dashboard context for a landlord user.

        Args:
            user: The authenticated user (must have landlord_profile).

        Returns:
            A dict with all context data for the landlord dashboard.

        Raises:
            ValueError: If the user does not have a landlord profile.
        """
        if not hasattr(user, "landlord_profile"):
            raise ValueError(_("User does not have a landlord profile."))

        landlord = user.landlord_profile
        return cls._build_landlord_data(landlord)

    @classmethod
    def _build_landlord_data(cls, landlord) -> dict:
        """
        Build the full context dictionary for a landlord.

        This method aggregates data from related models and returns
        a dict ready for template rendering.
        """
        # Prefetch properties with their related buildings and units
        properties = landlord.properties.prefetch_related("buildings__units").all()

        # Recent properties (last 5)
        recent_properties = properties.order_by("-created_at")[:cls.RECENT_LIMIT]

        # Count total properties
        total_properties = properties.count()

        # Count total units
        total_units = sum(p.total_units for p in properties)

        # Calculate occupancy rate (if there are units)
        total_occupied = sum(
            p.buildings.aggregate(
                occupied=Count("units", filter=Q(units__status="OCCUPIED"))
            )["occupied"] or 0
            for p in properties
        )
        occupancy_rate = (total_occupied / total_units * 100) if total_units > 0 else 0

        # Pending maintenance requests
        pending_maintenance = MaintenanceRequest.objects.filter(
            unit__building__property_ref__landlord=landlord,
            status="PENDING",
        ).count()

        # Recent rental applications
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

        # Monthly revenue (from active contracts)
        monthly_revenue = RentalContract.objects.filter(
            unit__building__property_ref__landlord=landlord,
            status="ACTIVE",
        ).aggregate(total=Sum("monthly_rent"))["total"] or 0

        # Property count by status
        property_count_by_status = {
            "active": properties.filter(status="ACTIVE").count(),
            "inactive": properties.filter(status="INACTIVE").count(),
            "under_construction": properties.filter(
                status="UNDER_CONSTRUCTION"
            ).count(),
        }

        # Total tenants (unique across all properties)
        tenant_count = RentalContract.objects.filter(
            unit__building__property_ref__landlord=landlord,
            status="ACTIVE",
        ).values("tenant").distinct().count()

        # Active contracts count
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
        """
        Return the context as a structured dataclass instead of a dict.

        This is useful for type safety and better code completion in IDEs.
        """
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

# Tenant Dashboard Context and Service
@dataclass
class TenantDashboardContext:
    """
    Structured data for the tenant dashboard.

    Attributes:
        tenant: The tenant profile instance.
        active_contract: The current active rental contract (or None).
        unit: The unit associated with the active contract.
        property: The property of the unit.
        landlord: The landlord of the property.
        upcoming_payments: List of upcoming charges (due soon).
        recent_maintenance_requests: Recent maintenance requests (limit 5).
        recent_payments: Recent payments made (limit 5).
        rent_amount: Monthly rent amount.
        lease_start: Contract start date.
        lease_end: Contract end date (or None if open-ended).
    """
    tenant: object
    active_contract: object | None
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
    """
    Service responsible for preparing tenant-specific dashboard data.
    Includes active lease, payment summary, and recent activity.
    """

    RECENT_LIMIT = 5
    DAYS_UPCOMING = 30  # Payments due within this many days

    @classmethod
    def get_context(cls, user: User) -> dict:
        """
        Prepare the dashboard context for a tenant user.

        Args:
            user: The authenticated user (must have tenant_profile).

        Returns:
            A dict with all context data for the tenant dashboard.

        Raises:
            ValueError: If the user does not have a tenant profile.
        """
        if not hasattr(user, "tenant_profile"):
            raise ValueError(_("User does not have a tenant profile."))

        tenant = user.tenant_profile
        return cls._build_tenant_data(tenant)

    @classmethod
    def _build_tenant_data(cls, tenant) -> dict:
        """
        Build the full context dictionary for a tenant.
        """
        # Fetch active contract (with related data)
        active_contract = (
            tenant.rental_contracts
            .filter(status="ACTIVE")
            .select_related(
                "unit__building__property_ref",
                "unit__building__property_ref__landlord",
            )
            .first()
        )

        unit = active_contract.unit if active_contract else None
        property_obj = unit.building.property_ref if unit else None
        landlord = property_obj.landlord if property_obj else None

        # Upcoming payments (charges due soon)
        now = timezone.now()
        upcoming_cutoff = now + timezone.timedelta(days=cls.DAYS_UPCOMING)

        upcoming_payments = []
        if active_contract:
            # Fetch charges for this contract that are pending and due soon
            upcoming_payments = (
                active_contract.charges
                .filter(
                    status="PENDING",
                    due_date__gte=now.date(),
                    due_date__lte=upcoming_cutoff.date()
                )
                .order_by("due_date")
                [:cls.RECENT_LIMIT]
            )

        # Recent maintenance requests
        recent_maintenance = (
            tenant.maintenance_requests
            .order_by("-created_at")
            .select_related("unit__building__property_ref")
            [:cls.RECENT_LIMIT]
        )

        # Recent payments (payments for this contract's charges)
        recent_payments = []
        if active_contract:
            recent_payments = (
                Payment.objects
                .filter(charge__contract=active_contract)
                .select_related("charge")
                .order_by("-paid_at")
                [:cls.RECENT_LIMIT]
            )

        # Lease dates
        lease_start = active_contract.start_date if active_contract else None
        lease_end = active_contract.end_date if active_contract else None
        rent_amount = active_contract.monthly_rent if active_contract else 0

        return {
            "tenant": tenant,
            "active_contract": active_contract,
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
        """
        Return the context as a structured dataclass for type safety.
        """
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

# Maintenance agent service
class MaintenanceDashboardService:
    """
    Service responsible for preparing maintenance agent-specific dashboard data.
    Includes task statistics, pending requests, and recent activity.
    """

    RECENT_LIMIT = 5

    @staticmethod
    def get_context(user) -> dict:
        """
        Prepare the dashboard context for a maintenance agent.

        Args:
            user: The authenticated user (must have maintenance_agent_profile).

        Returns:
            A dict with context data for the maintenance dashboard.

        Raises:
            ValueError: If the user does not have a maintenance agent profile.
        """
        # Check if user has employee profile
        if not hasattr(user, "employee_profile"):
            raise ValueError(_("User does not have an employee profile."))

        employee = user.employee_profile

        # Check if employee has maintenance agent profile
        if not hasattr(employee, "maintenance_agent_profile"):
            raise ValueError(_("Employee is not a maintenance agent."))

        agent = employee.maintenance_agent_profile

        return MaintenanceDashboardService._build_context(agent)

    @staticmethod
    def _build_context(agent) -> dict:
        """
        Build the full context dictionary for a maintenance agent.
        """
        # Get all tasks associated with this agent
        tasks = agent.tasks.all()

        # Statistics
        total_tasks = tasks.count()
        pending_tasks = tasks.filter(status="PENDING").count()
        in_progress_tasks = tasks.filter(status="IN_PROGRESS").count()
        completed_tasks = tasks.filter(status="COMPLETED").count()

        # Urgent maintenance requests associated with this agent's tasks
        urgent_requests = MaintenanceRequest.objects.filter(
            tasks__maintenance_agent=agent,
            priority="URGENT",
            status="PENDING",
        ).distinct().count()

        # Recent tasks (last 5)
        recent_tasks = tasks.order_by("-created_at")[:MaintenanceDashboardService.RECENT_LIMIT]

        # Recent maintenance requests linked to this agent's tasks (last 5)
        recent_requests = MaintenanceRequest.objects.filter(
            tasks__maintenance_agent=agent,
        ).distinct().order_by("-created_at")[:MaintenanceDashboardService.RECENT_LIMIT]

        # Completion rate (percentage of tasks completed)
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
        """
        Get all pending tasks for a maintenance agent.

        Args:
            user: The authenticated user.

        Returns:
            A queryset of pending tasks.
        """
        if not hasattr(user, "employee_profile"):
            return []

        employee = user.employee_profile
        if not hasattr(employee, "maintenance_agent_profile"):
            return []

        agent = employee.maintenance_agent_profile
        return agent.tasks.filter(status="PENDING").order_by("-created_at")

# Guard service
class GuardDashboardService:
    """
    Service responsible for preparing guard-specific dashboard data.
    Includes visitor statistics, entry logs, and shift information.
    """

    RECENT_LIMIT = 5

    @staticmethod
    def get_context(user) -> dict:
        """
        Prepare the dashboard context for a security guard.

        Args:
            user: The authenticated user (must have guard_profile).

        Returns:
            A dict with context data for the guard dashboard.

        Raises:
            ValueError: If the user does not have a guard profile.
        """
        # Check if user has employee profile
        if not hasattr(user, "employee_profile"):
            raise ValueError(_("User does not have an employee profile."))

        employee = user.employee_profile

        # Check if employee has guard profile
        if not hasattr(employee, "guard_profile"):
            raise ValueError(_("Employee is not a security guard."))

        guard = employee.guard_profile

        return GuardDashboardService._build_context(guard)

    @staticmethod
    def _build_context(guard) -> dict:
        """
        Build the full context dictionary for a security guard.
        """
        # Get current time and today's date
        now = timezone.now()
        today = now.date()

        # Get all entries/logs associated with this guard
        # Assuming there's a GuardLog or similar model
        logs = guard.logs.all() if hasattr(guard, "logs") else []

        # Statistics
        total_logs = logs.count()
        today_logs = logs.filter(created_at__date=today).count() if logs else 0

        # Active visitors (if you have a Visitor model)
        active_visitors = []
        if hasattr(guard, "visitors"):
            active_visitors = guard.visitors.filter(
                status="ACTIVE"
            ).count()

        # Recent entries (last 5)
        recent_logs = logs.order_by("-created_at")[:GuardDashboardService.RECENT_LIMIT] if logs else []

        # Expected visitors (scheduled visits)
        expected_visitors = 0
        if hasattr(guard, "scheduled_visits"):
            expected_visitors = guard.scheduled_visits.filter(
                visit_date=today,
                status="SCHEDULED"
            ).count()

        # Shift information
        shift_info = {
            "shift": guard.shift,  # DAY, NIGHT, etc.
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
        """
        Get all guard logs for today.

        Args:
            user: The authenticated user.

        Returns:
            A queryset of today's logs.
        """
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
        """
        Get all active visitors for the guard.

        Args:
            user: The authenticated user.

        Returns:
            A queryset of active visitors.
        """
        if not hasattr(user, "employee_profile"):
            return []

        employee = user.employee_profile
        if not hasattr(employee, "guard_profile"):
            return []

        guard = employee.guard_profile

        if hasattr(guard, "visitors"):
            return guard.visitors.filter(status="ACTIVE")

        return []

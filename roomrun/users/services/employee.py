from django.db.models import Q
from django.db.models import QuerySet
from users.models import Employee
from utils.enums import EmployeeStatus
from utils.enums import UserRole


class EmployeeService:
    """
    Business logic for employee management.
    """

    @staticmethod
    def get_list(
        *,
        landlord,
        search: str = "",
        employee_type: str = "",
        status: str = "",
    ) -> QuerySet[Employee]:
        """
        Return employees linked to the given landlord.

        An employee is considered linked to a landlord if:
        - they are a Guard employed by that landlord (Guard.landlord FK), OR
        - they are a MaintenanceAgent working for that landlord (M2M).

        Supports filtering by:
        - employee number, first name, last name, email (search)
        - employee type (UserRole.GUARD / UserRole.MAINTENANCE)
        - employee status (from EmployeeStatus enum)
        """
        queryset = (
            Employee.objects
            .select_related(
                "user",
                "guard_profile",
                "maintenance_agent_profile",
            )
            .filter(
                Q(guard_profile__landlord=landlord)
                | Q(maintenance_agent_profile__landlords=landlord)
            )
            .distinct()   # required because of the M2M join
            .order_by("user__last_name", "user__first_name")
        )

        # ---------------------------------------------------------
        # Search
        # ---------------------------------------------------------
        search = search.strip()
        if search:
            queryset = queryset.filter(
                Q(employee_number__icontains=search)
                | Q(user__first_name__icontains=search)
                | Q(user__last_name__icontains=search)
                | Q(user__email__icontains=search)
            )

        # ---------------------------------------------------------
        # Employee type (using UserRole)
        # ---------------------------------------------------------
        if employee_type == UserRole.GUARD:
            queryset = queryset.filter(guard_profile__isnull=False)
        elif employee_type == UserRole.MAINTENANCE:
            queryset = queryset.filter(maintenance_agent_profile__isnull=False)

        # ---------------------------------------------------------
        # Status
        # ---------------------------------------------------------
        if status in EmployeeStatus.values:
            queryset = queryset.filter(status=status)

        return queryset

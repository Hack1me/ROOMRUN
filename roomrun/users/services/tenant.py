from django.db.models import Q
from django.db.models import QuerySet
from users.models import Tenant


class TenantService:
    """
    Business logic related to tenants.
    """

    @staticmethod
    def get_list(
        *,
        landlord,
        search: str = "",
        user_status: str = "",
        verified: bool | None = None,
    ) -> QuerySet[Tenant]:
        """
        Return tenants related to the given landlord.

        A tenant is "related" to a landlord if they have at least one
        rental contract on one of the landlord's properties.

        Supports searching by:
        - first name / last name
        - email
        - tenant number

        Supports filtering by:
        - user_status (from User.UserStatus enum)
        - verified (True / False / None)
        """
        queryset = (
            Tenant.objects
            .select_related("user")
            .filter(
                rental_contracts__unit__building__property_ref__landlord=landlord,
            )
            .distinct()
            .order_by("user__last_name", "user__first_name")
        )

        search = search.strip()
        if search:
            queryset = queryset.filter(
                Q(tenant_number__icontains=search)
                | Q(user__first_name__icontains=search)
                | Q(user__last_name__icontains=search)
                | Q(user__email__icontains=search)
            )

        if user_status:
            queryset = queryset.filter(user__status=user_status)

        if verified is not None:
            queryset = queryset.filter(verified=verified)

        return queryset

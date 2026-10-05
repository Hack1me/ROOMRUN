from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from billing.models import Payment
from django.db.models import Count
from django.db.models import Sum
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.translation import gettext_lazy as _
from utils.enums import PaymentStatus
from utils.enums import RequestStatus

if TYPE_CHECKING:
    from users.models import User


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
    rent_amount: object
    lease_start: object | None
    lease_end: object | None
    open_maintenance_count: int
    tenant_chart_data: dict


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
            tenant.rental_contracts.filter(status="ACTIVE")
            .select_related(
                "unit__building__property_ref",
                "unit__building__property_ref__landlord",
            )
            .first()
        )
        signing_contract = (
            tenant.rental_contracts.filter(status="SIGNING")
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
            upcoming_payments = active_contract.charges.filter(
                status__in=["PENDING", "PARTIAL", "OVERDUE"],
                due_date__lte=upcoming_cutoff.date(),
            ).order_by("due_date")[: cls.RECENT_LIMIT]

        recent_maintenance = tenant.maintenance_requests.order_by(
            "-created_at"
        ).select_related("unit__building__property_ref")[: cls.RECENT_LIMIT]

        recent_payments = []
        if active_contract:
            recent_payments = (
                Payment.objects.filter(charge__contract=active_contract)
                .select_related("charge")
                .order_by("-created_at")[: cls.RECENT_LIMIT]
            )

        open_maintenance_count = tenant.maintenance_requests.exclude(
            status__in=[RequestStatus.RESOLVED, RequestStatus.CANCELLED]
        ).count()

        expense_queryset = (
            Payment.objects.filter(
                charge__contract=active_contract,
                status=PaymentStatus.COMPLETED,
                paid_at__isnull=False,
            )
            if active_contract
            else Payment.objects.none()
        )
        expense_labels = []
        expense_data = []
        today = timezone.localdate()
        for offset in range(5, -1, -1):
            month_index = today.year * 12 + today.month - 1 - offset
            year, month = divmod(month_index, 12)
            month += 1
            month_date = today.replace(year=year, month=month, day=1)
            expense_labels.append(str(date_format(month_date, "M")))
            expense_data.append(
                float(
                    expense_queryset.filter(
                        paid_at__year=year, paid_at__month=month
                    ).aggregate(total=Sum("amount"))["total"]
                    or 0
                )
            )

        maintenance_counts = dict(
            tenant.maintenance_requests.values("status")
            .annotate(total=Count("pk"))
            .values_list("status", "total")
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
            "open_maintenance_count": open_maintenance_count,
            "tenant_chart_data": {
                "expenses": {"labels": expense_labels, "data": expense_data},
                "maintenance": {
                    "labels": [
                        str(_("Resolved")),
                        str(_("In progress")),
                        str(_("Pending")),
                        str(_("Cancelled")),
                    ],
                    "data": [
                        maintenance_counts.get(RequestStatus.RESOLVED, 0),
                        maintenance_counts.get(RequestStatus.IN_PROGRESS, 0),
                        maintenance_counts.get(RequestStatus.PENDING, 0),
                        maintenance_counts.get(RequestStatus.CANCELLED, 0),
                    ],
                },
            },
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
            signing_contract=data["signing_contract"],
            unit=data["unit"],
            property=data["property"],
            landlord=data["landlord"],
            upcoming_payments=data["upcoming_payments"],
            recent_maintenance_requests=data["recent_maintenance_requests"],
            recent_payments=data["recent_payments"],
            rent_amount=data["rent_amount"],
            lease_start=data["lease_start"],
            lease_end=data["lease_end"],
            open_maintenance_count=data["open_maintenance_count"],
            tenant_chart_data=data["tenant_chart_data"],
        )

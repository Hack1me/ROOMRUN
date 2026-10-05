from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from billing.models import Payment
from django.db.models import Sum
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.translation import gettext_lazy as _
from maintenance.models import MaintenanceRequest
from properties.models import Unit
from rentals.models import RentalApplication
from rentals.models import RentalContract
from utils.enums import ContractStatus
from utils.enums import PaymentStatus
from utils.enums import RequestStatus

if TYPE_CHECKING:
    from users.models import User


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
        properties = landlord.properties.all()
        recent_properties = properties.order_by("-created_at")[: cls.RECENT_LIMIT]
        total_properties = properties.count()
        unit_queryset = Unit.objects.filter(building__property_ref__landlord=landlord)
        total_units = unit_queryset.count()
        total_occupied = unit_queryset.filter(status="OCCUPIED").count()
        occupancy_rate = (total_occupied / total_units * 100) if total_units > 0 else 0

        pending_maintenance = MaintenanceRequest.objects.filter(
            unit__building__property_ref__landlord=landlord,
            status="PENDING",
        ).count()

        recent_applications = (
            RentalApplication.objects.filter(
                unit__building__property_ref__landlord=landlord,
            )
            .select_related(
                "tenant__user",
                "unit__building__property_ref",
            )
            .order_by("-created_at")[: cls.RECENT_LIMIT]
        )

        recent_payments = (
            Payment.objects.filter(
                charge__contract__unit__building__property_ref__landlord=landlord,
                status=PaymentStatus.COMPLETED,
            )
            .select_related(
                "charge__contract__tenant__user",
                "charge__contract__unit__building__property_ref",
            )
            .order_by("-paid_at")[: cls.RECENT_LIMIT]
        )

        recent_maintenance_requests = (
            MaintenanceRequest.objects.filter(
                unit__building__property_ref__landlord=landlord,
            )
            .select_related(
                "tenant__user",
                "unit__building__property_ref",
            )
            .order_by("-created_at")[: cls.RECENT_LIMIT]
        )

        active_contracts_queryset = RentalContract.objects.filter(
            unit__building__property_ref__landlord=landlord,
            status=ContractStatus.ACTIVE,
        )
        monthly_revenue = (
            active_contracts_queryset.aggregate(total=Sum("monthly_rent"))["total"] or 0
        )

        property_count_by_status = {
            "active": properties.filter(status="ACTIVE").count(),
            "inactive": properties.filter(status="INACTIVE").count(),
            "under_construction": properties.filter(
                status="UNDER_CONSTRUCTION"
            ).count(),
        }

        tenant_count = active_contracts_queryset.values("tenant").distinct().count()
        active_contracts = active_contracts_queryset.count()

        payment_queryset = Payment.objects.filter(
            charge__contract__unit__building__property_ref__landlord=landlord,
            status=PaymentStatus.COMPLETED,
            paid_at__isnull=False,
        )
        today = timezone.localdate()
        revenue_labels = []
        revenue_data = []
        for offset in range(5, -1, -1):
            month_index = today.year * 12 + today.month - 1 - offset
            year, month = divmod(month_index, 12)
            month += 1
            month_date = today.replace(year=year, month=month, day=1)
            revenue_labels.append(date_format(month_date, "M"))
            revenue_data.append(
                float(
                    payment_queryset.filter(
                        paid_at__year=year, paid_at__month=month
                    ).aggregate(total=Sum("amount"))["total"]
                    or 0
                )
            )

        occupied_units = unit_queryset.filter(status="OCCUPIED").count()
        available_units = unit_queryset.filter(
            status__in=["AVAILABLE", "RESERVED"]
        ).count()
        maintenance_units = unit_queryset.filter(status="MAINTENANCE").count()
        inactive_units = unit_queryset.filter(status="INACTIVE").count()

        maintenance_queryset = MaintenanceRequest.objects.filter(
            unit__building__property_ref__landlord=landlord
        )
        maintenance_labels = []
        maintenance_new = []
        maintenance_in_progress = []
        maintenance_completed = []
        for offset in range(3, -1, -1):
            month_index = today.year * 12 + today.month - 1 - offset
            year, month = divmod(month_index, 12)
            month += 1
            month_date = today.replace(year=year, month=month, day=1)
            requests_in_month = maintenance_queryset.filter(
                created_at__year=year, created_at__month=month
            )
            maintenance_labels.append(date_format(month_date, "M"))
            maintenance_new.append(
                requests_in_month.filter(status=RequestStatus.PENDING).count()
            )
            maintenance_in_progress.append(
                requests_in_month.filter(status=RequestStatus.IN_PROGRESS).count()
            )
            maintenance_completed.append(
                requests_in_month.filter(status=RequestStatus.RESOLVED).count()
            )

        recent_activities = [
            {
                "kind": "payment",
                "title": payment.charge.get_charge_type_display(),
                "subtitle": payment.charge.contract.tenant.user.full_name,
                "date": payment.paid_at or payment.created_at,
                "amount": payment.amount,
                "url_name": "billing:landlord-wallet",
            }
            for payment in recent_payments
        ]
        recent_activities.extend(
            {
                "kind": "maintenance",
                "title": request.title,
                "subtitle": request.unit.building.property_ref.name,
                "date": request.created_at,
                "url_name": "maintenance:landlord-request-detail",
                "url_pk": request.pk,
            }
            for request in recent_maintenance_requests
        )
        recent_activities.extend(
            {
                "kind": "application",
                "title": application.tenant.user.full_name,
                "subtitle": application.unit.building.property_ref.name,
                "date": application.created_at,
                "url_name": "rentals:landlord-rental-application-detail",
                "url_pk": application.pk,
            }
            for application in recent_applications
        )
        recent_activities.sort(key=lambda item: item["date"], reverse=True)

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
            "occupied_unit_count": occupied_units,
            "pending_applications": RentalApplication.objects.filter(
                unit__building__property_ref__landlord=landlord,
                status="PENDING",
            ).count(),
            "dashboard_charts": {
                "revenue": {"labels": revenue_labels, "data": revenue_data},
                "occupancy": {
                    "labels": [
                        str(_("Occupied")),
                        str(_("Available / reserved")),
                        str(_("Maintenance")),
                        str(_("Inactive")),
                    ],
                    "data": [
                        occupied_units,
                        available_units,
                        maintenance_units,
                        inactive_units,
                    ],
                    "backgroundColor": ["#2E9E5B", "#4A90D9", "#B9770E", "#DCE5F1"],
                },
                "maintenance": {
                    "labels": maintenance_labels,
                    "new": maintenance_new,
                    "inProgress": maintenance_in_progress,
                    "completed": maintenance_completed,
                },
            },
            "recent_activities": recent_activities[: cls.RECENT_LIMIT * 2],
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

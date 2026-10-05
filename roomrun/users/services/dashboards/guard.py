from __future__ import annotations

from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from operations.models import VisitorVisit
from utils.enums import VisitorStatus


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
        visits = VisitorVisit.objects.filter(
            building__property_ref__landlord__in=guard.landlords.all()
        ).select_related("host", "building")
        active_visitors = visits.filter(status=VisitorStatus.CHECKED_IN).count()
        expected_visitors = visits.filter(
            expected_arrival__date=today, status=VisitorStatus.EXPECTED
        ).count()
        today_visits = visits.filter(checked_in_at__date=today)
        today_logs = today_visits.count()
        recent_visitors = today_visits.order_by("-checked_in_at")[
            : GuardDashboardService.RECENT_LIMIT
        ]
        expected_visits = visits.filter(
            status=VisitorStatus.EXPECTED, expected_arrival__date=today
        ).order_by("expected_arrival")[: GuardDashboardService.RECENT_LIMIT]
        completed_visitors = visits.filter(
            status=VisitorStatus.CHECKED_OUT, checked_out_at__date=today
        ).count()

        shift_info = {
            "shift": guard.shift,
            "start_time": guard.shift_start_time
            if hasattr(guard, "shift_start_time")
            else None,
            "end_time": guard.shift_end_time
            if hasattr(guard, "shift_end_time")
            else None,
        }

        return {
            "guard": guard,
            "total_logs": visits.count(),
            "today_logs": today_logs,
            "active_visitors": active_visitors,
            "expected_visitors": expected_visitors,
            "recent_logs": recent_visitors,
            "completed_visitors": completed_visitors,
            "shift_info": shift_info,
            "recent_visitors": recent_visitors,
            "expected_visits": expected_visits,
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

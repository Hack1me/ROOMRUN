from __future__ import annotations

from django.utils.translation import gettext_lazy as _
from maintenance.models import MaintenanceRequest


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
        pending_tasks = tasks.filter(status__in=["PENDING", "ASSIGNED"]).count()
        in_progress_tasks = tasks.filter(status="IN_PROGRESS").count()
        completed_tasks = tasks.filter(status="COMPLETED").count()

        urgent_requests = (
            MaintenanceRequest.objects.filter(
                tasks__maintenance_agent=agent,
                priority="URGENT",
                status="IN_PROGRESS",
            )
            .distinct()
            .count()
        )

        recent_tasks = tasks.order_by("-created_at")[
            : MaintenanceDashboardService.RECENT_LIMIT
        ]
        recent_requests = (
            MaintenanceRequest.objects.filter(
                tasks__maintenance_agent=agent,
            )
            .distinct()
            .order_by("-created_at")[: MaintenanceDashboardService.RECENT_LIMIT]
        )

        completion_rate = (
            round((completed_tasks / total_tasks) * 100, 1) if total_tasks > 0 else 0
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
        return agent.tasks.filter(status__in=["PENDING", "ASSIGNED"]).order_by(
            "-created_at"
        )

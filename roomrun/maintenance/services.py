from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from maintenance.models import MaintenanceRequest
from maintenance.models import MaintenanceRequestAttachment
from maintenance.models import Task
from rentals.models import RentalContract
from utils.enums import ContractStatus
from utils.enums import RequestStatus
from utils.enums import TaskStatus


class MaintenanceWorkflowService:
    """Centralises the workflow so web views cannot bypass ownership rules."""

    @staticmethod
    @transaction.atomic
    def create_request(*, tenant, data, photos, user):
        contract = (
            RentalContract.objects.select_related("unit")
            .filter(tenant=tenant, status=ContractStatus.ACTIVE)
            .order_by("-created_at")
            .first()
        )
        if not contract:
            raise ValidationError(
                _("You need an active lease to report a maintenance issue.")
            )

        request = MaintenanceRequest(
            tenant=tenant,
            unit=contract.unit,
            title=data["title"],
            description=data["description"],
            priority=data["priority"],
            created_by=user,
            updated_by=user,
        )
        request.save()
        for photo in photos:
            MaintenanceRequestAttachment.objects.create(
                maintenance_request=request,
                file=photo,
                created_by=user,
                updated_by=user,
            )
        return request

    @staticmethod
    @transaction.atomic
    def create_landlord_request(*, landlord, data, photos, user):
        unit = data["unit"]
        contract = (
            RentalContract.objects.select_for_update()
            .filter(tenant__isnull=False, unit=unit, status=ContractStatus.ACTIVE)
            .select_related("tenant")
            .first()
        )
        if not contract:
            raise ValidationError(_("Select a unit with an active lease."))
        agent = data["maintenance_agent"]
        if not agent.landlords.filter(pk=landlord.pk).exists():
            raise ValidationError(
                _("Select a maintenance agent linked to your account.")
            )
        request = MaintenanceRequest(
            tenant=contract.tenant,
            unit=unit,
            title=data["title"],
            description=data["description"],
            priority=data["priority"],
            status=RequestStatus.IN_PROGRESS,
            created_by=user,
            updated_by=user,
        )
        request.save()
        for photo in photos:
            MaintenanceRequestAttachment.objects.create(
                maintenance_request=request,
                file=photo,
                created_by=user,
                updated_by=user,
            )
        Task.objects.create(
            maintenance_request=request,
            maintenance_agent=agent,
            title=request.title,
            description=request.description,
            status=TaskStatus.ASSIGNED,
            created_by=user,
            updated_by=user,
        )
        return request

    @staticmethod
    @transaction.atomic
    def claim_request(*, request_id, agent, user):
        request = MaintenanceRequest.objects.select_for_update().get(pk=request_id)
        if request.status != RequestStatus.PENDING:
            raise ValidationError(_("This request is no longer available."))
        if request.tasks.exclude(status=TaskStatus.CANCELLED).exists():
            raise ValidationError(_("This request has already been assigned."))

        task = Task(
            maintenance_request=request,
            maintenance_agent=agent,
            title=request.title,
            description=request.description,
            status=TaskStatus.ASSIGNED,
            created_by=user,
            updated_by=user,
        )
        task.save()
        request.status = RequestStatus.IN_PROGRESS
        request.updated_by = user
        request.save(update_fields=["status", "updated_by", "updated_at"])
        return task

    @staticmethod
    @transaction.atomic
    def progress_task(*, task_id, agent, action, work_notes, user):
        task = (
            Task.objects.select_for_update()
            .select_related("maintenance_request")
            .get(pk=task_id, maintenance_agent=agent)
        )
        now = timezone.now()
        if action == "start":
            if task.status not in {TaskStatus.ASSIGNED, TaskStatus.PENDING}:
                raise ValidationError(_("Only an assigned task can be started."))
            task.status = TaskStatus.IN_PROGRESS
            task.started_at = now
        elif action == "complete":
            if task.status != TaskStatus.IN_PROGRESS:
                raise ValidationError(_("Start the task before marking it completed."))
            task.status = TaskStatus.COMPLETED
            task.completed_at = now
        else:
            raise ValidationError(_("Unsupported task action."))

        if work_notes:
            task.work_notes = work_notes
        task.updated_by = user
        task.save()

        if action == "complete":
            request = task.maintenance_request
            incomplete_tasks = request.tasks.exclude(
                status__in=[TaskStatus.COMPLETED, TaskStatus.CANCELLED]
            ).exists()
            if not incomplete_tasks:
                request.status = RequestStatus.RESOLVED
                request.resolved_at = now
                request.updated_by = user
                request.save(
                    update_fields=["status", "resolved_at", "updated_by", "updated_at"]
                )
        return task

    @staticmethod
    @transaction.atomic
    def cancel_request(*, request_id, tenant, user):
        request = MaintenanceRequest.objects.select_for_update().get(
            pk=request_id, tenant=tenant
        )
        if request.status != RequestStatus.PENDING:
            raise ValidationError(_("Only a pending request can be cancelled."))
        if request.tasks.exists():
            raise ValidationError(_("An assigned request cannot be cancelled."))
        request.status = RequestStatus.CANCELLED
        request.updated_by = user
        request.save(update_fields=["status", "updated_by", "updated_at"])
        return request

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.http import FileResponse
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import CreateView
from django.views.generic import DetailView
from django.views.generic import FormView
from django.views.generic import ListView
from maintenance.forms import LandlordMaintenanceRequestForm
from maintenance.forms import MaintenanceRequestForm
from maintenance.forms import TaskProgressForm
from maintenance.models import MaintenanceRequest
from maintenance.models import MaintenanceRequestAttachment
from maintenance.models import Task
from maintenance.services import MaintenanceWorkflowService
from properties.mixins import LandlordRequiredMixin
from rentals.mixins import TenantRequiredMixin
from utils.enums import RequestStatus


class MaintenanceAgentRequiredMixin(LoginRequiredMixin):
    """Expose maintenance data only to the authenticated assigned agent."""

    def get_agent(self):
        try:
            return self.request.user.employee_profile.maintenance_agent_profile
        except AttributeError as exc:
            raise PermissionDenied from exc


class TenantRequestListView(TenantRequiredMixin, ListView):
    template_name = "dashboard/maintenance/tenant/request_list.html"
    context_object_name = "maintenance_requests"
    paginate_by = 15

    def get_queryset(self):
        return (
            MaintenanceRequest.objects.filter(tenant=self.get_tenant())
            .select_related("unit__building__property_ref")
            .prefetch_related("tasks")
        )


class TenantRequestCreateView(TenantRequiredMixin, CreateView):
    form_class = MaintenanceRequestForm
    template_name = "dashboard/maintenance/tenant/request_form.html"

    def form_valid(self, form):
        try:
            maintenance_request = MaintenanceWorkflowService.create_request(
                tenant=self.get_tenant(),
                data=form.cleaned_data,
                photos=form.cleaned_data.get("photos", []),
                user=self.request.user,
            )
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
        messages.success(
            self.request,
            _("Your maintenance request %(number)s has been submitted.")
            % {"number": maintenance_request.request_number},
        )
        return redirect(maintenance_request.get_absolute_url())


class TenantRequestDetailView(TenantRequiredMixin, DetailView):
    template_name = "dashboard/maintenance/tenant/request_detail.html"
    context_object_name = "maintenance_request"

    def get_queryset(self):
        return (
            MaintenanceRequest.objects.filter(tenant=self.get_tenant())
            .select_related("unit__building__property_ref")
            .prefetch_related("attachments", "tasks")
        )


class TenantRequestCancelView(TenantRequiredMixin, View):
    def post(self, request, pk):
        try:
            MaintenanceWorkflowService.cancel_request(
                request_id=pk, tenant=self.get_tenant(), user=request.user
            )
            messages.success(request, _("Maintenance request cancelled."))
        except MaintenanceRequest.DoesNotExist:
            raise Http404 from None
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        return redirect("maintenance:request-detail", pk=pk)


class LandlordRequestCreateView(LandlordRequiredMixin, CreateView):
    form_class = LandlordMaintenanceRequestForm
    template_name = "dashboard/maintenance/landlord/request_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["landlord"] = self.get_landlord()
        return kwargs

    def form_valid(self, form):
        try:
            maintenance_request = MaintenanceWorkflowService.create_landlord_request(
                landlord=self.get_landlord(),
                data=form.cleaned_data,
                photos=form.cleaned_data.get("photos", []),
                user=self.request.user,
            )
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
        messages.success(self.request, _("Maintenance request created and assigned."))
        return redirect(
            "maintenance:landlord-request-detail", pk=maintenance_request.pk
        )


class LandlordRequestListView(LandlordRequiredMixin, ListView):
    """List only requests that concern the current landlord's properties."""

    template_name = "dashboard/maintenance/landlord/request_list.html"
    context_object_name = "maintenance_requests"
    paginate_by = 20

    def get_queryset(self):
        return (
            MaintenanceRequest.objects.filter(
                unit__building__property_ref__landlord=self.get_landlord()
            )
            .select_related("tenant__user", "unit__building__property_ref")
            .prefetch_related("tasks__maintenance_agent__employee__user")
        )


class LandlordRequestDetailView(LandlordRequiredMixin, DetailView):
    template_name = "dashboard/maintenance/landlord/request_detail.html"
    context_object_name = "maintenance_request"

    def get_queryset(self):
        return (
            MaintenanceRequest.objects.filter(
                unit__building__property_ref__landlord=self.get_landlord()
            )
            .select_related("tenant__user", "unit__building__property_ref")
            .prefetch_related("attachments", "tasks__maintenance_agent__employee__user")
        )


class AgentQueueView(MaintenanceAgentRequiredMixin, ListView):
    template_name = "dashboard/maintenance/agent/queue.html"
    context_object_name = "maintenance_requests"
    paginate_by = 20

    def get_queryset(self):
        self.get_agent()
        return (
            MaintenanceRequest.objects.filter(status=RequestStatus.PENDING)
            .select_related("unit__building__property_ref")
            .prefetch_related("attachments")
        )


class AgentClaimRequestView(MaintenanceAgentRequiredMixin, View):
    def post(self, request, pk):
        try:
            task = MaintenanceWorkflowService.claim_request(
                request_id=pk, agent=self.get_agent(), user=request.user
            )
        except MaintenanceRequest.DoesNotExist:
            raise Http404 from None
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
            return redirect("maintenance:agent-queue")
        messages.success(request, _("The request is now assigned to you."))
        return redirect("maintenance:task-detail", pk=task.pk)


class AgentTaskListView(MaintenanceAgentRequiredMixin, ListView):
    template_name = "dashboard/maintenance/agent/task_list.html"
    context_object_name = "tasks"
    paginate_by = 20

    def get_queryset(self):
        return Task.objects.filter(maintenance_agent=self.get_agent()).select_related(
            "maintenance_request__unit__building__property_ref",
            "maintenance_request__tenant__user",
        )


class AgentTaskDetailView(MaintenanceAgentRequiredMixin, FormView):
    template_name = "dashboard/maintenance/agent/task_detail.html"
    form_class = TaskProgressForm

    def dispatch(self, request, *args, **kwargs):
        self.task = get_object_or_404(
            Task.objects.select_related(
                "maintenance_request__unit__building__property_ref",
                "maintenance_request__tenant__user",
            ).prefetch_related("maintenance_request__attachments"),
            pk=kwargs["pk"],
            maintenance_agent=self.get_agent(),
        )
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["task"] = self.task
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["task"] = self.task
        return context

    def form_valid(self, form):
        try:
            MaintenanceWorkflowService.progress_task(
                task_id=self.task.pk,
                agent=self.get_agent(),
                action=form.cleaned_data["action"],
                work_notes=form.cleaned_data["work_notes"],
                user=self.request.user,
            )
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
        messages.success(self.request, _("Task updated successfully."))
        return redirect("maintenance:task-detail", pk=self.task.pk)


class AttachmentDownloadView(LoginRequiredMixin, View):
    """Serve evidence only after checking tenant/assigned-agent membership."""

    def get(self, request, pk):
        attachment = get_object_or_404(
            MaintenanceRequestAttachment.objects.select_related(
                "maintenance_request__tenant__user"
            ),
            pk=pk,
        )
        maintenance_request = attachment.maintenance_request
        is_tenant = maintenance_request.tenant.user_id == request.user.id
        is_assigned_agent = maintenance_request.tasks.filter(
            maintenance_agent__employee__user=request.user
        ).exists()
        is_landlord = MaintenanceRequest.objects.filter(
            pk=maintenance_request.pk,
            unit__building__property_ref__landlord__user=request.user,
        ).exists()
        if not (is_tenant or is_assigned_agent or is_landlord):
            raise PermissionDenied
        return FileResponse(
            attachment.file.open("rb"),
            as_attachment=True,
            filename=attachment.file.name.rsplit("/", 1)[-1],
        )

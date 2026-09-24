from django import forms
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.core.exceptions import PermissionDenied
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import CreateView
from django.urls import reverse
from django.views.generic import DetailView
from django.views.generic import ListView
from django.views.generic import UpdateView
from operations.models import CleaningSchedule
from properties.mixins import LandlordRequiredMixin
from properties.models import Building
from rentals.mixins import TenantRequiredMixin
from rentals.models import RentalContract
from operations.models import VisitorVisit
from utils.enums import CleaningStatus
from utils.enums import ContractStatus

from utils.enums import VisitorStatus


class CleaningScheduleForm(forms.ModelForm):
    class Meta:
        model = CleaningSchedule
        fields = ("building", "scheduled_date", "start_time", "end_time", "description")
        widgets = {
            "building": forms.Select(attrs={"class": "form-select"}),
            "scheduled_date": forms.DateInput(
                attrs={"class": "form-input", "type": "date"}
            ),
            "start_time": forms.TimeInput(
                attrs={"class": "form-input", "type": "time"}
            ),
            "end_time": forms.TimeInput(attrs={"class": "form-input", "type": "time"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 5}),
        }

    def __init__(self, *args, landlord, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["building"].queryset = Building.objects.filter(
            property_ref__landlord=landlord
        ).select_related("property_ref")


class LandlordCleaningScheduleListView(LandlordRequiredMixin, ListView):
    template_name = "dashboard/operations/landlord/cleaning_list.html"
    context_object_name = "schedules"
    paginate_by = 20

    def get_queryset(self):
        return CleaningSchedule.objects.filter(
            building__property_ref__landlord=self.get_landlord()
        ).select_related("building__property_ref")


class LandlordCleaningScheduleCreateView(LandlordRequiredMixin, CreateView):
    form_class = CleaningScheduleForm
    template_name = "dashboard/operations/landlord/cleaning_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["landlord"] = self.get_landlord()
        return kwargs

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        messages.success(self.request, _("Cleaning schedule created."))
        return super().form_valid(form)

    def get_success_url(self):
        return self.object.get_absolute_url()


class LandlordCleaningScheduleDetailView(LandlordRequiredMixin, DetailView):
    template_name = "dashboard/operations/landlord/cleaning_detail.html"
    context_object_name = "schedule"

    def get_queryset(self):
        return CleaningSchedule.objects.filter(
            building__property_ref__landlord=self.get_landlord()
        ).select_related("building__property_ref")


class LandlordCleaningScheduleUpdateView(LandlordRequiredMixin, UpdateView):
    form_class = CleaningScheduleForm
    template_name = "dashboard/operations/landlord/cleaning_form.html"

    def get_queryset(self):
        return CleaningSchedule.objects.filter(
            building__property_ref__landlord=self.get_landlord(),
            status=CleaningStatus.SCHEDULED,
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["landlord"] = self.get_landlord()
        return kwargs

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, _("Cleaning schedule updated."))
        return super().form_valid(form)

    def get_success_url(self):
        return self.object.get_absolute_url()


class LandlordCleaningStatusView(LandlordRequiredMixin, View):
    @transaction.atomic
    def post(self, request, pk):
        schedule = get_object_or_404(
            CleaningSchedule.objects.select_for_update(),
            pk=pk,
            building__property_ref__landlord=self.get_landlord(),
        )
        action = request.POST.get("action")
        if action == "start" and schedule.status == CleaningStatus.SCHEDULED:
            if schedule.scheduled_date > timezone.localdate():
                messages.error(
                    request, _("This cleaning is scheduled for a future date.")
                )
                return redirect("operations:cleaning-detail", pk=schedule.pk)
            schedule.status = CleaningStatus.IN_PROGRESS
        elif action == "complete" and schedule.status == CleaningStatus.IN_PROGRESS:
            schedule.status = CleaningStatus.COMPLETED
        elif action == "cancel" and schedule.status in {
            CleaningStatus.SCHEDULED,
            CleaningStatus.IN_PROGRESS,
        }:
            schedule.status = CleaningStatus.CANCELLED
        else:
            messages.error(request, _("This cleaning action is not allowed."))
            return redirect("operations:cleaning-detail", pk=schedule.pk)

        schedule.updated_by = request.user
        schedule.save(update_fields=["status", "updated_by", "updated_at"])
        messages.success(request, _("Cleaning schedule updated."))
        return redirect("operations:cleaning-detail", pk=schedule.pk)


class TenantCleaningScheduleListView(TenantRequiredMixin, ListView):
    template_name = "dashboard/operations/tenant/cleaning_list.html"

    context_object_name = "schedules"
    paginate_by = 20

    def get_queryset(self):
        contract = (
            RentalContract.objects.filter(
                tenant=self.get_tenant(), status=ContractStatus.ACTIVE
            )
            .select_related("unit__building")
            .first()
        )
        if not contract:
            return CleaningSchedule.objects.none()
        return (
            CleaningSchedule.objects.filter(building=contract.unit.building)
            .exclude(status=CleaningStatus.CANCELLED)
            .select_related("building__property_ref")
        )


class VisitorHostMixin(LoginRequiredMixin):
    """Limit invitations to buildings the authenticated host may use."""

    def get_host_buildings(self):
        if hasattr(self.request.user, "landlord_profile"):
            return Building.objects.filter(
                property_ref__landlord=self.request.user.landlord_profile
            )
        if hasattr(self.request.user, "tenant_profile"):
            return Building.objects.filter(
                units__rental_contracts__tenant=self.request.user.tenant_profile,
                units__rental_contracts__status=ContractStatus.ACTIVE,
            ).distinct()
        raise PermissionDenied

    def get_visit_queryset(self):
        return VisitorVisit.objects.filter(host=self.request.user).select_related(
            "building", "building__property_ref"
        )


class VisitorInvitationForm(forms.ModelForm):
    class Meta:
        model = VisitorVisit
        fields = (
            "building",
            "visitor_name",
            "visitor_phone",
            "purpose",
            "expected_arrival",
            "expected_departure",
        )
        widgets = {
            "expected_arrival": forms.DateTimeInput(
                attrs={"type": "datetime-local", "class": "rr-input"}
            ),
            "expected_departure": forms.DateTimeInput(
                attrs={"type": "datetime-local", "class": "rr-input"}
            ),
        }

    def __init__(self, *args, buildings, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["building"].queryset = buildings
        for name, field in self.fields.items():
            field.widget.attrs.setdefault("class", "rr-input")
        self.fields["purpose"].widget.attrs["placeholder"] = _("Reason for the visit")


class VisitorInvitationView(VisitorHostMixin, CreateView):
    form_class = VisitorInvitationForm
    template_name = "dashboard/operations/visitors/invitation_list.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["buildings"] = self.get_host_buildings()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["visits"] = self.get_visit_queryset()[:30]
        return context

    def form_valid(self, form):
        if form.cleaned_data["expected_arrival"] < timezone.now():
            form.add_error("expected_arrival", _("Arrival must be in the future."))
            return self.form_invalid(form)
        form.instance.host = self.request.user
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        messages.success(self.request, _("Visitor invitation created."))
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("operations:visitor-invitations")


class VisitorInvitationCancelView(VisitorHostMixin, View):
    @transaction.atomic
    def post(self, request, pk):
        visit = get_object_or_404(
            self.get_visit_queryset().select_for_update(),
            pk=pk,
            status=VisitorStatus.EXPECTED,
        )
        visit.status = VisitorStatus.CANCELLED
        visit.updated_by = request.user
        visit.save(update_fields=["status", "updated_by", "updated_at"])
        messages.success(request, _("Visitor invitation cancelled."))
        return redirect("operations:visitor-invitations")


class GuardVisitorMixin(LoginRequiredMixin):
    def get_guard(self):
        try:
            return self.request.user.employee_profile.guard_profile
        except AttributeError as exc:
            raise PermissionDenied from exc

    def get_guard_visits(self):
        return VisitorVisit.objects.filter(
            building__property_ref__landlord__in=self.get_guard().landlords.all()
        ).select_related(
            "building",
            "building__property_ref",
            "host",
            "checked_in_by",
            "checked_out_by",
        )


class GuardVisitorListView(GuardVisitorMixin, ListView):
    template_name = "dashboard/operations/guard/visitor_list.html"
    context_object_name = "visits"
    paginate_by = 30

    def get_queryset(self):
        return (
            self.get_guard_visits()
            .filter(status__in=[VisitorStatus.EXPECTED, VisitorStatus.CHECKED_IN])
            .order_by("expected_arrival")
        )


class GuardVisitorStatusView(GuardVisitorMixin, View):
    @transaction.atomic
    def post(self, request, pk):
        guard = self.get_guard()
        visit = get_object_or_404(self.get_guard_visits().select_for_update(), pk=pk)
        action = request.POST.get("action")
        now = timezone.now()
        if action == "check-in" and visit.status == VisitorStatus.EXPECTED:
            visit.status = VisitorStatus.CHECKED_IN
            visit.checked_in_at = now
            visit.checked_in_by = guard
        elif action == "check-out" and visit.status == VisitorStatus.CHECKED_IN:
            visit.status = VisitorStatus.CHECKED_OUT
            visit.checked_out_at = now
            visit.checked_out_by = guard
        elif action == "deny" and visit.status == VisitorStatus.EXPECTED:
            visit.status = VisitorStatus.DENIED
        else:
            messages.error(request, _("This visitor action is not allowed."))
            return redirect("operations:guard-visitors")
        visit.updated_by = request.user
        visit.save()
        messages.success(request, _("Visitor status updated."))
        return redirect("operations:guard-visitors")

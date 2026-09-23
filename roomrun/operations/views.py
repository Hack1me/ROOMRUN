from django import forms
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import CreateView
from django.views.generic import DetailView
from django.views.generic import ListView
from django.views.generic import UpdateView
from operations.models import CleaningSchedule
from properties.mixins import LandlordRequiredMixin
from properties.models import Building
from rentals.mixins import TenantRequiredMixin
from rentals.models import RentalContract
from utils.enums import CleaningStatus
from utils.enums import ContractStatus


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

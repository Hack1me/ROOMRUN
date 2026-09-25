from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import CreateView
from django.views.generic import DetailView
from django.views.generic import ListView
from django.views.generic import UpdateView
from operations.models import CleaningSchedule
from operations.models import VisitorVisit
from operations.visitor_qr import get_visit_qr_data_uri
from operations.visitor_qr import read_visit_token
from properties.mixins import LandlordRequiredMixin
from properties.models import Building
from rentals.mixins import TenantRequiredMixin
from rentals.models import RentalContract
from utils.enums import CleaningStatus
from utils.enums import ContractStatus
from utils.enums import EmployeeStatus
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
                return redirect("operations:cleaning-detail", pk=schedule.slug)
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
            return redirect("operations:cleaning-detail", pk=schedule.slug)

        schedule.updated_by = request.user
        schedule.save(update_fields=["status", "updated_by", "updated_at"])
        messages.success(request, _("Cleaning schedule updated."))
        return redirect("operations:cleaning-detail", pk=schedule.slug)


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
        for field in self.fields.values():
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
        visits = list(self.get_visit_queryset()[:30])
        for visit in visits:
            if visit.status in (VisitorStatus.EXPECTED, VisitorStatus.CHECKED_IN):
                visit.qr_data_uri = get_visit_qr_data_uri(visit)
        context["visits"] = visits
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
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["sidebar_template"] = "dashboard/includes/guard_sidebar.html"
        return context

    def get_guard(self):
        try:
            guard = self.request.user.employee_profile.guard_profile
        except AttributeError as exc:
            raise PermissionDenied from exc
        if guard.employee.status != EmployeeStatus.ACTIVE:
            raise PermissionDenied
        return guard

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
        queryset = (
            self.get_guard_visits()
            .filter(status__in=[VisitorStatus.EXPECTED, VisitorStatus.CHECKED_IN])
            .order_by("expected_arrival")
        )
        search = self.request.GET.get("q", "").strip()
        if search:
            queryset = queryset.filter(
                Q(visitor_name__icontains=search)
                | Q(visitor_phone__icontains=search)
                | Q(host__first_name__icontains=search)
                | Q(host__last_name__icontains=search)
                | Q(host__email__icontains=search)
                | Q(building__name__icontains=search)
                | Q(building__property_ref__name__icontains=search)
            )
        return queryset


class GuardCheckInForm(forms.ModelForm):
    """Register a walk-in visitor for a residence assigned to the guard."""

    class Meta:
        model = VisitorVisit
        fields = (
            "building",
            "visitor_name",
            "visitor_phone",
            "purpose",
            "check_in_note",
        )
        widgets = {
            "purpose": forms.Textarea(attrs={"rows": 3}),
            "check_in_note": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, guard, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["building"].queryset = Building.objects.filter(
            property_ref__landlord__in=guard.landlords.all()
        ).select_related("property_ref")
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "rr-input")
        self.fields["visitor_phone"].widget.attrs["autocomplete"] = "tel"
        self.fields["visitor_name"].widget.attrs["autocomplete"] = "name"


class GuardCheckInView(GuardVisitorMixin, CreateView):
    """Securely check in a walk-in visitor at the security desk."""

    form_class = GuardCheckInForm
    template_name = "dashboard/operations/guard/checkin_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["guard"] = self.get_guard()
        return kwargs

    @transaction.atomic
    def form_valid(self, form):
        guard = self.get_guard()
        now = timezone.now()
        form.instance.expected_arrival = now
        form.instance.status = VisitorStatus.CHECKED_IN
        form.instance.checked_in_at = now
        form.instance.checked_in_by = guard
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        messages.success(self.request, _("Visitor checked in successfully."))
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("operations:guard-visitors")


class GuardVisitorHistoryView(GuardVisitorMixin, ListView):
    template_name = "dashboard/operations/guard/visitor_history.html"
    context_object_name = "visits"
    paginate_by = 30

    def get_queryset(self):
        return (
            self.get_guard_visits()
            .filter(
                status__in=[
                    VisitorStatus.CHECKED_OUT,
                    VisitorStatus.DENIED,
                    VisitorStatus.CANCELLED,
                ]
            )
            .order_by("-updated_at")
        )


class GuardVisitorStatusView(GuardVisitorMixin, View):
    @transaction.atomic
    def post(self, request, pk):
        guard = self.get_guard()
        # Lock only the visitor row: related guard fields are nullable joins,
        # and PostgreSQL cannot apply FOR UPDATE to the nullable side of those
        # joins when select_related() is present.
        visit = get_object_or_404(
            self.get_guard_visits().select_for_update(of=("self",)),
            pk=pk,
        )
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


class GuardVisitorQRScanView(GuardVisitorMixin, View):
    """Scan a guest's signed QR and transition expected/in-progress visits."""

    template_name = "dashboard/operations/guard/visitor_qr_scan.html"

    def get(self, request, *args, **kwargs):
        self.get_guard()
        return render(request, self.template_name)

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        guard = self.get_guard()
        token = request.POST.get("token", "")
        try:
            visit_pk = read_visit_token(token)
        except (signing.BadSignature, KeyError, TypeError, ValueError):
            messages.error(request, _("This visitor QR code is invalid or expired."))
            return redirect("operations:guard-visitor-qr-scan")

        visit = get_object_or_404(
            self.get_guard_visits().select_for_update(of=("self",)), pk=visit_pk,
        )
        now = timezone.now()
        if visit.status == VisitorStatus.EXPECTED:
            if visit.expected_arrival > now + timezone.timedelta(minutes=30):
                messages.error(request, _("This visitor has not arrived yet."))
                return redirect("operations:guard-visitor-qr-scan")
            visit.status = VisitorStatus.CHECKED_IN
            visit.checked_in_at = now
            visit.checked_in_by = guard
            action = _("checked in")
        elif visit.status == VisitorStatus.CHECKED_IN:
            visit.status = VisitorStatus.CHECKED_OUT
            visit.checked_out_at = now
            visit.checked_out_by = guard
            action = _("checked out")
        else:
            messages.error(
                request,
                _("This invitation has already been used or cancelled."),
            )
            return redirect("operations:guard-visitor-qr-scan")

        visit.updated_by = request.user
        visit.save()
        messages.success(
            request,
            _("%(visitor)s was %(action)s successfully.")
            % {"visitor": visit.visitor_name, "action": action},
        )
        return redirect("operations:guard-visitors")

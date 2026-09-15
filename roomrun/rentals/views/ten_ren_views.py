from django.contrib import messages
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView
from django.views.generic import DetailView
from django.views.generic import ListView
from rentals.forms import RentalApplicationForm
from rentals.mixins import TenantApplicationQuerysetMixin
from rentals.mixins import TenantRequiredMixin
from rentals.models import RentalApplication
from rentals.services import RentalApplicationService


class RentalApplicationListView(TenantApplicationQuerysetMixin, ListView):
    template_name = "dashboard/rentals/applications/list.html"
    context_object_name = "applications"
    paginate_by = 10


class RentalApplicationDetailView(TenantApplicationQuerysetMixin, DetailView):
    template_name = "dashboard/rentals/applications/detail.html"
    context_object_name = "application"


class RentalApplicationCreateView(TenantRequiredMixin, CreateView):
    model = RentalApplication
    form_class = RentalApplicationForm
    template_name = "dashboard/rentals/applications/form.html"

    def get_form_kwargs(self):
        """
        Pass the tenant to the form so it can filter units and prevent
        duplicate pending applications.
        """
        kwargs = super().get_form_kwargs()
        kwargs["tenant"] = self.get_tenant()
        return kwargs

    def form_valid(self, form):
        tenant = self.get_tenant()

        try:
            RentalApplicationService.create(
                tenant=tenant,
                data=form.cleaned_data,
            )
        except Exception as exc:  # noqa: BLE001
            form.add_error(None, str(exc))
            return self.form_invalid(form)

        messages.success(
            self.request,
            _("Your rental application has been submitted successfully."),
        )

        return redirect("rentals:rental-application-list")

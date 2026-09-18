from django.views.generic import ListView
from properties.mixins import LandlordRequiredMixin
from users.models import Employee
from users.services import EmployeeService


class EmployeeListView(LandlordRequiredMixin, ListView):
    """
    Display the employees belonging to the current landlord.
    """

    model = Employee
    template_name = "dashboard/employees/list.html"
    context_object_name = "employees"
    paginate_by = 10

    def get_queryset(self):
        return EmployeeService.get_list(
            landlord=self.get_landlord(),
            search=self.request.GET.get("q", ""),
            employee_type=self.request.GET.get("type", ""),
            status=self.request.GET.get("status", ""),
        )

    def get_context_data(self, **kwargs):
        """Preserve filters across pagination links."""
        context = super().get_context_data(**kwargs)

        context.update({
            "search": self.request.GET.get("q", "").strip(),
            "selected_type": self.request.GET.get("type", "").strip(),
            "selected_status": self.request.GET.get("status", "").strip(),
        })

        return context

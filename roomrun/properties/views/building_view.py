from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from django.views import View
from properties.forms import BuildingForm
from properties.mixins import LandlordBuildingAccessMixin
from properties.mixins import ServiceFormMixin
from properties.services import BuildingService


class BuildingListView(LandlordBuildingAccessMixin, View):
    """List all buildings within a property owned by the landlord."""

    template_name = "dashboard/buildings/list.html"
    paginate_by = 10

    def get(self, request, property_id):
        property_obj = self.get_property(property_id)

        queryset = property_obj.buildings.all().order_by("-created_at")
        page_obj = Paginator(queryset, self.paginate_by).get_page(
            request.GET.get("page")
        )

        return render(
            request,
            self.template_name,
            {
                "property": property_obj,
                "buildings": page_obj,
                "page_obj": page_obj,
            },
        )


class BuildingCreateView(LandlordBuildingAccessMixin, ServiceFormMixin, View):
    """Create a new building inside the given property."""

    template_name = "dashboard/buildings/form.html"

    def get(self, request, property_id):
        property_obj = self.get_property(property_id)
        return self.render_form(
            form=BuildingForm(),
            context={
                "property": property_obj,
                "page_title": _("Create building"),
            },
        )

    def post(self, request, property_id):
        property_obj = self.get_property(property_id)
        form = BuildingForm(request.POST)

        if not form.is_valid():
            return self.render_form(
                form=form,
                context={
                    "property": property_obj,
                    "page_title": _("Create building"),
                },
            )

        try:
            building = BuildingService.create(
                property_obj=property_obj,
                data=form.cleaned_data,
            )
        except ValidationError as e:
            self.handle_service_errors(form, e)
            return self.render_form(
                form=form,
                context={
                    "property": property_obj,
                    "page_title": _("Create building"),
                },
            )

        return self.service_success(
            _("Building created successfully."),
            "properties:building-detail",
            pk=building.pk,
        )


class BuildingDetailView(LandlordBuildingAccessMixin, View):
    """Display a single building owned by the landlord."""

    template_name = "dashboard/buildings/detail.html"
    paginate_by = 6

    def get(self, request, pk):
        building = self.get_building(pk)
        units = building.units.all().order_by("unit_number")
        page_obj = Paginator(units, self.paginate_by).get_page(request.GET.get("page"))
        unit_count = units.count()
        occupied_count = units.filter(status="OCCUPIED").count()
        available_count = units.filter(status="AVAILABLE").count()
        occupancy_rate = round((occupied_count / unit_count) * 100) if unit_count else 0

        return render(
            request,
            self.template_name,
            {
                "building": building,
                "property": building.property_ref,
                "units": page_obj,
                "page_obj": page_obj,
                "unit_count": unit_count,
                "occupied_count": occupied_count,
                "available_count": available_count,
                "occupancy_rate": occupancy_rate,
            },
        )


class BuildingUpdateView(LandlordBuildingAccessMixin, ServiceFormMixin, View):
    """Update an existing building."""

    template_name = "dashboard/buildings/form.html"

    def get(self, request, pk):
        building = self.get_building(pk)
        return self.render_form(
            form=BuildingForm(instance=building),
            context={
                "building": building,
                "property": building.property_ref,
                "page_title": _("Edit building"),
            },
        )

    def post(self, request, pk):
        building = self.get_building(pk)
        form = BuildingForm(request.POST, instance=building)

        if not form.is_valid():
            return self.render_form(
                form=form,
                context={
                    "building": building,
                    "property": building.property_ref,
                    "page_title": _("Edit building"),
                },
            )

        try:
            BuildingService.update(building=building, data=form.cleaned_data)
        except ValidationError as e:
            self.handle_service_errors(form, e)
            return self.render_form(
                form=form,
                context={
                    "building": building,
                    "property": building.property_ref,
                    "page_title": _("Edit building"),
                },
            )

        return self.service_success(
            _("Building updated successfully."),
            "properties:building-detail",
            pk=building.pk,
        )


class BuildingDeleteView(LandlordBuildingAccessMixin, View):
    """Delete a building owned by the landlord."""

    template_name = "dashboard/buildings/confirm_delete.html"

    def get(self, request, pk):
        building = self.get_building(pk)
        return render(request, self.template_name, {"building": building})

    def post(self, request, pk):
        building = self.get_building(pk)
        property_obj = building.property_ref

        BuildingService.delete(building=building)

        messages.success(request, _("Building deleted successfully."))
        return redirect("properties:property-detail", pk=property_obj.pk)

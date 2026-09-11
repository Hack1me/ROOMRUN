from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from django.views import View
from properties.forms import BuildingForm
from properties.mixins import LandlordBuildingAccessMixin
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


class BuildingCreateView(LandlordBuildingAccessMixin, View):
    """Create a new building inside the given property."""

    template_name = "dashboard/buildings/form.html"

    def get(self, request, property_id):
        property_obj = self.get_property(property_id)
        return render(
            request,
            self.template_name,
            {
                "property": property_obj,
                "form": BuildingForm(),
                "page_title": _("Create building"),
            },
        )

    def post(self, request, property_id):
        property_obj = self.get_property(property_id)
        form = BuildingForm(request.POST)

        if not form.is_valid():
            return render(
                request,
                self.template_name,
                {
                    "property": property_obj,
                    "form": form,
                    "page_title": _("Create building"),
                },
            )

        try:
            BuildingService.create(
                property=property_obj,
                data=form.cleaned_data,
            )
        except ValidationError as e:
            for field, errors in e.message_dict.items():
                for error in errors:
                    form.add_error(field, error)
            return render(
                request,
                self.template_name,
                {
                    "property": property_obj,
                    "form": form,
                    "page_title": _("Create building"),
                },
            )

        messages.success(request, _("Building created successfully."))
        return redirect("properties:building-list", property_id=property_obj.pk)


class BuildingDetailView(LandlordBuildingAccessMixin, View):
    """Display a single building owned by the landlord."""

    template_name = "dashboard/buildings/detail.html"

    def get(self, request, pk):
        building = self.get_building(pk)
        return render(request, self.template_name, {"building": building})


class BuildingUpdateView(LandlordBuildingAccessMixin, View):
    """Update an existing building."""

    template_name = "dashboard/buildings/form.html"

    def get(self, request, pk):
        building = self.get_building(pk)
        form = BuildingForm(instance=building)
        return render(
            request,
            self.template_name,
            {
                "building": building,
                "property": building.property_ref,
                "form": form,
                "page_title": _("Edit building"),
            },
        )

    def post(self, request, pk):
        building = self.get_building(pk)
        form = BuildingForm(request.POST, instance=building)

        if not form.is_valid():
            return render(
                request,
                self.template_name,
                {
                    "building": building,
                    "property": building.property_ref,
                    "form": form,
                    "page_title": _("Edit building"),
                },
            )

        try:
            BuildingService.update(building=building, data=form.cleaned_data)
        except ValidationError as e:
            for field, errors in e.message_dict.items():
                for error in errors:
                    form.add_error(field, error)
            return render(
                request,
                self.template_name,
                {
                    "building": building,
                    "property": building.property_ref,
                    "form": form,
                    "page_title": _("Edit building"),
                },
            )

        messages.success(request, _("Building updated successfully."))
        return redirect("properties:building-detail", pk=building.pk)


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
        return redirect("properties:building-list", property_id=property_obj.pk)

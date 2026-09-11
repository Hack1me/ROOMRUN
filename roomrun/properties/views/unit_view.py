from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from django.views import View
from properties.forms import UnitForm
from properties.mixins import LandlordUnitAccessMixin
from properties.mixins import ServiceFormMixin
from properties.services import UnitService


class UnitListView(LandlordUnitAccessMixin, View):
    """List all units in a given building."""

    template_name = "dashboard/properties/units/list.html"
    paginate_by = 20

    def get(self, request, property_id, building_id):
        building = self.get_building(property_id, building_id)

        queryset = building.units.all().order_by("unit_number")
        page_obj = Paginator(queryset, self.paginate_by).get_page(
            request.GET.get("page")
        )

        return render(
            request,
            self.template_name,
            {
                "building": building,
                "units": page_obj,
                "page_obj": page_obj,
            },
        )


class UnitCreateView(LandlordUnitAccessMixin, ServiceFormMixin, View):
    """Create a new unit inside a building."""

    template_name = "dashboard/properties/units/form.html"

    def get(self, request, property_id, building_id):
        building = self.get_building(property_id, building_id)
        return self.render_form(
            form=UnitForm(),
            context={"building": building},
        )

    def post(self, request, property_id, building_id):
        building = self.get_building(property_id, building_id)
        form = UnitForm(request.POST)

        if not form.is_valid():
            return self.render_form(
                form=form,
                context={"building": building},
            )

        try:
            UnitService.create(building=building, data=form.cleaned_data)
        except ValidationError as e:
            self.handle_service_errors(form, e)
            return self.render_form(
                form=form,
                context={"building": building},
            )

        return self.service_success(
            _("Unit created successfully."),
            "properties:unit-list",
            property_id=property_id,
            building_id=building_id,
        )


class UnitDetailView(LandlordUnitAccessMixin, View):
    """Display a single unit."""

    template_name = "dashboard/properties/units/detail.html"

    def get(self, request, pk):
        unit = self.get_unit(pk)
        return render(request, self.template_name, {"unit": unit})


class UnitUpdateView(LandlordUnitAccessMixin, ServiceFormMixin, View):
    """Update an existing unit."""

    template_name = "dashboard/properties/units/form.html"

    def get(self, request, pk):
        unit = self.get_unit(pk)
        return self.render_form(
            form=UnitForm(instance=unit),
            context={"unit": unit, "building": unit.building},
        )

    def post(self, request, pk):
        unit = self.get_unit(pk)
        form = UnitForm(request.POST, instance=unit)

        if not form.is_valid():
            return self.render_form(
                form=form,
                context={"unit": unit, "building": unit.building},
            )

        try:
            UnitService.update(unit=unit, data=form.cleaned_data)
        except ValidationError as e:
            self.handle_service_errors(form, e)
            return self.render_form(
                form=form,
                context={"unit": unit, "building": unit.building},
            )

        return self.service_success(
            _("Unit updated successfully."),
            "properties:unit-detail",
            pk=unit.id,
        )


class UnitDeleteView(LandlordUnitAccessMixin, View):
    """Delete an existing unit."""

    template_name = "dashboard/properties/units/confirm_delete.html"

    def get(self, request, pk):
        unit = self.get_unit(pk)
        return render(request, self.template_name, {"unit": unit})

    def post(self, request, pk):
        unit = self.get_unit(pk)

        building = unit.building
        property_id = building.property_ref_id
        building_id = building.id

        UnitService.delete(unit=unit)

        messages.success(request, _("Unit deleted successfully."))
        return redirect(
            "properties:unit-list",
            property_id=property_id,
            building_id=building_id,
        )

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from django.views import View
from properties.forms import UnitForm
from properties.forms import PropertyImageForm
from properties.mixins import LandlordUnitAccessMixin
from properties.mixins import ServiceFormMixin
from properties.services import UnitService
from properties.services import PropertyImageService


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
            context={"building": building, "property": building.property_ref},
        )

    def post(self, request, property_id, building_id):
        building = self.get_building(property_id, building_id)
        form = UnitForm(request.POST)

        if not form.is_valid():
            return self.render_form(
                form=form,
                context={"building": building, "property": building.property_ref},
            )

        try:
            UnitService.create(building=building, data=form.cleaned_data)
        except ValidationError as e:
            self.handle_service_errors(form, e)
            return self.render_form(
                form=form,
                context={"building": building, "property": building.property_ref},
            )

        return self.service_success(
            _("Unit created successfully."),
            "properties:building-detail",
            pk=building.pk,
        )


class UnitImagesView(LandlordUnitAccessMixin, ServiceFormMixin, View):
    """Manage the images attached to one rental unit."""

    template_name = "dashboard/properties/units/images.html"
    max_images = 8

    def get(self, request, pk):
        unit = self.get_unit(pk)
        return render(
            request,
            self.template_name,
            {
                "unit": unit,
                "building": unit.building,
                "property": unit.building.property_ref,
                "images": unit.images.all(),
            },
        )

    def post(self, request, pk):
        unit = self.get_unit(pk)
        files = request.FILES.getlist("images")
        existing_count = unit.images.count()

        if not files:
            messages.info(request, _("Choose at least one image to upload."))
            return redirect("properties:unit-images", pk=unit.pk)

        if existing_count + len(files) > self.max_images:
            messages.error(
                request,
                _("A unit can have a maximum of %(count)s images.")
                % {"count": self.max_images},
            )
            return redirect("properties:unit-images", pk=unit.pk)

        forms = []
        for uploaded_file in files:
            form = PropertyImageForm(
                {"caption": _("Unit image"), "is_primary": False},
                {"image": uploaded_file},
            )
            if not form.is_valid():
                self.add_form_errors_as_messages(form)
                return redirect("properties:unit-images", pk=unit.pk)
            forms.append(form)

        try:
            with transaction.atomic():
                for form in forms:
                    PropertyImageService.create(unit=unit, data=form.cleaned_data)
        except ValidationError as exc:
            self.handle_service_errors(forms[0], exc)
            self.add_form_errors_as_messages(forms[0])
            return redirect("properties:unit-images", pk=unit.pk)

        messages.success(request, _("Unit images uploaded successfully."))
        return redirect("properties:unit-images", pk=unit.pk)


class UnitDetailView(LandlordUnitAccessMixin, View):
    """Display a single unit."""

    template_name = "dashboard/properties/units/detail.html"

    def get(self, request, pk):
        unit = self.get_unit(pk)
        return render(
            request,
            self.template_name,
            {
                "unit": unit,
                "building": unit.building,
                "property": unit.building.property_ref,
            },
        )


class UnitUpdateView(LandlordUnitAccessMixin, ServiceFormMixin, View):
    """Update an existing unit."""

    template_name = "dashboard/properties/units/form.html"

    def get(self, request, pk):
        unit = self.get_unit(pk)
        return self.render_form(
            form=UnitForm(instance=unit),
            context={
                "unit": unit,
                "building": unit.building,
                "property": unit.building.property_ref,
            },
        )

    def post(self, request, pk):
        unit = self.get_unit(pk)
        form = UnitForm(request.POST, instance=unit)

        if not form.is_valid():
            return self.render_form(
                form=form,
                context={
                    "unit": unit,
                    "building": unit.building,
                    "property": unit.building.property_ref,
                },
            )

        try:
            UnitService.update(unit=unit, data=form.cleaned_data)
        except ValidationError as e:
            self.handle_service_errors(form, e)
            return self.render_form(
                form=form,
                context={
                    "unit": unit,
                    "building": unit.building,
                    "property": unit.building.property_ref,
                },
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
        building_id = building.id

        UnitService.delete(unit=unit)

        messages.success(request, _("Unit deleted successfully."))
        return redirect("properties:building-detail", pk=building_id)

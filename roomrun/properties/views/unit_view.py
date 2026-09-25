from uuid import UUID

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count
from django.db.models import Q
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from django.views import View
from djmoney.money import Money
from properties.forms import PropertyImageForm
from properties.forms import UnitForm
from properties.mixins import LandlordUnitAccessMixin
from properties.mixins import ServiceFormMixin
from properties.models import Unit
from properties.services import PropertyImageService
from properties.services import UnitService


class LandlordUnitOverviewView(LandlordUnitAccessMixin, View):
    """List and filter every housing unit owned by the current landlord."""

    template_name = "dashboard/properties/units/list.html"
    paginate_by = 20

    def get(self, request):
        landlord = self.get_landlord()
        search = request.GET.get("search", "").strip()
        status_filter = request.GET.get("status", "").strip().upper()
        property_filter = request.GET.get("property", "").strip()

        queryset = Unit.objects.filter(
            building__property_ref__landlord=landlord,
        ).select_related("building", "building__property_ref")

        if search:
            queryset = queryset.filter(
                Q(unit_number__icontains=search)
                | Q(building__name__icontains=search)
                | Q(building__property_ref__name__icontains=search)
                | Q(building__property_ref__property_number__icontains=search)
            )
        valid_statuses = {choice for choice, _label in Unit._meta.get_field("status").choices}
        if status_filter in valid_statuses:
            queryset = queryset.filter(status=status_filter)
        else:
            status_filter = ""
        try:
            property_filter = str(UUID(property_filter)) if property_filter else ""
        except ValueError:
            property_filter = ""
        if property_filter:
            queryset = queryset.filter(building__property_ref_id=property_filter)

        counts = {
            row["status"]: row["total"]
            for row in Unit.objects.filter(
                building__property_ref__landlord=landlord,
            ).values("status").annotate(total=Count("pk"))
        }
        page_obj = Paginator(
            queryset.order_by("building__property_ref__name", "building__name", "unit_number"),
            self.paginate_by,
        ).get_page(request.GET.get("page"))

        return render(
            request,
            self.template_name,
            {
                "units": page_obj,
                "page_obj": page_obj,
                "search": search,
                "status_filter": status_filter,
                "property_filter": property_filter,
                "status_choices": Unit._meta.get_field("status").choices,
                "properties": landlord.properties.order_by("name"),
                "unit_count": sum(counts.values()),
                "available_count": counts.get("AVAILABLE", 0),
                "occupied_count": counts.get("OCCUPIED", 0),
                "maintenance_count": counts.get("MAINTENANCE", 0),
                "result_count": queryset.count(),
            },
        )


class UnitListView(LandlordUnitAccessMixin, View):
    """List all units in a given building."""

    template_name = "dashboard/properties/units/list.html"
    paginate_by = 20

    def get(self, request, property_id, building_id):
        building = self.get_building(property_id, building_id)

        search = request.GET.get("search", "").strip()
        status_filter = request.GET.get("status", "").strip().upper()
        queryset = building.units.select_related("building__property_ref")
        if search:
            queryset = queryset.filter(
                Q(unit_number__icontains=search)
                | Q(building__name__icontains=search)
                | Q(building__property_ref__name__icontains=search)
            )
        valid_statuses = {choice for choice, _label in Unit._meta.get_field("status").choices}
        if status_filter in valid_statuses:
            queryset = queryset.filter(status=status_filter)
        else:
            status_filter = ""

        counts = {
            row["status"]: row["total"]
            for row in building.units.values("status").annotate(total=Count("pk"))
        }
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
                "search": search,
                "status_filter": status_filter,
                "property_filter": str(building.property_ref_id),
                "status_choices": Unit._meta.get_field("status").choices,
                "properties": [building.property_ref],
                "unit_count": sum(counts.values()),
                "available_count": counts.get("AVAILABLE", 0),
                "occupied_count": counts.get("OCCUPIED", 0),
                "maintenance_count": counts.get("MAINTENANCE", 0),
                "result_count": queryset.count(),
            },
        )


class UnitCreateView(LandlordUnitAccessMixin, ServiceFormMixin, View):
    """Create a new unit inside a building."""

    template_name = "dashboard/properties/units/form.html"

    @staticmethod
    def apply_property_currency(form, building):
        """Keep the unit rent in the currency configured for its property."""
        rent = form.cleaned_data["monthly_rent"]
        form.cleaned_data["monthly_rent"] = Money(
            rent.amount,
            building.property_ref.default_currency,
        )

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

        self.apply_property_currency(form, building)

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

        UnitCreateView.apply_property_currency(form, unit.building)

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

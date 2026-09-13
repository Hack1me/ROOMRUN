# properties/views/property.py

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import models
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from django.views import View
from properties.forms import PropertyConfigurationForm
from properties.forms import PropertyForm
from properties.forms import PropertyImageForm
from properties.mixins import LandlordPropertyMixin
from properties.mixins import LandlordRequiredMixin
from properties.mixins import ServiceFormMixin
from properties.models import Property
from properties.services import PropertyService
from properties.services import PropertyImageService


class PropertyListView(LandlordRequiredMixin, View):
    """List all properties owned by the authenticated landlord."""

    template_name = "dashboard/properties/list.html"
    paginate_by = 12

    def get(self, request):
        landlord = self.get_landlord()

        search = request.GET.get("search", "").strip()
        status_filter = request.GET.get("status", "").strip()
        city_filter = request.GET.get("city", "").strip()
        sort = request.GET.get("sort", "").strip()

        queryset = (
            Property.objects
            .filter(landlord=landlord)
            .prefetch_related("images", "buildings__units")
            .annotate(
                _occupied_units=models.Count(
                    "buildings__units",
                    filter=models.Q(buildings__units__status="OCCUPIED"),
                    distinct=True,
                ),
                _unit_count=models.Count(
                    "buildings__units",
                    distinct=True,
                ),
            )
        )

        if search:
            queryset = queryset.filter(
                models.Q(name__icontains=search)
                | models.Q(address__icontains=search)
                | models.Q(property_number__icontains=search)
            )

        if status_filter:
            queryset = queryset.filter(status=status_filter.upper())

        if city_filter:
            queryset = queryset.filter(city__icontains=city_filter)

        if sort == "name":
            queryset = queryset.order_by("name")
        else:
            queryset = queryset.order_by("-created_at")

        paginator = Paginator(queryset, self.paginate_by)
        page_obj = paginator.get_page(request.GET.get("page"))

        for prop in page_obj:
            prop.occupied_units = prop._occupied_units or 0
            prop.unit_count = prop._unit_count or 0
            prop.building_count = len(prop.buildings.all())

            total_rent = 0.0
            for building in prop.buildings.all():
                for unit in building.units.all():
                    total_rent += float(unit.monthly_rent.amount)

            prop.total_rent = total_rent
            prop.average_rent = (
                total_rent / prop.unit_count if prop.unit_count else 0.0
            )

        cities = (
            Property.objects
            .filter(landlord=landlord)
            .values_list("city", flat=True)
            .distinct()
            .order_by("city")
        )

        return render(
            request,
            self.template_name,
            {
                "properties": page_obj,
                "page_obj": page_obj,
                "search": search,
                "status_filter": status_filter,
                "city_filter": city_filter,
                "sort": sort,
                "cities": cities,
            },
        )


class PropertyCreateView(LandlordRequiredMixin, ServiceFormMixin, View):
    """Create a new property for the authenticated landlord."""

    template_name = "dashboard/properties/form.html"

    def get(self, request):
        return self.render_form(
            form=PropertyForm(),
            context={"page_title": _("Create property")},
        )

    def post(self, request):
        form = PropertyForm(request.POST, request.FILES)

        if not form.is_valid():
            return self.render_form(
                form=form,
                context={"page_title": _("Create property")},
            )

        try:
            property_obj = PropertyService.create(
                landlord=self.get_landlord(),
                data=form.cleaned_data,
            )
        except ValidationError as e:
            self.handle_service_errors(form, e)
            return self.render_form(
                form=form,
                context={"page_title": _("Create property")},
            )

        action = request.POST.get("action", "continue")

        if action == "save":
            messages.success(request, _("Property saved successfully."))
            return redirect("properties:property-list")

        messages.success(request, _("Property created successfully."))
        return redirect("properties:property-configure", pk=property_obj.pk)


class PropertyDetailView(LandlordPropertyMixin, View):
    """Display a single property owned by the authenticated landlord."""

    template_name = "dashboard/properties/detail.html"

    def get(self, request, pk):
        property_obj = get_object_or_404(
            Property.objects
            .filter(landlord=self.get_landlord())
            .prefetch_related("images"),
            pk=pk,
        )
        return render(
            request,
            self.template_name,
            {"property": property_obj},
        )


class PropertyUpdateView(LandlordPropertyMixin, ServiceFormMixin, View):
    """Update an existing property owned by the authenticated landlord."""

    template_name = "dashboard/properties/form.html"

    def get(self, request, pk):
        property_obj = self.get_property(pk)
        return self.render_form(
            form=PropertyForm(instance=property_obj),
            context={
                "property": property_obj,
                "page_title": _("Edit property"),
            },
        )

    def post(self, request, pk):
        property_obj = self.get_property(pk)

        form = PropertyForm(
            request.POST,
            request.FILES,
            instance=property_obj,
        )

        if not form.is_valid():
            return self.render_form(
                form=form,
                context={
                    "property": property_obj,
                    "page_title": _("Edit property"),
                },
            )

        try:
            PropertyService.update(
                property_obj=property_obj,
                data=form.cleaned_data,
            )
        except ValidationError as e:
            self.handle_service_errors(form, e)
            return self.render_form(
                form=form,
                context={
                    "property": property_obj,
                    "page_title": _("Edit property"),
                },
            )

        return self.service_success(
            _("Property updated successfully."),
            "properties:property-detail",
            pk=property_obj.pk,
        )


class PropertyConfigurationView(LandlordPropertyMixin, ServiceFormMixin, View):
    """Configure an existing property (Step 2 of the creation flow)."""

    template_name = "dashboard/properties/configuration.html"

    def get(self, request, pk):
        property_obj = self.get_property(pk)
        return self.render_form(
            form=PropertyConfigurationForm(instance=property_obj),
            context={
                "property": property_obj,
                "page_title": _("Property configuration"),
            },
        )

    def post(self, request, pk):
        property_obj = self.get_property(pk)

        form = PropertyConfigurationForm(
            request.POST,
            instance=property_obj,
        )

        if not form.is_valid():
            return self.render_form(
                form=form,
                context={
                    "property": property_obj,
                    "page_title": _("Property configuration"),
                },
            )

        try:
            PropertyService.update(
                property_obj=property_obj,
                data=form.cleaned_data,
            )
        except ValidationError as e:
            self.handle_service_errors(form, e)
            return self.render_form(
                form=form,
                context={
                    "property": property_obj,
                    "page_title": _("Property configuration"),
                },
            )

        action = request.POST.get("action", "continue")

        if action == "save":
            messages.success(request, _("Property configuration saved successfully."))
            return redirect("properties:property-list")

        messages.success(request, _("Property configuration updated successfully."))
        return redirect("properties:property-images", pk=property_obj.pk)


class PropertyImagesView(LandlordPropertyMixin, ServiceFormMixin, View):
    """Upload property images (Step 3 of the creation flow)."""

    template_name = "dashboard/properties/images.html"
    max_images = 8

    def get(self, request, pk):
        property_obj = self.get_property(pk)
        return render(
            request,
            self.template_name,
            {"property": property_obj, "images": property_obj.images.all()},
        )

    def post(self, request, pk):
        property_obj = self.get_property(pk)
        files = request.FILES.getlist("images")
        existing_count = property_obj.images.count()

        if existing_count + len(files) > self.max_images:
            messages.error(
                request,
                _("A property can have a maximum of %(count)s images.")
                % {"count": self.max_images},
            )
            return redirect("properties:property-images", pk=property_obj.pk)

        for index, uploaded_file in enumerate(files):
            form = PropertyImageForm(
                {"caption": _("Property image"), "is_primary": not property_obj.images.exists() and index == 0},
                {"image": uploaded_file},
            )
            if not form.is_valid():
                self.add_form_errors_as_messages(form)
                return redirect("properties:property-images", pk=property_obj.pk)

            try:
                PropertyImageService.create(
                    property_obj=property_obj,
                    data=form.cleaned_data,
                )
            except ValidationError as exc:
                self.handle_service_errors(form, exc)
                self.add_form_errors_as_messages(form)
                return redirect("properties:property-images", pk=property_obj.pk)

        messages.success(request, _("Property created successfully."))
        return redirect("properties:property-detail", pk=property_obj.pk)


class PropertyDeleteView(LandlordPropertyMixin, View):
    """Delete a property owned by the authenticated landlord."""

    template_name = "dashboard/properties/confirm_delete.html"

    def get(self, request, pk):
        property_obj = self.get_property(pk)
        return render(
            request,
            self.template_name,
            {"property": property_obj},
        )

    def post(self, request, pk):
        property_obj = self.get_property(pk)
        PropertyService.delete(property=property_obj)

        messages.success(request, _("Property deleted successfully."))
        return redirect("properties:property-list")

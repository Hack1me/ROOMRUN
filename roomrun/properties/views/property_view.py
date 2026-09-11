# properties/views/property.py

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from django.views import View
from properties.forms import PropertyForm
from properties.mixins import LandlordPropertyMixin
from properties.mixins import LandlordRequiredMixin
from properties.models import Property
from properties.services import PropertyService


class PropertyListView(LandlordRequiredMixin, View):
    """List all properties owned by the authenticated landlord."""

    template_name = "dashboard/properties/list.html"
    paginate_by = 10

    def get(self, request):
        landlord = self.get_landlord()

        queryset = (
            Property.objects
            .filter(landlord=landlord)
            .prefetch_related("images")
            .order_by("-created_at")
        )

        paginator = Paginator(queryset, self.paginate_by)
        page_obj = paginator.get_page(request.GET.get("page"))

        return render(
            request,
            self.template_name,
            {"properties": page_obj, "page_obj": page_obj},
        )


class PropertyCreateView(LandlordRequiredMixin, View):
    """Create a new property for the authenticated landlord."""

    template_name = "dashboard/properties/form.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {
                "form": PropertyForm(),
                "page_title": _("Create property"),
            },
        )

    def post(self, request):
        form = PropertyForm(request.POST, request.FILES)

        if not form.is_valid():
            return render(
                request,
                self.template_name,
                {
                    "form": form,
                    "page_title": _("Create property"),
                },
            )

        try:
            PropertyService.create(
                landlord=self.get_landlord(),
                data=form.cleaned_data,
            )
        except ValidationError as e:
            for field, errors in e.message_dict.items():
                for error in errors:
                    form.add_error(field, error)
            return render(
                request,
                self.template_name,
                {"form": form, "page_title": _("Create property")},
            )

        messages.success(request, _("Property created successfully."))
        return redirect("properties:property-list")


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


class PropertyUpdateView(LandlordPropertyMixin, View):
    """Update an existing property owned by the authenticated landlord."""

    template_name = "dashboard/properties/form.html"

    def get(self, request, pk):
        property_obj = self.get_property(pk)
        form = PropertyForm(instance=property_obj)

        return render(
            request,
            self.template_name,
            {
                "form": form,
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
            return render(
                request,
                self.template_name,
                {
                    "form": form,
                    "property": property_obj,
                    "page_title": _("Edit property"),
                },
            )

        try:
            PropertyService.update(
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
                    "form": form,
                    "property": property_obj,
                    "page_title": _("Edit property"),
                },
            )

        messages.success(request, _("Property updated successfully."))
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

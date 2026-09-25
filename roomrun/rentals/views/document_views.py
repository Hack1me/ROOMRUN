import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views import View
from rentals.models import RentalContract
from utils.pdf import PDFError
from utils.pdf import PDFOptions
from utils.pdf import PDFService

logger = logging.getLogger(__name__)


class LeaseDocumentAccessMixin(LoginRequiredMixin):
    """Restrict lease documents to the contract's tenant or property landlord."""

    def get_lease(self, pk):
        lease = get_object_or_404(
            RentalContract.objects.select_related(
                "tenant__user",
                "unit__building__property_ref__landlord__user",
                "unit__building",
            ),
            pk=pk,
        )
        tenant_profile = getattr(self.request.user, "tenant_profile", None)
        landlord_profile = getattr(self.request.user, "landlord_profile", None)
        is_tenant = tenant_profile and lease.tenant_id == tenant_profile.pk
        is_landlord = (
            landlord_profile
            and lease.unit.building.property_ref.landlord_id == landlord_profile.pk
        )
        if not (is_tenant or is_landlord):
            raise PermissionDenied
        return lease

    @staticmethod
    def get_document_context(lease):
        advance_total = lease.monthly_rent * lease.advance_rent_months
        return {
            "lease": lease,
            "advance_total": advance_total,
            "document_date": timezone.localdate(),
        }


class LeaseDocumentPreviewView(LeaseDocumentAccessMixin, View):
    template_name = "pdf/rentals/lease.html"

    def get(self, request, pk):
        lease = self.get_lease(pk)
        return render(
            request,
            self.template_name,
            self.get_document_context(lease),
        )


class LeasePDFView(LeaseDocumentAccessMixin, View):
    template_name = "pdf/rentals/lease.html"

    def get(self, request, pk):
        lease = self.get_lease(pk)
        filename = f"lease-{lease.contract_number}.pdf"
        try:
            return PDFService.generate_response(
                template=self.template_name,
                context=self.get_document_context(lease),
                filename=filename,
                download=True,
                options=PDFOptions(
                    page_size="A4",
                    orientation="portrait",
                    margin_top="0",
                    margin_right="0",
                    margin_bottom="0",
                    margin_left="0",
                ),
            )
        except PDFError:
            logger.exception("Unable to generate lease PDF | contract=%s", lease.pk)
            messages.error(request, _("The lease PDF could not be generated. Please try again."))
            return redirect("rentals:lease-document", pk=lease.pk)

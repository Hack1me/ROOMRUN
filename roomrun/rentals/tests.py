import base64
from types import SimpleNamespace
from uuid import uuid4

from django import forms
from django.test import SimpleTestCase
from django.urls import resolve
from django.urls import reverse
from django.template.loader import render_to_string
from djmoney.money import Money

from rentals.forms import RentalContractForm
from rentals.forms import SignatureImageField
from rentals.forms import TenantContractSignatureForm
from rentals.views.ten_ren_views import TenantRentalContractSignView


class _SignatureForm(forms.Form):
    signature = SignatureImageField()


class SignatureImageFieldTests(SimpleTestCase):
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\x0dIDATx\x9cc\xf8\xcf\xc0\xf0\x1f\x00\x05"
        b"\x00\x01\xff\x89\x99=\x1d\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    def test_accepts_canvas_png_data_url(self):
        data_url = "data:image/png;base64," + base64.b64encode(self.png).decode()

        form = _SignatureForm(data={"signature": data_url})

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["signature"].content_type, "image/png")

    def test_rejects_unsupported_canvas_data_url(self):
        form = _SignatureForm(data={"signature": "data:image/svg+xml;base64,PHN2Zy8+"})

        self.assertFalse(form.is_valid())
        self.assertIn("signature", form.errors)


class TenantContractUrlTests(SimpleTestCase):
    def test_contract_signature_url_is_routed(self):
        url = reverse(
            "rentals:tenant-rental-contract-sign",
            kwargs={"pk": "00000000-0000-0000-0000-000000000000"},
        )
        match = resolve(url)

        self.assertIs(match.func.view_class, TenantRentalContractSignView)


class RentalTemplateRenderTests(SimpleTestCase):
    def setUp(self):
        rental_property = SimpleNamespace(
            name="Résidence Test",
            address="1 rue des Tests",
            city=None,
        )
        unit = SimpleNamespace(
            pk=uuid4(),
            unit_number="A-01",
            monthly_rent=Money(50000, "XAF"),
            building=SimpleNamespace(name="Bâtiment A", property_ref=rental_property),
        )
        self.application = SimpleNamespace(
            pk=uuid4(),
            application_number="APP-TEST",
            unit=unit,
            get_status_display=lambda: "Pending",
        )
        self.contract = SimpleNamespace(contract_number="CNT-TEST")

    def test_landlord_contract_page_renders_signature_canvas(self):
        rendered = render_to_string(
            "dashboard/rentals/applications/landlord/contract_form.html",
            {
                "application": self.application,
                "tenant_user": SimpleNamespace(full_name="Tenant Test"),
                "form": RentalContractForm(),
                "user": SimpleNamespace(profile_picture=None),
            },
        )

        self.assertIn('id="signatureCanvas"', rendered)
        self.assertIn('id="signatureInput"', rendered)
        self.assertIn("canvas.toDataURL('image/png')", rendered)

    def test_tenant_signature_page_renders_upload_form(self):
        rendered = render_to_string(
            "dashboard/rentals/contracts/tenant/sign.html",
            {"contract": self.contract, "form": TenantContractSignatureForm()},
        )

        self.assertIn('enctype="multipart/form-data"', rendered)
        self.assertIn('name="tenant_signature"', rendered)

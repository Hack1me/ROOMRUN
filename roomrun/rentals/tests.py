import uuid
from datetime import date, timedelta
from unittest import mock

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from djmoney.money import Money

from properties.models import Property, Building, Unit
from rentals.forms import RentalApplicationForm, RentalContractForm
from rentals.managers import LandlordRentalQuerySet
from rentals.models import RentalApplication, RentalContract
from rentals.services import RentalApplicationService, RentalContractService
from users.models import User, Landlord, Tenant
from utils.enums import ApplicationStatus, ContractStatus, UnitStatus


# =====================================================================
# FIXTURE HELPERS
# =====================================================================


class RentalTestCase(TestCase):
    """Base test case providing reusable rental fixtures."""

    @staticmethod
    def _create_user(email, first_name="Test", last_name="User", password="testpass123"):
        return User.objects.create_user(
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=password,
        )

    @classmethod
    def _create_landlord(cls, email="landlord@test.com"):
        user = cls._create_user(email=email, first_name="Landlord", last_name="Test")
        return Landlord.objects.create(user=user)

    @classmethod
    def _create_tenant(cls, email="tenant@test.com"):
        user = cls._create_user(email=email, first_name="Tenant", last_name="Test")
        return Tenant.objects.create(user=user)

    @classmethod
    def _create_property(cls, landlord):
        return Property.objects.create(
            landlord=landlord,
            name="Test Property",
            address="1 Test Street",
            status="ACTIVE",
        )

    @classmethod
    def _create_building(cls, property_obj):
        return Building.objects.create(
            property_ref=property_obj,
            name="Test Building",
            status="ACTIVE",
        )

    @classmethod
    def _create_unit(cls, building, status=UnitStatus.AVAILABLE, monthly_rent=None):
        if monthly_rent is None:
            monthly_rent = Money(50000, "XAF")
        return Unit.objects.create(
            building=building,
            unit_number="A-01",
            monthly_rent=monthly_rent,
            status=status,
        )

    @classmethod
    def _create_rental_application(
        cls,
        tenant,
        unit,
        status=ApplicationStatus.PENDING,
        desired_move_in_date=None,
    ):
        if desired_move_in_date is None:
            desired_move_in_date = date.today() + timedelta(days=30)
        return RentalApplication.objects.create(
            tenant=tenant,
            unit=unit,
            status=status,
            desired_move_in_date=desired_move_in_date,
            desired_duration=12,
            occupants_count=1,
        )


# =====================================================================
# MODEL TESTS
# =====================================================================


class RentalApplicationModelTests(RentalTestCase):
    """Tests for the RentalApplication model."""

    def test_application_number_auto_generated_on_create(self):
        """An application_number should be assigned automatically."""
        landlord = self._create_landlord()
        property_obj = self._create_property(landlord)
        building = self._create_building(property_obj)
        unit = self._create_unit(building)
        tenant = self._create_tenant()

        application = self._create_rental_application(tenant=tenant, unit=unit)

        self.assertIsNotNone(application.application_number)
        self.assertIn("APP", application.application_number)

    def test_str_returns_application_number(self):
        """__str__ should return the application_number."""
        landlord = self._create_landlord()
        property_obj = self._create_property(landlord)
        building = self._create_building(property_obj)
        unit = self._create_unit(building)
        tenant = self._create_tenant()
        application = self._create_rental_application(tenant=tenant, unit=unit)

        self.assertEqual(str(application), application.application_number)

    def test_clean_raises_when_approved_duplicate_exists(self):
        """Approving a duplicate tenant/unit pair should raise ValidationError."""
        landlord = self._create_landlord()
        property_obj = self._create_property(landlord)
        building = self._create_building(property_obj)
        unit = self._create_unit(building)
        tenant = self._create_tenant()

        self._create_rental_application(
            tenant=tenant, unit=unit, status=ApplicationStatus.APPROVED
        )

        duplicate = RentalApplication(
            tenant=tenant,
            unit=unit,
            status=ApplicationStatus.APPROVED,
            desired_move_in_date=date.today() + timedelta(days=30),
            desired_duration=12,
            occupants_count=1,
        )
        with self.assertRaises(ValidationError):
            duplicate.full_clean()

    def test_clean_raises_when_non_pending_has_no_reviewed_at(self):
        """Setting a non-PENDING status without reviewed_at should fail."""
        landlord = self._create_landlord()
        property_obj = self._create_property(landlord)
        building = self._create_building(property_obj)
        unit = self._create_unit(building)
        tenant = self._create_tenant()

        application = self._create_rental_application(tenant=tenant, unit=unit)
        application.status = ApplicationStatus.APPROVED
        application.reviewed_at = None

        with self.assertRaises(ValidationError):
            application.full_clean()

    def test_get_absolute_url(self):
        """get_absolute_url should reverse to the detail view."""
        landlord = self._create_landlord()
        property_obj = self._create_property(landlord)
        building = self._create_building(property_obj)
        unit = self._create_unit(building)
        tenant = self._create_tenant()
        application = self._create_rental_application(tenant=tenant, unit=unit)

        url = application.get_absolute_url()
        expected = reverse("rentals:rental-application-detail", kwargs={"pk": application.pk})
        self.assertEqual(url, expected)


class RentalContractModelTests(RentalTestCase):
    """Tests for the RentalContract model."""

    def test_contract_number_auto_generated_on_create(self):
        """A contract_number should be assigned automatically."""
        landlord = self._create_landlord()
        property_obj = self._create_property(landlord)
        building = self._create_building(property_obj)
        unit = self._create_unit(building)
        tenant = self._create_tenant()

        contract = RentalContract.objects.create(
            tenant=tenant,
            unit=unit,
            status=ContractStatus.ACTIVE,
            start_date=date.today(),
            monthly_rent=Money(50000, "XAF"),
        )

        self.assertIsNotNone(contract.contract_number)
        self.assertIn("CNT", contract.contract_number)

    def test_str_returns_contract_number(self):
        """__str__ should return the contract_number."""
        contract = RentalContract(
            contract_number="CNT-TEST",
            start_date=date.today(),
            monthly_rent=Money(50000, "XAF"),
        )
        self.assertEqual(str(contract), "CNT-TEST")

    def test_initial_payment_property(self):
        """initial_payment should equal deposit + monthly_rent * advance_rent_months."""
        landlord = self._create_landlord()
        property_obj = self._create_property(landlord)
        building = self._create_building(property_obj)
        unit = self._create_unit(building)
        tenant = self._create_tenant()

        contract = RentalContract(
            tenant=tenant,
            unit=unit,
            status=ContractStatus.ACTIVE,
            start_date=date.today(),
            monthly_rent=Money(50000, "XAF"),
            deposit=Money(10000, "XAF"),
            advance_rent_months=2,
        )
        expected = Money(10000, "XAF") + (Money(50000, "XAF") * 2)
        self.assertEqual(contract.initial_payment, expected)

    def test_clean_raises_when_end_date_not_after_start_date(self):
        """Setting end_date <= start_date should raise ValidationError."""
        landlord = self._create_landlord()
        property_obj = self._create_property(landlord)
        building = self._create_building(property_obj)
        unit = self._create_unit(building)
        tenant = self._create_tenant()

        contract = RentalContract(
            tenant=tenant,
            unit=unit,
            status=ContractStatus.ACTIVE,
            start_date=date.today() + timedelta(days=30),
            end_date=date.today(),
            monthly_rent=Money(50000, "XAF"),
        )
        with self.assertRaises(ValidationError):
            contract.full_clean()

    def test_get_absolute_url(self):
        """get_absolute_url should reverse to the detail view."""
        contract = RentalContract(
            contract_number="CNT-TEST",
            start_date=date.today(),
            monthly_rent=Money(50000, "XAF"),
        )
        url = contract.get_absolute_url()
        expected = reverse("rentals:rental-contract-detail", kwargs={"pk": contract.pk})
        self.assertEqual(url, expected)


# =====================================================================
# SERVICE TESTS
# =====================================================================


class RentalApplicationServiceTests(RentalTestCase):
    """Tests for the RentalApplicationService."""

    def test_create_forces_status_to_pending(self):
        """create should always force PENDING status."""
        landlord = self._create_landlord()
        property_obj = self._create_property(landlord)
        building = self._create_building(property_obj)
        unit = self._create_unit(building)
        tenant = self._create_tenant()

        application = RentalApplicationService.create(
            tenant=tenant,
            data={
                "unit": unit,
                "desired_move_in_date": date.today() + timedelta(days=30),
                "desired_duration": 12,
                "occupants_count": 1,
            },
        )

        self.assertEqual(application.status, ApplicationStatus.PENDING)
        self.assertEqual(application.tenant, tenant)

    def test_create_ignores_incoming_status(self):
        """create should ignore any incoming status field."""
        landlord = self._create_landlord()
        property_obj = self._create_property(landlord)
        building = self._create_building(property_obj)
        unit = self._create_unit(building)
        tenant = self._create_tenant()

        application = RentalApplicationService.create(
            tenant=tenant,
            data={
                "unit": unit,
                "status": ApplicationStatus.APPROVED,
                "desired_move_in_date": date.today() + timedelta(days=30),
                "desired_duration": 12,
                "occupants_count": 1,
            },
        )

        self.assertEqual(application.status, ApplicationStatus.PENDING)

    def test_approve_transitions_to_approved(self):
        """approve should transition PENDING → APPROVED."""
        landlord = self._create_landlord()
        property_obj = self._create_property(landlord)
        building = self._create_building(property_obj)
        unit = self._create_unit(building)
        tenant = self._create_tenant()
        reviewer = self._create_user("reviewer@test.com", "Reviewer", "Test")

        application = self._create_rental_application(tenant=tenant, unit=unit)
        result = RentalApplicationService.approve(
            application=application, reviewer=reviewer
        )

        self.assertEqual(result.status, ApplicationStatus.APPROVED)
        self.assertEqual(result.reviewed_by, reviewer)
        self.assertIsNotNone(result.reviewed_at)

    def test_approve_raises_for_non_pending(self):
        """approve should raise ValidationError when application is not PENDING."""
        landlord = self._create_landlord()
        property_obj = self._create_property(landlord)
        building = self._create_building(property_obj)
        unit = self._create_unit(building)
        tenant = self._create_tenant()
        reviewer = self._create_user("reviewer@test.com", "Reviewer", "Test")

        application = self._create_rental_application(
            tenant=tenant, unit=unit, status=ApplicationStatus.APPROVED
        )

        with self.assertRaises(ValidationError):
            RentalApplicationService.approve(
                application=application, reviewer=reviewer
            )

    def test_reject_transitions_to_rejected(self):
        """reject should transition PENDING → REJECTED."""
        landlord = self._create_landlord()
        property_obj = self._create_property(landlord)
        building = self._create_building(property_obj)
        unit = self._create_unit(building)
        tenant = self._create_tenant()
        reviewer = self._create_user("reviewer@test.com", "Reviewer", "Test")

        application = self._create_rental_application(tenant=tenant, unit=unit)
        result = RentalApplicationService.reject(
            application=application, reviewer=reviewer
        )

        self.assertEqual(result.status, ApplicationStatus.REJECTED)
        self.assertEqual(result.reviewed_by, reviewer)
        self.assertIsNotNone(result.reviewed_at)

    def test_reject_raises_for_non_pending(self):
        """reject should raise ValidationError when application is not PENDING."""
        landlord = self._create_landlord()
        property_obj = self._create_property(landlord)
        building = self._create_building(property_obj)
        unit = self._create_unit(building)
        tenant = self._create_tenant()
        reviewer = self._create_user("reviewer@test.com", "Reviewer", "Test")

        application = self._create_rental_application(
            tenant=tenant, unit=unit, status=ApplicationStatus.APPROVED
        )

        with self.assertRaises(ValidationError):
            RentalApplicationService.reject(
                application=application, reviewer=reviewer
            )

    def test_cancel_transitions_to_cancelled(self):
        """cancel should transition PENDING → CANCELLED."""
        landlord = self._create_landlord()
        property_obj = self._create_property(landlord)
        building = self._create_building(property_obj)
        unit = self._create_unit(building)
        tenant = self._create_tenant()

        application = self._create_rental_application(tenant=tenant, unit=unit)
        result = RentalApplicationService.cancel(application=application)

        self.assertEqual(result.status, ApplicationStatus.CANCELLED)

    def test_cancel_raises_for_non_pending(self):
        """cancel should raise ValidationError when application is not PENDING."""
        landlord = self._create_landlord()
        property_obj = self._create_property(landlord)
        building = self._create_building(property_obj)
        unit = self._create_unit(building)
        tenant = self._create_tenant()

        application = self._create_rental_application(
            tenant=tenant, unit=unit, status=ApplicationStatus.APPROVED
        )

        with self.assertRaises(ValidationError):
            RentalApplicationService.cancel(application=application)


class RentalContractServiceTests(RentalTestCase):
    """Tests for the RentalContractService."""

    def test_create_contract_without_application(self):
        """create should create a contract in SIGNING status when no application."""
        landlord = self._create_landlord()
        property_obj = self._create_property(landlord)
        building = self._create_building(property_obj)
        unit = self._create_unit(building)
        tenant = self._create_tenant()

        contract = RentalContractService.create(
            tenant=tenant,
            unit=unit,
            data={
                "start_date": date.today() + timedelta(days=30),
                "monthly_rent": Money(50000, "XAF"),
                "deposit": Money(10000, "XAF"),
                "advance_rent_months": 1,
            },
        )

        self.assertEqual(contract.tenant, tenant)
        self.assertEqual(contract.unit, unit)
        self.assertIsNone(contract.application)
        self.assertEqual(contract.status, ContractStatus.SIGNING)

    def test_create_contract_with_approved_application(self):
        """create should link an approved application and mark it."""
        landlord = self._create_landlord()
        property_obj = self._create_property(landlord)
        building = self._create_building(property_obj)
        unit = self._create_unit(building)
        tenant = self._create_tenant()

        application = self._create_rental_application(
            tenant=tenant, unit=unit, status=ApplicationStatus.APPROVED
        )

        contract = RentalContractService.create(
            tenant=tenant,
            unit=unit,
            application=application,
            data={
                "start_date": date.today() + timedelta(days=30),
                "monthly_rent": Money(50000, "XAF"),
                "deposit": Money(10000, "XAF"),
                "advance_rent_months": 1,
            },
        )

        self.assertEqual(contract.application, application)
        application.refresh_from_db()
        self.assertEqual(application.status, ApplicationStatus.APPROVED)

    def test_create_raises_when_unit_not_available(self):
        """create should raise ValidationError when unit is not AVAILABLE."""
        landlord = self._create_landlord()
        property_obj = self._create_property(landlord)
        building = self._create_building(property_obj)
        unit = self._create_unit(building, status=UnitStatus.OCCUPIED)
        tenant = self._create_tenant()

        with self.assertRaises(ValidationError):
            RentalContractService.create(
                tenant=tenant,
                unit=unit,
                data={
                    "start_date": date.today() + timedelta(days=30),
                    "monthly_rent": Money(50000, "XAF"),
                    "deposit": Money(10000, "XAF"),
                    "advance_rent_months": 1,
                },
            )

    def test_create_raises_for_non_pending_application(self):
        """create should raise ValidationError when application is not PENDING."""
        landlord = self._create_landlord()
        property_obj = self._create_property(landlord)
        building = self._create_building(property_obj)
        unit = self._create_unit(building)
        tenant = self._create_tenant()

        application = self._create_rental_application(
            tenant=tenant, unit=unit, status=ApplicationStatus.APPROVED
        )

        with self.assertRaises(ValidationError):
            RentalContractService.create(
                tenant=tenant,
                unit=unit,
                application=application,
                data={
                    "start_date": date.today() + timedelta(days=30),
                    "monthly_rent": Money(50000, "XAF"),
                    "deposit": Money(10000, "XAF"),
                    "advance_rent_months": 1,
                },
            )

    def test_create_raises_when_application_tenant_mismatch(self):
        """create should raise when application tenant does not match."""
        landlord = self._create_landlord()
        property_obj = self._create_property(landlord)
        building = self._create_building(property_obj)
        unit = self._create_unit(building)
        tenant = self._create_tenant()
        other_tenant = self._create_tenant(email="other@test.com")

        application = self._create_rental_application(
            tenant=other_tenant, unit=unit, status=ApplicationStatus.APPROVED
        )

        with self.assertRaises(ValidationError):
            RentalContractService.create(
                tenant=tenant,
                unit=unit,
                application=application,
                data={
                    "start_date": date.today() + timedelta(days=30),
                    "monthly_rent": Money(50000, "XAF"),
                    "deposit": Money(10000, "XAF"),
                    "advance_rent_months": 1,
                },
            )

    def test_create_raises_when_application_unit_mismatch(self):
        """create should raise when application unit does not match."""
        landlord = self._create_landlord()
        property_obj = self._create_property(landlord)
        building = self._create_building(property_obj)
        unit = self._create_unit(building)
        tenant = self._create_tenant()

        other_building = self._create_building(property_obj)
        other_unit = self._create_unit(other_building)

        application = self._create_rental_application(
            tenant=tenant, unit=other_unit, status=ApplicationStatus.APPROVED
        )

        with self.assertRaises(ValidationError):
            RentalContractService.create(
                tenant=tenant,
                unit=unit,
                application=application,
                data={
                    "start_date": date.today() + timedelta(days=30),
                    "monthly_rent": Money(50000, "XAF"),
                    "deposit": Money(10000, "XAF"),
                    "advance_rent_months": 1,
                },
            )

    def test_create_raises_when_contract_already_exists_for_application(self):
        """create should raise when application already has a contract."""
        landlord = self._create_landlord()
        property_obj = self._create_property(landlord)
        building = self._create_building(property_obj)
        unit = self._create_unit(building)
        tenant = self._create_tenant()

        application = self._create_rental_application(
            tenant=tenant, unit=unit, status=ApplicationStatus.APPROVED
        )

        RentalContractService.create(
            tenant=tenant,
            unit=unit,
            application=application,
            data={
                "start_date": date.today() + timedelta(days=30),
                "monthly_rent": Money(50000, "XAF"),
                "deposit": Money(10000, "XAF"),
                "advance_rent_months": 1,
            },
        )

        with self.assertRaises(ValidationError):
            RentalContractService.create(
                tenant=tenant,
                unit=unit,
                application=application,
                data={
                    "start_date": date.today() + timedelta(days=30),
                    "monthly_rent": Money(50000, "XAF"),
                    "deposit": Money(10000, "XAF"),
                    "advance_rent_months": 1,
                },
            )


# =====================================================================
# FORM TESTS
# =====================================================================


class RentalApplicationFormTests(RentalTestCase):
    """Tests for the RentalApplicationForm."""

    def test_valid_form(self):
        """Form should be valid with correct data."""
        landlord = self._create_landlord()
        property_obj = self._create_property(landlord)
        building = self._create_building(property_obj)
        unit = self._create_unit(building)
        tenant = self._create_tenant()

        form = RentalApplicationForm(
            data={
                "unit": unit.pk,
                "desired_move_in_date": date.today() + timedelta(days=30),
                "desired_duration": 12,
                "occupants_count": 1,
                "message": "Hello",
            },
            tenant=tenant,
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_form_rejects_past_move_in_date(self):
        """Form should reject a move-in date in the past."""
        landlord = self._create_landlord()
        property_obj = self._create_property(landlord)
        building = self._create_building(property_obj)
        unit = self._create_unit(building)
        tenant = self._create_tenant()

        form = RentalApplicationForm(
            data={
                "unit": unit.pk,
                "desired_move_in_date": date.today() - timedelta(days=1),
                "desired_duration": 12,
                "occupants_count": 1,
            },
            tenant=tenant,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("desired_move_in_date", form.errors)

    def test_form_rejects_duplicate_pending_application(self):
        """Form should reject when a pending application already exists."""
        landlord = self._create_landlord()
        property_obj = self._create_property(landlord)
        building = self._create_building(property_obj)
        unit = self._create_unit(building)
        tenant = self._create_tenant()

        self._create_rental_application(tenant=tenant, unit=unit)

        form = RentalApplicationForm(
            data={
                "unit": unit.pk,
                "desired_move_in_date": date.today() + timedelta(days=30),
                "desired_duration": 12,
                "occupants_count": 1,
            },
            tenant=tenant,
        )

        self.assertFalse(form.is_valid())

    def test_form_filters_units_to_available(self):
        """Form should only list units with AVAILABLE status."""
        landlord = self._create_landlord()
        property_obj = self._create_property(landlord)
        building = self._create_building(property_obj)
        available_unit = self._create_unit(building, status=UnitStatus.AVAILABLE)
        occupied_unit = self._create_unit(
            building, unit_number="B-01", status=UnitStatus.OCCUPIED
        )
        tenant = self._create_tenant()

        form = RentalApplicationForm(tenant=tenant)
        unit_choices = [choice[0] for choice in form.fields["unit"].choices]

        self.assertIn(available_unit.pk, unit_choices)
        self.assertNotIn(occupied_unit.pk, unit_choices)


class RentalContractFormTests(RentalTestCase):
    """Tests for the RentalContractForm."""

    def test_valid_form(self):
        """Form should be valid with correct data."""
        form = RentalContractForm(
            data={
                "start_date": date.today() + timedelta(days=30),
                "end_date": date.today() + timedelta(days=390),
                "monthly_rent": Money(50000, "XAF"),
                "deposit": Money(10000, "XAF"),
                "advance_rent_months": 1,
            }
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_form_rejects_end_date_not_after_start_date(self):
        """Form should reject when end_date is not after start_date."""
        form = RentalContractForm(
            data={
                "start_date": date.today() + timedelta(days=30),
                "end_date": date.today() + timedelta(days=30),
                "monthly_rent": Money(50000, "XAF"),
                "deposit": Money(10000, "XAF"),
                "advance_rent_months": 1,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("end_date", form.errors)

    def test_form_rejects_negative_monthly_rent(self):
        """Form should reject negative monthly_rent."""
        form = RentalContractForm(
            data={
                "start_date": date.today() + timedelta(days=30),
                "end_date": date.today() + timedelta(days=390),
                "monthly_rent": Money(-1, "XAF"),
                "deposit": Money(10000, "XAF"),
                "advance_rent_months": 1,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("monthly_rent", form.errors)

    def test_form_rejects_zero_advance_rent_months(self):
        """Form should reject advance_rent_months < 1."""
        form = RentalContractForm(
            data={
                "start_date": date.today() + timedelta(days=30),
                "end_date": date.today() + timedelta(days=390),
                "monthly_rent": Money(50000, "XAF"),
                "deposit": Money(10000, "XAF"),
                "advance_rent_months": 0,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("advance_rent_months", form.errors)


# =====================================================================
# MANAGER TESTS
# =====================================================================


class LandlordRentalQuerySetTests(RentalTestCase):
    """Tests for the LandlordRentalQuerySet manager."""

    def test_for_landlord_filters_applications(self):
        """for_landlord should only return applications for the given landlord."""
        landlord1 = self._create_landlord(email="landlord1@test.com")
        landlord2 = self._create_landlord(email="landlord2@test.com")
        property1 = self._create_property(landlord1)
        property2 = self._create_property(landlord2)
        building1 = self._create_building(property1)
        building2 = self._create_building(property2)
        unit1 = self._create_unit(building1)
        unit2 = self._create_unit(building2)
        tenant = self._create_tenant()

        self._create_rental_application(tenant=tenant, unit=unit1)
        self._create_rental_application(tenant=tenant, unit=unit2)

        qs = RentalApplication.landlord_objects.for_landlord(landlord1)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().unit, unit1)

    def test_for_landlord_filters_contracts(self):
        """for_landlord should only return contracts for the given landlord."""
        landlord1 = self._create_landlord(email="landlord1@test.com")
        landlord2 = self._create_landlord(email="landlord2@test.com")
        property1 = self._create_property(landlord1)
        property2 = self._create_property(landlord2)
        building1 = self._create_building(property1)
        building2 = self._create_building(property2)
        unit1 = self._create_unit(building1)
        unit2 = self._create_unit(building2)
        tenant = self._create_tenant()

        RentalContract.objects.create(
            tenant=tenant,
            unit=unit1,
            status=ContractStatus.ACTIVE,
            start_date=date.today(),
            monthly_rent=Money(50000, "XAF"),
        )
        RentalContract.objects.create(
            tenant=tenant,
            unit=unit2,
            status=ContractStatus.ACTIVE,
            start_date=date.today(),
            monthly_rent=Money(50000, "XAF"),
        )

        qs = RentalContract.landlord_objects.for_landlord(landlord1)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().unit, unit1)


# =====================================================================
# URL TESTS
# =====================================================================


class RentalUrlTests(TestCase):
    """Smoke tests for rental URL routing."""

    def test_application_list_url_is_routed(self):
        url = reverse("rentals:rental-application-list")
        self.assertEqual(url, "/rentals/applications/")

    def test_application_create_url_is_routed(self):
        url = reverse("rentals:rental-application-create")
        self.assertEqual(url, "/rentals/applications/create/")

    def test_landlord_applications_url_is_routed(self):
        url = reverse("rentals:landlord-rental-application-list")
        self.assertEqual(url, "/rentals/landlord/applications/")

    def test_landlord_contracts_url_is_routed(self):
        url = reverse("rentals:landlord-rental-contract-list")
        self.assertEqual(url, "/rentals/landlord/contracts/")


# =====================================================================
# CONTRACT INITIAL PAYMENT TESTS
# =====================================================================


class RentalContractInitialPaymentTests(RentalTestCase):
    """Tests for the contract initial payment logic."""

    def test_initial_payment_with_default_values(self):
        """initial_payment with default advance_rent_months=1."""
        landlord = self._create_landlord()
        property_obj = self._create_property(landlord)
        building = self._create_building(property_obj)
        unit = self._create_unit(building)
        tenant = self._create_tenant()

        contract = RentalContract(
            tenant=tenant,
            unit=unit,
            status=ContractStatus.ACTIVE,
            start_date=date.today(),
            monthly_rent=Money(50000, "XAF"),
            deposit=Money(0, "XAF"),
        )

        expected = Money(0, "XAF") + (Money(50000, "XAF") * 1)
        self.assertEqual(contract.initial_payment, expected)

    def test_initial_payment_with_zero_deposit(self):
        """initial_payment with zero deposit should equal monthly_rent * advance_rent_months."""
        landlord = self._create_landlord()
        property_obj = self._create_property(landlord)
        building = self._create_building(property_obj)
        unit = self._create_unit(building)
        tenant = self._create_tenant()

        contract = RentalContract(
            tenant=tenant,
            unit=unit,
            status=ContractStatus.ACTIVE,
            start_date=date.today(),
            monthly_rent=Money(75000, "XAF"),
            deposit=Money(0, "XAF"),
            advance_rent_months=3,
        )

        expected = Money(0, "XAF") + (Money(75000, "XAF") * 3)
        self.assertEqual(contract.initial_payment, expected)

    def test_initial_payment_with_large_values(self):
        """initial_payment should handle large monetary values correctly."""
        landlord = self._create_landlord()
        property_obj = self._create_property(landlord)
        building = self._create_building(property_obj)
        unit = self._create_unit(building)
        tenant = self._create_tenant()

        contract = RentalContract(
            tenant=tenant,
            unit=unit,
            status=ContractStatus.ACTIVE,
            start_date=date.today(),
            monthly_rent=Money(150000, "XAF"),
            deposit=Money(50000, "XAF"),
            advance_rent_months=6,
        )

        expected = Money(50000, "XAF") + (Money(150000, "XAF") * 6)
        self.assertEqual(contract.initial_payment, expected)


# =====================================================================
# SOFT DELETE TESTS
# =====================================================================


class RentalSoftDeleteTests(RentalTestCase):
    """Tests for soft delete behavior on rental models."""

    def test_application_soft_delete(self):
        """Soft-deleting an application should set is_deleted=True."""
        landlord = self._create_landlord()
        property_obj = self._create_property(landlord)
        building = self._create_building(property_obj)
        unit = self._create_unit(building)
        tenant = self._create_tenant()
        application = self._create_rental_application(tenant=tenant, unit=unit)

        application.soft_delete(user=tenant.user)

        self.assertTrue(application.is_deleted)
        self.assertFalse(RentalApplication.objects.filter(pk=application.pk).exists())
        self.assertTrue(
            RentalApplication.all_objects.filter(pk=application.pk).exists()
        )

    def test_contract_soft_delete(self):
        """Soft-deleting a contract should set is_deleted=True."""
        landlord = self._create_landlord()
        property_obj = self._create_property(landlord)
        building = self._create_building(property_obj)
        unit = self._create_unit(building)
        tenant = self._create_tenant()

        contract = RentalContract.objects.create(
            tenant=tenant,
            unit=unit,
            status=ContractStatus.ACTIVE,
            start_date=date.today(),
            monthly_rent=Money(50000, "XAF"),
        )

        contract.soft_delete(user=tenant.user)

        self.assertTrue(contract.is_deleted)
        self.assertFalse(RentalContract.objects.filter(pk=contract.pk).exists())
        self.assertTrue(
            RentalContract.all_objects.filter(pk=contract.pk).exists()
        )

    def test_application_restore(self):
        """Restoring a soft-deleted application should set is_deleted=False."""
        landlord = self._create_landlord()
        property_obj = self._create_property(landlord)
        building = self._create_building(property_obj)
        unit = self._create_unit(building)
        tenant = self._create_tenant()
        application = self._create_rental_application(tenant=tenant, unit=unit)

        application.soft_delete(user=tenant.user)
        application.restore(user=tenant.user)

        self.assertFalse(application.is_deleted)
        self.assertTrue(
            RentalApplication.objects.filter(pk=application.pk).exists()
        )

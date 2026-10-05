from datetime import timedelta

from core.utils.enums import VisitorStatus
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from operations.models import VisitorVisit
from properties.models import Building
from properties.models import Property
from users.models import Employee
from users.models import Guard
from users.models import Landlord
from users.models import User


class GuardVisitorAccessTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com", password="safe-password"
        )
        self.landlord = Landlord.objects.create(user=self.owner)
        self.property = Property.objects.create(
            landlord=self.landlord, name="Residence One", address="1 Main Street"
        )
        self.building = Building.objects.create(
            property_ref=self.property, name="Building A"
        )
        self.visit = VisitorVisit.objects.create(
            building=self.building,
            host=self.owner,
            visitor_name="Marie Visitor",
            expected_arrival=timezone.now() + timedelta(hours=1),
            created_by=self.owner,
            updated_by=self.owner,
        )
        self.guard_user = User.objects.create_user(
            email="guard@example.com", password="safe-password"
        )
        self.guard = Guard.objects.create(
            employee=Employee.objects.create(user=self.guard_user)
        )
        self.guard.landlords.add(self.landlord)

    def test_assigned_guard_can_check_in_expected_visitor(self):
        self.client.force_login(self.guard_user)

        response = self.client.post(
            reverse("operations:guard-visitor-status", args=[self.visit.pk]),
            {"action": "check-in"},
        )

        self.assertRedirects(response, reverse("operations:guard-visitors"))
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.status, VisitorStatus.CHECKED_IN)
        self.assertEqual(self.visit.checked_in_by, self.guard)
        self.assertIsNotNone(self.visit.checked_in_at)

    def test_unassigned_guard_cannot_change_visitor_status(self):
        other_user = User.objects.create_user(
            email="other-guard@example.com", password="safe-password"
        )
        Guard.objects.create(employee=Employee.objects.create(user=other_user))
        self.client.force_login(other_user)

        response = self.client.post(
            reverse("operations:guard-visitor-status", args=[self.visit.pk]),
            {"action": "check-in"},
        )

        self.assertEqual(response.status_code, 404)
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.status, VisitorStatus.EXPECTED)

    def test_guard_can_register_and_check_out_walk_in_visitor(self):
        self.client.force_login(self.guard_user)

        response = self.client.post(
            reverse("operations:guard-visitor-check-in"),
            {
                "building": self.building.pk,
                "visitor_name": "Alex Walk-in",
                "visitor_phone": "+237600000000",
                "purpose": "Delivery",
                "check_in_note": "ID verified",
            },
        )

        self.assertRedirects(response, reverse("operations:guard-visitors"))
        walk_in = VisitorVisit.objects.get(visitor_name="Alex Walk-in")
        self.assertEqual(walk_in.status, VisitorStatus.CHECKED_IN)
        self.assertEqual(walk_in.checked_in_by, self.guard)
        self.assertIsNotNone(walk_in.checked_in_at)
        self.assertEqual(walk_in.created_by, self.guard_user)

        response = self.client.post(
            reverse("operations:guard-visitor-status", args=[walk_in.pk]),
            {"action": "check-out"},
        )

        self.assertRedirects(response, reverse("operations:guard-visitors"))
        walk_in.refresh_from_db()
        self.assertEqual(walk_in.status, VisitorStatus.CHECKED_OUT)
        self.assertEqual(walk_in.checked_out_by, self.guard)
        self.assertIsNotNone(walk_in.checked_out_at)

    def test_walk_in_form_rejects_building_outside_guard_scope(self):
        other_owner = User.objects.create_user(
            email="other-owner.com", password="safe-password"
        )
        other_landlord = Landlord.objects.create(user=other_owner)
        other_property = Property.objects.create(
            landlord=other_landlord, name="Residence Two", address="2 Main Street"
        )
        other_building = Building.objects.create(
            property_ref=other_property, name="Building B"
        )
        self.client.force_login(self.guard_user)

        response = self.client.post(
            reverse("operations:guard-visitor-check-in"),
            {"building": other_building.pk, "visitor_name": "Unauthorised Visitor"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a valid choice")
        self.assertFalse(
            VisitorVisit.objects.filter(visitor_name="Unauthorised Visitor").exists()
        )


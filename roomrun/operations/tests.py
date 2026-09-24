from datetime import timedelta

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
from utils.enums import VisitorStatus


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

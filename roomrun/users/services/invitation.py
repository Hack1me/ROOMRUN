from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from operations.models import UserInvitation
from users.models import User
from utils.enums import InvitationStatus
from utils.enums import UserRole


class UserInvitationService:
    @staticmethod
    def _generate_token() -> str:
        return secrets.token_urlsafe(32)

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    @classmethod
    @transaction.atomic
    def create(cls, *, email: str, invited_by, role: str) -> tuple[UserInvitation, str]:
        email = email.strip().lower()

        UserInvitation.objects.filter(
            email=email,
            invited_by=invited_by,
            role=role,
            status=InvitationStatus.PENDING,
        ).update(
            status=InvitationStatus.REJECTED,
            updated_at=timezone.now(),
        )

        raw_token = cls._generate_token()

        invitation = UserInvitation(
            email=email,
            invited_by=invited_by,
            role=role,
            token_hash=cls._hash_token(raw_token),
            expires_at=timezone.now() + timedelta(hours=settings.INVITATION_EXPIRATION_HOURS),
        )

        invitation.full_clean()
        invitation.save()

        return invitation, raw_token

    @classmethod
    def get_by_token(cls, token: str) -> UserInvitation:
        token_hash = cls._hash_token(token)

        try:
            invitation = UserInvitation.objects.get(token_hash=token_hash)
        except UserInvitation.DoesNotExist:
            raise ValidationError(_("This invitation is invalid."))

        if invitation.is_expired:
            if invitation.status == InvitationStatus.PENDING:
                invitation.status = InvitationStatus.EXPIRED
                invitation.save(update_fields=["status", "updated_at"])
            raise ValidationError(_("This invitation has expired."))

        if invitation.status != InvitationStatus.PENDING:
            raise ValidationError(_("This invitation is no longer valid."))

        return invitation

    @staticmethod
    @transaction.atomic
    def accept(invitation: UserInvitation) -> UserInvitation:
        if not invitation.can_accept:
            raise ValidationError(_("This invitation is no longer valid."))

        invitation.status = InvitationStatus.ACCEPTED
        invitation.accepted_at = timezone.now()

        invitation.save(update_fields=["status", "accepted_at", "updated_at"])

        return invitation

    @staticmethod
    @transaction.atomic
    def cancel(invitation: UserInvitation) -> UserInvitation:
        if invitation.status != InvitationStatus.PENDING:
            raise ValidationError(_("Only pending invitations can be cancelled."))

        invitation.status = InvitationStatus.REJECTED

        invitation.save(update_fields=["status", "updated_at"])

        return invitation


class InvitationAcceptanceService:
    @staticmethod
    @transaction.atomic
    def accept(
        *,
        invitation: UserInvitation,
        password: str,
        first_name: str = "",
        last_name: str = "",
    ) -> User:
        if not invitation.can_accept:
            raise ValidationError(_("This invitation is no longer valid."))

        if User.objects.filter(email__iexact=invitation.email).exists():
            raise ValidationError(_("An account already exists with this email."))

        try:
            user = User.objects.create_user(
                email=invitation.email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_active=True,
            )
        except IntegrityError:
            raise ValidationError(_("An account already exists with this email."))

        InvitationAcceptanceService._create_profile_for_role(user, invitation.role)

        UserInvitationService.accept(invitation)

        return user

    @staticmethod
    def _create_profile_for_role(user: User, role: str) -> None:
        if role == UserRole.LANDLORD:
            from users.models import Landlord
            Landlord.objects.create(user=user)

        elif role == UserRole.TENANT:
            from users.models import Tenant
            Tenant.objects.create(user=user)

        elif role == UserRole.GUARD:
            from users.models import Employee
            from users.models import Guard
            employee = Employee.objects.create(user=user)
            Guard.objects.create(employee=employee)

        elif role == UserRole.MAINTENANCE:
            from users.models import Employee
            from users.models import MaintenanceAgent
            employee = Employee.objects.create(user=user)
            MaintenanceAgent.objects.create(employee=employee)

        else:
            raise ValidationError(_("Unsupported role for invitation."))

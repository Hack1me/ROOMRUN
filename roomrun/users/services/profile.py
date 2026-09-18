from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction
from django.utils.translation import gettext_lazy as _  # noqa: F401

if TYPE_CHECKING:
    from users.models import User


class ProfileService:
    ALLOWED_UPDATE_FIELDS = {
        "first_name",
        "last_name",
        "phone",
        "country",
        "profile_picture",
    }

    @staticmethod
    @transaction.atomic
    def update(user: User, data: dict) -> User:
        changed_fields = []
        old_picture_name = user.profile_picture.name if user.profile_picture else None
        allowed_fields = ProfileService.ALLOWED_UPDATE_FIELDS

        for field, value in data.items():
            if field not in allowed_fields:
                continue

            if not hasattr(user, field):
                msg = f"Field '{field}' does not exist on User model."
                raise AttributeError(
                    msg
                )

            current_value = getattr(user, field)
            if current_value != value:
                setattr(user, field, value)
                changed_fields.append(field)

        if changed_fields:
            user.full_clean()

            update_fields = changed_fields.copy()
            if hasattr(user, "updated_at"):
                update_fields.append("updated_at")

            user.save(update_fields=update_fields)

            if (
                "profile_picture" in changed_fields
                and old_picture_name
                and user.profile_picture.name != old_picture_name
            ):
                storage = user.profile_picture.storage
                transaction.on_commit(lambda: storage.delete(old_picture_name))

        return user

    @staticmethod
    def update_bulk(users: list[User], data: dict) -> list[User]:
        updated_users = []
        for user in users:
            updated = ProfileService.update(user, data)
            updated_users.append(updated)
        return updated_users

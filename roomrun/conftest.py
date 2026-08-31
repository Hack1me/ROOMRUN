from __future__ import annotations

import pytest
from users.models import User


@pytest.fixture(autouse=True)
def _media_storage(settings, tmpdir) -> None:
    settings.MEDIA_ROOT = tmpdir.strpath


@pytest.fixture
def user(db) -> User:
    return User.objects.create_user(
        email="user@example.com",
        password="test-password",  # noqa: S106
    )

"""Keep unit tests isolated from the new RTDB authorization boundary."""

from contextlib import nullcontext
from unittest.mock import Mock

import pytest

from app.services import realtime_access_service


@pytest.fixture(autouse=True)
def mock_realtime_access(monkeypatch):
    # Existing service tests use fake Firestore and must never publish live permissions.
    for name in ("sync_business_member_access", "sync_chat_access", "disable_realtime_user"):
        monkeypatch.setattr(realtime_access_service, name, Mock())
    monkeypatch.setattr(
        realtime_access_service, "changing_business_member_access",
        Mock(side_effect=lambda *a, **k: nullcontext()),
    )

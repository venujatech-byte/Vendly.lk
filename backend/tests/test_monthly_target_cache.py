"""Monthly target saves must invalidate analytics atomically without extra document reads/writes."""

from copy import deepcopy
from unittest.mock import Mock

import pytest
from google.api_core.exceptions import PermissionDenied

from firestore_memory import MemoryFirestore
from app import create_app
from app.core.errors import ApiError
from app.services.analytics_service import get_analytics_version, update_monthly_revenue_target

BUSINESS = "businesses/business-a"


class TargetFirestore(MemoryFirestore):
    # The shared offline transport ignores transforms; model this existing numeric version transform only.
    def commit(self, request, **kwargs):
        result = super().commit(request, **kwargs)
        for write in request["writes"]:
            for transform in write.update_transforms:
                if transform.field_path == "analyticsVersion":
                    path = write.update.name.split("/documents/", 1)[1]
                    self.documents[path]["analyticsVersion"] = self.documents[path].get("analyticsVersion", 0) + transform.increment.integer_value
        return result


@pytest.mark.parametrize("initial", [None, 7])
def test_target_and_version_commit_together_with_one_write_and_no_reads(initial):
    store = TargetFirestore()
    store.put(BUSINESS, {} if initial is None else {"analyticsVersion": initial})
    assert update_monthly_revenue_target(store.client, "business-a", {"monthlyTargetMinor": 500000}) == 500000
    writes = store.client._firestore_api.commit.call_args.kwargs["request"]["writes"]
    assert len(writes) == 1
    assert store.commits == 1
    assert writes[0].update.name.endswith(f"/documents/{BUSINESS}")
    assert writes[0].update.fields["monthlyRevenueTargetMinor"].integer_value == 500000
    transforms = {item.field_path: item for item in writes[0].update_transforms}
    assert transforms["analyticsVersion"].increment.integer_value == 1
    assert transforms["analyticsUpdatedAt"].set_to_server_value
    store.client._firestore_api.batch_get_documents.assert_not_called()
    store.client._firestore_api.run_query.assert_not_called()
    assert get_analytics_version(store.client, "business-a") == (initial or 0) + 1


def test_repeated_saves_keep_versions_monotonic_and_leave_other_businesses_unchanged():
    store = TargetFirestore()
    store.put(BUSINESS, {"analyticsVersion": 3})
    store.put("businesses/business-b", {"analyticsVersion": 8, "monthlyRevenueTargetMinor": 900})
    for target in (100, 200):
        update_monthly_revenue_target(store.client, "business-a", {"monthlyTargetMinor": target})
    assert store.documents[BUSINESS]["analyticsVersion"] == 5
    assert store.documents[BUSINESS]["monthlyRevenueTargetMinor"] == 200
    assert store.documents["businesses/business-b"] == {"analyticsVersion": 8, "monthlyRevenueTargetMinor": 900}


def test_rejected_save_publishes_neither_target_nor_new_version():
    store = TargetFirestore()
    store.put(BUSINESS, {"analyticsVersion": 3, "monthlyRevenueTargetMinor": 100})
    before = deepcopy(store.documents)

    def fail(_store):
        raise PermissionDenied("Synthetic denied target save")

    store.before_commit = fail
    with pytest.raises(PermissionDenied):
        update_monthly_revenue_target(store.client, "business-a", {"monthlyTargetMinor": 200})
    assert store.documents == before


def test_invalid_target_does_not_publish_data_or_cache_changes():
    store = TargetFirestore()
    store.put(BUSINESS, {"analyticsVersion": 3})
    before = deepcopy(store.documents)
    with pytest.raises(ApiError):
        update_monthly_revenue_target(store.client, "business-a", {"monthlyTargetMinor": -1})
    assert store.documents == before
    store.client._firestore_api.commit.assert_not_called()


@pytest.fixture
def api(monkeypatch):
    store = TargetFirestore()
    store.put(BUSINESS, {"analyticsVersion": 3, "monthlyRevenueTargetMinor": 100})
    member = f"{BUSINESS}/members/member-a"
    store.put(member, {"role": "owner", "status": "active"})
    monkeypatch.setattr("app.initialize_firebase", Mock())
    monkeypatch.setattr("app.core.auth.firebase_auth.verify_id_token", Mock(return_value={"uid": "member-a"}))
    monkeypatch.setattr("app.core.authorization.get_firestore_client", lambda: store.client)
    monkeypatch.setattr("app.api.analytics.get_firestore_client", lambda: store.client)
    return create_app({"TESTING": True}).test_client(), store


def test_same_flask_save_used_by_web_and_mobile_exposes_new_version(api):
    client, store = api
    headers = {"Authorization": "Bearer synthetic-token"}
    response = client.patch("/api/v1/businesses/business-a/analytics/monthly-target", json={"monthlyTargetMinor": 500000}, headers=headers)
    assert response.status_code == 200
    assert response.get_json() == {"monthlyTargetMinor": 500000}
    response = client.get("/api/v1/businesses/business-a/analytics/version", headers=headers)
    assert response.get_json() == {"analyticsVersion": 4}
    assert store.commits == 1

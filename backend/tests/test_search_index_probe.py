"""Check offline index recall, read tradeoffs and fallback behavior against the current matcher."""

from copy import deepcopy
import subprocess
import sys

import pytest

from scripts import probe_search_index as probe

MEMBERSHIPS = {("business-a", "owner-a"): {"role": "owner", "status": "active"}}


def sources_for(module, rows):
    # Callers supply the server's ordered rows; this experiment does not replace Firestore collation.
    modules = {name: {"revision": "source-1", "records": []} for name in probe.MODULES}
    modules[module]["records"] = rows
    return {"business-a": modules}


def run(sources, index, query="needle", storage="embedded", **kwargs):
    return probe.simulate(sources, index, MEMBERSHIPS, "business-a", "owner-a", query, storage, **kwargs)


@pytest.mark.parametrize("storage", ["embedded", "sidecar"])
@pytest.mark.parametrize("module, fields", [
    ("orders", {"orderNumber": "Needle"}), ("orders", {"waybillNumber": "Needle"}),
    ("orders", {"customerSnapshot": {"name": "Needle"}}),
    ("orders", {"customerSnapshot": {"normalizedPhone": "Needle"}}),
    ("orders", {"items": [{"name": "Needle"}]}), ("orders", {"items": [{"sku": "Needle"}]}),
    ("orders", {"items": [{"barcode": "Needle"}]}),
    ("products", {"name": "Needle"}), ("products", {"skuPrefix": "Needle"}),
    ("products", {"brand": "Needle"}), ("products", {"categoryName": "Needle"}),
    ("products", {"variantSummaries": [{"sku": "Needle"}]}),
    ("products", {"variantSummaries": [{"barcode": "Needle"}]}),
    ("products", {"variantSummaries": [{"size": "Needle"}]}),
    ("customers", {"name": "Needle"}), ("customers", {"normalizedPhone": "Needle"}),
    ("customers", {"email": "Needle"}),
])
def test_every_existing_search_field_retains_recall_and_projection(storage, module, fields):
    row = {"id": "source-a", "name": "", "createdAt": 1, **fields}
    sources = sources_for(module, [row])
    index = probe.build_index(sources)
    reference = run(sources, index, storage="scan")["results"]
    assert reference[module][0]["id"] == "source-a"
    assert run(sources, index, storage=storage)["results"] == reference


@pytest.mark.parametrize("value, query", [
    ("Straße", "ß"), ("Smart Watch", "smart wa"), ("ශ්‍රී", "ශ්‍රී"), ("தமிழ்", "மிழ்"),
    ("Needle", "<b>needle</b>"), ("Éclair", "eclair"), ("foo   bar", "foo bar"),
    ("s" * 80, "ß" * 80), ("Synthetic", "a"),
])
def test_unicode_multiword_and_sanitizer_behavior_remains_exact(value, query):
    sources = sources_for("products", [{"id": "source-a", "name": value}])
    index = probe.build_index(sources)
    reference = run(sources, index, query, "scan")["results"]
    for storage in ("embedded", "sidecar"):
        assert run(sources, index, query, storage)["results"] == reference


def test_oversized_token_sets_use_overflow_instead_of_truncating_late_variant_matches():
    variants = [{"sku": "".join(chr(0x4000 + number * 60 + char) for char in range(60))} for number in range(100)]
    sources = sources_for("products", [{"id": "large", "name": "Large item", "variantSummaries": variants}])
    index = probe.build_index(sources)
    entry = index["business-a"]["products"]["entries"][0]
    assert entry["overflow"] is True
    assert not entry["tokens"]
    query = variants[-1]["sku"][20:30]
    reference = run(sources, index, query, "scan")["results"]
    assert len(reference["products"]) == 1
    for storage in ("embedded", "sidecar"):
        assert run(sources, index, query, storage)["results"] == reference


def test_regular_and_overflow_results_merge_in_original_rank_order():
    rows = [{"id": letter, "name": name} for letter, name in zip("abcd", ["aaaa", "aabcdefghijklmnopqrstuvwxyz", "aaaa", "a中文漢字aaa"])]
    sources = sources_for("products", rows)
    index = probe.build_index(sources, limit=1)
    for storage in ("embedded", "sidecar"):
        result = run(sources, index, "aa", storage, page_size=1)
        assert [row["id"] for row in result["results"]["products"]] == list("abcd")


@pytest.mark.parametrize("ready", [False, None, "yes"])
def test_partial_or_invalid_readiness_falls_back_without_hiding_records(ready):
    sources = sources_for("products", [{"id": "a", "name": "Needle"}])
    index = probe.build_index(sources)
    index["business-a"]["products"].update(ready=ready, entries=[])
    result = run(sources, index)
    assert result["results"]["products"][0]["id"] == "a"
    assert "products" in result["counts"]["fallback_modules"]


def test_missing_index_uses_the_complete_reference_scan():
    sources = sources_for("products", [{"id": "a", "name": "Needle"}])
    assert run(sources, {}, storage="sidecar")["results"] == run(sources, {}, storage="scan")["results"]


def test_mixed_generations_fall_back_then_aligned_update_and_deletion_remain_correct():
    sources = sources_for("products", [{"id": "a", "name": "Original"}])
    old_index = probe.build_index(sources)
    updated = deepcopy(sources)
    updated["business-a"]["products"].update(revision="source-2", records=[{"id": "a", "name": "Needle"}])
    stale = run(updated, old_index)
    assert stale["results"]["products"][0]["id"] == "a"
    assert "products" in stale["counts"]["fallback_modules"]
    aligned = probe.build_index(updated)
    assert run(updated, aligned)["results"] == stale["results"]
    updated["business-a"]["products"].update(revision="source-3", records=[])
    assert run(updated, aligned)["results"]["products"] == []


def test_failed_index_build_leaves_the_previous_snapshot_and_source_untouched():
    sources = sources_for("orders", [{"id": "a", "createdAt": 1, "orderNumber": "Needle"}])
    previous = probe.build_index(sources)
    before = deepcopy(previous)
    draft = deepcopy(sources)
    draft["business-a"]["orders"]["records"][0]["items"] = [42]
    unchanged_draft = deepcopy(draft)
    with pytest.raises(AttributeError):
        probe.build_index(draft)
    assert previous == before
    assert draft == unchanged_draft


def test_query_visibility_archive_exclusion_and_eight_result_limit_are_preserved():
    rows = [{"id": f"customer-{number:02d}", "name": "Needle", "status": "archived" if number < 3 else "active"} for number in range(20)]
    rows.insert(0, {"id": "missing-name", "email": "needle@example.test"})
    sources = sources_for("customers", rows)
    sources["business-a"]["orders"]["records"] = [
        {"id": "missing-date", "orderNumber": "Needle"},
        {"id": "present-date", "orderNumber": "Needle", "createdAt": 1},
    ]
    index = probe.build_index(sources)
    reference = run(sources, index, storage="scan", page_size=5)["results"]
    assert [row["id"] for row in reference["customers"]] == [f"customer-{number:02d}" for number in range(3, 11)]
    assert [row["id"] for row in reference["orders"]] == ["present-date"]
    for storage in ("embedded", "sidecar"):
        assert run(sources, index, storage=storage, page_size=5)["results"] == reference


def test_tenant_gate_runs_before_any_source_or_index_access():
    with pytest.raises(PermissionError):
        probe.simulate(object(), object(), MEMBERSHIPS, "business-b", "owner-a", "needle")
    inactive = {("business-a", "owner-a"): {"role": "owner", "status": "inactive"}}
    with pytest.raises(PermissionError):
        probe.simulate(object(), object(), inactive, "business-a", "owner-a", "needle")


def test_only_permitted_modules_are_opened_even_with_broader_index_data():
    sources = sources_for("products", [{"id": "a", "name": "Needle"}])
    index = probe.build_index(sources)
    sources["business-a"].update(orders=None, customers=None)
    index["business-a"].update(orders=None, customers=None)
    memberships = {("business-a", "staff-a"): {"role": "custom", "status": "active", "permissions": ["inventory:read"]}}
    result = probe.simulate(sources, index, memberships, "business-a", "staff-a", "needle")
    assert result["results"]["products"][0]["id"] == "a"
    assert result["results"]["orders"] == result["results"]["customers"] == []


def test_overlapping_ids_cannot_cross_tenants_and_record_fields_cannot_forge_scope():
    sources = sources_for("products", [{"id": "same", "name": "Needle local", "businessId": "business-b"}])
    sources["business-b"] = sources_for("products", [{"id": "same", "name": "Needle private"}])["business-a"]
    index = probe.build_index(sources)
    result = run(sources, index)
    assert result["results"]["products"][0]["name"] == "Needle local"


def test_broad_queries_and_overflow_can_cost_more_even_with_exact_result_parity():
    rows = [{"id": f"product-{number:02d}", "name": "aaaa" if number % 2 else "aabcdefghijklmnopqrstuvwxyz"} for number in range(40)]
    sources = sources_for("products", rows)
    index = probe.build_index(sources, limit=1)
    reference = run(sources, index, "aa", "scan", page_size=10)
    embedded = run(sources, index, "aa", "embedded", page_size=10)
    sidecar = run(sources, index, "aa", "sidecar", page_size=10)
    assert embedded["results"] == sidecar["results"] == reference["results"]
    assert reference["counts"]["source_reads"] == 10
    assert embedded["counts"]["source_reads"] == 20
    assert sidecar["counts"]["source_reads"] + sidecar["counts"]["index_reads"] == 40


def test_a_later_page_failure_cannot_return_partial_results(monkeypatch):
    sources = sources_for("products", [{"id": str(number), "name": "Needle"} for number in range(20)])
    index = probe.build_index(sources)
    pages = probe._pages

    def fail_after_first(*args, **kwargs):
        for number, page in enumerate(pages(*args, **kwargs)):
            if number == 1:
                raise RuntimeError("Synthetic failed page")
            yield page

    monkeypatch.setattr(probe, "_pages", fail_after_first)
    with pytest.raises(RuntimeError, match="Synthetic failed page"):
        run(sources, index, "needle absent", page_size=2)


def test_demo_uses_no_firebase_client_and_prints_counts_without_rows(monkeypatch, capsys):
    import app.core.firebase
    import firebase_admin

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Offline probe attempted Firebase access")

    monkeypatch.setattr(app.core.firebase, "get_firestore_client", forbidden)
    monkeypatch.setattr(firebase_admin, "initialize_app", forbidden)
    probe.main()
    output = capsys.readouterr().out
    assert '"offline_model": true' in output
    assert "synthetic@example.test" not in output
    assert "94700000123" not in output
    assert '"results"' not in output


def test_cli_rejects_apply_arguments_instead_of_appearing_to_run_a_migration():
    result = subprocess.run([sys.executable, probe.__file__, "--apply"], capture_output=True, text=True)
    assert result.returncode != 0
    assert not result.stdout
    assert "no arguments or apply mode" in result.stderr

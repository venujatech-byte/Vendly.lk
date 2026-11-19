"""Offline substring-index experiment; synthetic data only, with no Firebase client or migration mode."""

import heapq
import json
import sys
from pathlib import Path

# Match the existing script entry points so this can run from any working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.authorization import membership_has_permission
from app.services.search_service import sanitize_search_query, search_records

MODULES = {"orders": "orders:read", "products": "inventory:read", "customers": "customers:read"}
PAGE_SIZE = 500
# shortcut: This experimental bound needs document/index capacity tests before production use.
TOKEN_LIMIT = 4096


def indexed_values(module, row):
    """Mirror the current matcher inputs only; promotion must share this schema with the matcher."""
    # shortcut: Share this field schema with the matcher before activating a production index.
    if module == "orders":
        contact = row.get("customerSnapshot", {})
        return [row.get("orderNumber"), row.get("waybillNumber"), contact.get("name"), contact.get("normalizedPhone"),
                *[item.get(field) for item in row.get("items", []) for field in ("name", "sku", "barcode")]]
    if module == "products":
        return [row.get(field) for field in ("name", "skuPrefix", "brand", "categoryName")] + [
            item.get(field) for item in row.get("variantSummaries", []) for field in ("sku", "barcode", "size")]
    return [row.get(field) for field in ("name", "normalizedPhone", "email")]


def token_metadata(module, row, limit=TOKEN_LIMIT):
    # Overflow records remain searchable through a separate stream instead of silently losing tokens.
    if limit < 0:
        raise ValueError("Token limit must not be negative.")
    tokens = set()
    for value in indexed_values(module, row):
        text = str(value or "").casefold()
        for position in range(len(text) - 1):
            tokens.add(text[position:position + 2])
            if len(tokens) > limit:
                return {"tokens": frozenset(), "overflow": True}
    return {"tokens": frozenset(tokens), "overflow": False}


def query_visible(module, row):
    # Existing Firestore ordering excludes missing createdAt/name fields before the matcher sees rows.
    return not ((module == "orders" and "createdAt" not in row) or (module == "customers" and "name" not in row))


def build_index(sources, limit=TOKEN_LIMIT):
    """Snapshot preordered fixture rows; generations/readiness are a model contract, not a live schema."""
    index = {}
    for business_id, modules in sources.items():
        index[business_id] = {}
        for module, source in modules.items():
            entries = [
                {"id": row["id"], "rank": rank, **token_metadata(module, row, limit)}
                for rank, row in enumerate(source["records"]) if query_visible(module, row)
            ]
            index[business_id][module] = {"ready": True, "revision": source["revision"], "entries": entries}
    return index


def _pages(rows, counts, kind, page_size):
    # Count the whole fetched page, including unused rows when the matcher stops at eight results.
    offset = 0
    while True:
        page = rows[offset:offset + page_size]
        counts["query_requests"] += 1
        counts[kind] += len(page)
        counts["empty_queries"] += not page
        yield page
        if len(page) < page_size:
            return
        offset += page_size


def _active(module, rows):
    # Archived customers consume reads but never occupy result slots, matching the existing reader.
    return (row for row in rows if module != "customers" or row.get("status", "active") != "archived")


def _full_stream(module, records, counts, page_size):
    visible = [row for row in records if query_visible(module, row)]
    for page in _pages(visible, counts, "source_reads", page_size):
        yield from _active(module, page)


def _indexed_stream(module, records, index, token, storage, counts, page_size):
    by_id = {row["id"]: row for row in records}
    regular = [entry for entry in index["entries"] if token in entry["tokens"]]
    overflow = [entry for entry in index["entries"] if entry["overflow"]]

    def candidates(entries):
        # Sidecar IDs require authoritative source lookups; embedded metadata arrives with its source row.
        kind = "index_reads" if storage == "sidecar" else "source_reads"
        for page in _pages(entries, counts, kind, page_size):
            if storage == "sidecar":
                counts["source_reads"] += len(page)
            for entry in page:
                row = by_id.get(entry["id"])
                if row is not None:
                    yield entry["rank"], row

    # Concatenation could put a later regular match ahead of an earlier overflow match.
    merged = heapq.merge(candidates(regular), candidates(overflow), key=lambda item: item[0])
    yield from _active(module, (row for _rank, row in merged))


def simulate(sources, index, memberships, business_id, uid, query, storage="embedded", page_size=PAGE_SIZE):
    """Model record reads and ACL lookup; authentication, RPCs and real index billing are not simulated."""
    if storage not in {"scan", "embedded", "sidecar"} or page_size < 1:
        raise ValueError("Choose a known layout and a positive page size.")
    member = memberships.get((business_id, uid))
    if not member or member.get("status") != "active":
        raise PermissionError("No active fixture membership for this business.")
    counts = {"source_reads": 0, "index_reads": 0, "query_requests": 0, "empty_queries": 0, "fallback_modules": []}
    text = sanitize_search_query(query).casefold()
    streams = []
    for module, permission in MODULES.items():
        if len(text) < 2 or not membership_has_permission(member, permission):
            streams.append(iter(()))
            continue
        source = sources[business_id][module]
        manifest = index.get(business_id, {}).get(module)
        ready = manifest and manifest.get("ready") is True and manifest.get("revision") == source["revision"]
        if storage == "scan" or not ready:
            if storage != "scan":
                counts["fallback_modules"].append(module)
            streams.append(_full_stream(module, source["records"], counts, page_size))
        else:
            streams.append(_indexed_stream(module, source["records"], manifest, text[:2], storage, counts, page_size))
    # Pass the raw query once: casefold expansion and the sanitizer's length clamp must remain unchanged.
    results = search_records(*streams, query)
    return {"results": results, "counts": counts}


def synthetic_sources():
    # Fixed public test strings only; this script does not accept exported records, credentials or project IDs.
    rows = {
        "orders": [{"id": "special", "createdAt": 1, "orderNumber": "VD-SYNTHETIC", "waybillNumber": "VWB-SYNTHETIC", "customerSnapshot": {"name": "Straße ශ්‍රී தமிழ்", "normalizedPhone": "94700000123"}, "items": [{"name": "Smart Watch USB Cable", "sku": "AB-WATCH-9", "barcode": "890123"}]}],
        "products": [{"id": "special", "name": "Smart Watch Straße ශ්‍රී தமிழ்", "skuPrefix": "AB-WATCH", "brand": "Synthetic", "categoryName": "Accessories", "variantSummaries": [{"sku": "AB-WATCH-9", "barcode": "890123", "size": "Large"}]}],
        "customers": [{"id": "special", "name": "Straße ශ්‍රී தமிழ்", "normalizedPhone": "94700000123", "email": "synthetic@example.test"}],
    }
    for number in range(2000):
        for module in MODULES:
            row = {"id": f"record-{number:04d}", "name": f"Record {number:04d}"}
            if module == "orders":
                row.update(createdAt=-number, orderNumber=f"VD-{number:06d}", customerSnapshot={"name": row["name"]})
            rows[module].append(row)
    # These ASCII fixture IDs/names reproduce the existing per-module server ordering.
    rows["orders"].sort(key=lambda row: (row["createdAt"], row["id"]), reverse=True)
    rows["products"].sort(key=lambda row: row["id"])
    rows["customers"].sort(key=lambda row: (row["name"].encode(), row["id"]))
    return {"synthetic-business": {module: {"revision": "fixture-1", "records": records} for module, records in rows.items()}}


def main():
    sources = synthetic_sources()
    index = build_index(sources)
    memberships = {("synthetic-business", "synthetic-owner"): {"role": "owner", "status": "active"}}
    cases = {"sku_fragment": "watch", "multiword": "smart wa", "phone_fragment": "0123", "casefold": "strasse", "casefold_expansion": "ß", "sinhala": "ශ්‍රී", "tamil": "தமிழ்", "markup": "<b>watch</b>", "rare_no_match": "zz-no-such-record", "broad_no_match": "record zz-no-such-record", "short": "a", "common_match": "record"}
    entries = [entry for module in index["synthetic-business"].values() for entry in module["entries"]]
    # Raw token bytes exclude document/index overhead; row writes exclude manifest and index-entry work.
    report = {
        "offline_model": True, "data_reads_exclude_metadata_and_index_billing": True,
        "index_metadata": {
            "records": len(entries), "token_limit": TOKEN_LIMIT,
            "stored_tokens": sum(len(entry["tokens"]) for entry in entries),
            "raw_token_utf8_bytes": sum(len(token.encode()) for entry in entries for token in entry["tokens"]),
            "overflow_records": sum(entry["overflow"] for entry in entries),
        },
        "row_write_model_excludes_manifests_and_index_entries": True,
        "backfill_row_writes": {"embedded": len(entries), "sidecar": len(entries)},
        "extra_row_writes_per_search_field_change": {"embedded": 0, "sidecar": 1},
        "cases": {},
    }
    for label, query in cases.items():
        reference = simulate(sources, index, memberships, "synthetic-business", "synthetic-owner", query, "scan")
        comparison = {}
        for storage in ("embedded", "sidecar"):
            candidate = simulate(sources, index, memberships, "synthetic-business", "synthetic-owner", query, storage)
            if candidate["results"] != reference["results"]:
                raise AssertionError(f"Synthetic parity failure: {label}")
            comparison[storage] = candidate["counts"]
        report["cases"][label] = {"scan": reference["counts"], **comparison}
    # Only aggregate counts and fixed case labels leave the process; no row values, IDs or query text are logged.
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    if len(sys.argv) != 1:
        raise SystemExit("This offline probe accepts no arguments or apply mode.")
    main()

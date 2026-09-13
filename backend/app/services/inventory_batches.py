"""FIFO inventory batch tracking for accurate Cost of Goods Sold (COGS) and profit calculations."""
from datetime import datetime, timezone


def normalize_batches(batches, fallback_quantity=0, fallback_cost_minor=0):
    """Ensure batches list has valid structure and non-empty items."""
    if not batches:
        if fallback_quantity > 0:
            return [
                {
                    "batchId": "initial",
                    "quantity": int(fallback_quantity),
                    "initialQuantity": int(fallback_quantity),
                    "unitCostMinor": int(fallback_cost_minor or 0),
                    "createdAt": datetime.now(timezone.utc).isoformat(),
                }
            ]
        return []

    result = []
    for b in batches:
        if not isinstance(b, dict):
            continue
        qty = int(b.get("quantity", 0) or 0)
        if qty > 0:
            result.append({
                "batchId": str(b.get("batchId") or "batch"),
                "quantity": qty,
                "initialQuantity": int(b.get("initialQuantity", qty) or qty),
                "unitCostMinor": int(b.get("unitCostMinor", fallback_cost_minor) or 0),
                "createdAt": b.get("createdAt") or datetime.now(timezone.utc).isoformat(),
            })
    return result


def get_active_unit_cost(batches, default_unit_cost_minor=0):
    """Return the unit cost of the oldest active batch with remaining stock."""
    active = [b for b in batches if int(b.get("quantity", 0) or 0) > 0]
    if active:
        return int(active[0].get("unitCostMinor", default_unit_cost_minor) or 0)
    return int(default_unit_cost_minor or 0)


def add_fifo_batch(batches, quantity_added, unit_cost_minor, timestamp=None, batch_id=None):
    """Add a new stock arrival batch to the variant's batch list."""
    current = normalize_batches(batches)
    if quantity_added <= 0:
        return current

    created_iso = (
        timestamp.isoformat()
        if isinstance(timestamp, datetime)
        else str(timestamp or datetime.now(timezone.utc).isoformat())
    )

    new_batch = {
        "batchId": batch_id or f"batch_{int(datetime.now(timezone.utc).timestamp() * 1000)}",
        "quantity": int(quantity_added),
        "initialQuantity": int(quantity_added),
        "unitCostMinor": int(unit_cost_minor or 0),
        "createdAt": created_iso,
    }
    current.append(new_batch)
    return current


def consume_fifo_batches(batches, quantity_to_consume, default_unit_cost_minor=0):
    """
    Consume items from FIFO batches in order of arrival.
    
    Returns:
        tuple of (
            updated_batches: list of remaining batches with positive quantity,
            total_cost_minor: total cost for the consumed units,
            weighted_unit_cost_minor: average unit cost for this sale,
            active_unit_cost_minor: unit cost of next available batch
        )
    """
    qty_needed = int(quantity_to_consume)
    if qty_needed <= 0:
        norm = normalize_batches(batches)
        active_cost = get_active_unit_cost(norm, default_unit_cost_minor)
        return norm, 0, active_cost, active_cost

    available_batches = normalize_batches(batches, fallback_quantity=qty_needed, fallback_cost_minor=default_unit_cost_minor)
    total_cost_minor = 0
    remaining_needed = qty_needed

    for batch in available_batches:
        if remaining_needed <= 0:
            break
        b_qty = batch["quantity"]
        b_cost = batch["unitCostMinor"]
        taken = min(b_qty, remaining_needed)
        batch["quantity"] = b_qty - taken
        total_cost_minor += taken * b_cost
        remaining_needed -= taken

    # If oversold beyond recorded batches, cost remaining at the latest known cost
    if remaining_needed > 0:
        fallback_cost = (
            available_batches[-1]["unitCostMinor"]
            if available_batches
            else int(default_unit_cost_minor or 0)
        )
        total_cost_minor += remaining_needed * fallback_cost

    remaining_batches = [b for b in available_batches if b["quantity"] > 0]
    weighted_unit_cost_minor = (
        total_cost_minor // qty_needed if qty_needed > 0 else int(default_unit_cost_minor or 0)
    )
    active_unit_cost_minor = get_active_unit_cost(remaining_batches, default_unit_cost_minor)

    return remaining_batches, total_cost_minor, weighted_unit_cost_minor, active_unit_cost_minor

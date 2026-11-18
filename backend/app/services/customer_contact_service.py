"""Project order contacts without disclosing profiles matched by unverified phone numbers."""


def is_legacy_guest_order(order):
    # Old guest orders can contain copied profile details with no proof of their source.
    created_by = str(order.get("createdBy") or "")
    return (
        created_by.startswith("public-chat:")
        or (not created_by and order.get("source") == "chatbot")
    ) and order.get("customerContactSource") != "checkout"


def customer_order_contact(order):
    # Only contact fields with a known source belong in customer-facing receipts and history.
    legacy_guest = is_legacy_guest_order(order)
    snapshot = {} if legacy_guest else order.get("customerSnapshot") or {}
    contact = {
        field: snapshot.get(field, "")
        for field in ("name", "normalizedPhone", "email", "secondaryPhoneNumber")
    }
    if not legacy_guest:
        contact["name"] = contact["name"] or order.get("customerName", "")
        contact["email"] = contact["email"] or snapshot.get("emailAddress") or order.get("customerEmail", "")
    return contact, {} if legacy_guest else order.get("deliveryAddress") or {}

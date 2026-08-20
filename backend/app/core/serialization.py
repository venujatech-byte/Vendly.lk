from datetime import date, datetime


def serialize_value(value):
    """Convert Firestore values into JSON-compatible response values."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, list):
        return [serialize_value(item) for item in value]

    if isinstance(value, dict):
        return {key: serialize_value(item) for key, item in value.items()}

    return value


def serialize_snapshot(snapshot):
    return {
        "id": snapshot.id,
        **serialize_value(snapshot.to_dict()),
    }

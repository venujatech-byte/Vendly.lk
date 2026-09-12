from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore, db as rtdb


def initialize_firebase(settings):
    """Initialize the default Firebase Admin application exactly once."""
    try:
        return firebase_admin.get_app()
    except ValueError:
        pass

    options = {}

    if settings.firebase_project_id:
        options["projectId"] = settings.firebase_project_id

    if settings.firebase_storage_bucket:
        options["storageBucket"] = settings.firebase_storage_bucket

    if settings.firebase_database_url:
        options["databaseURL"] = settings.firebase_database_url
    elif settings.firebase_project_id:
        options["databaseURL"] = f"https://{settings.firebase_project_id}-default-rtdb.asia-southeast1.firebasedatabase.app"

    if settings.firebase_service_account_path:
        credential_path = Path(settings.firebase_service_account_path).expanduser().resolve()

        if not credential_path.is_file():
            raise RuntimeError(
                "FIREBASE_SERVICE_ACCOUNT_PATH does not point to an existing file.",
            )

        credential = credentials.Certificate(str(credential_path))
        return firebase_admin.initialize_app(credential, options)

    return firebase_admin.initialize_app(options=options)


def get_firestore_client():
    """Return the Firestore Admin client for repository and service code."""
    return firestore.client()


def get_rtdb_reference(path=""):
    """Return a Realtime Database reference for real-time chat messages."""
    try:
        if not firebase_admin._apps:
            return None
        return rtdb.reference(path)
    except Exception:
        return None

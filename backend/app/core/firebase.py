from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore


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

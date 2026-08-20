import os
from dataclasses import dataclass

from dotenv import load_dotenv


def parse_boolean(value, default=False):
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_positive_float(value, default):
    try:
        parsed_value = float(value)
    except (TypeError, ValueError):
        return default

    return parsed_value if parsed_value > 0 else default


@dataclass(frozen=True)
class Settings:
    debug: bool
    frontend_origins: list[str]
    firebase_project_id: str | None
    firebase_storage_bucket: str | None
    firebase_service_account_path: str | None
    cloudinary_cloud_name: str | None
    cloudinary_api_key: str | None
    cloudinary_api_secret: str | None
    ai_provider: str
    ai_api_key: str | None
    ai_model: str | None
    ai_api_base_url: str | None
    ai_timeout_seconds: float
    rate_limit_storage_uri: str

    @classmethod
    def from_environment(cls):
        load_dotenv()

        origins = [
            origin.strip()
            for origin in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173").split(",")
            if origin.strip()
        ]

        return cls(
            debug=parse_boolean(os.getenv("FLASK_DEBUG"), default=False),
            frontend_origins=origins,
            firebase_project_id=os.getenv("FIREBASE_PROJECT_ID") or None,
            firebase_storage_bucket=os.getenv("FIREBASE_STORAGE_BUCKET") or None,
            firebase_service_account_path=(
                os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH") or None
            ),
            cloudinary_cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME") or None,
            cloudinary_api_key=os.getenv("CLOUDINARY_API_KEY") or None,
            cloudinary_api_secret=os.getenv("CLOUDINARY_API_SECRET") or None,
            ai_provider=os.getenv("AI_PROVIDER", "none").strip().lower(),
            ai_api_key=os.getenv("AI_API_KEY") or None,
            ai_model=os.getenv("AI_MODEL") or None,
            ai_api_base_url=os.getenv("AI_API_BASE_URL") or None,
            ai_timeout_seconds=parse_positive_float(
                os.getenv("AI_TIMEOUT_SECONDS"),
                15.0,
            ),
            rate_limit_storage_uri=(
                os.getenv("RATE_LIMIT_STORAGE_URI", "memory://").strip()
                or "memory://"
            ),
        )

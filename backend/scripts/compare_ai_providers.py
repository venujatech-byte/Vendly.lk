"""Try the same storefront questions on every configured AI provider.

Choosing between providers on their marketing pages is guesswork: what matters
here is whether a Sinhala question comes back in Sinhala, whether a comparison
names a real product, and how long a customer waits. This asks all of them the
same things and prints the answers side by side.

    python scripts/compare_ai_providers.py

Reads keys from the backend .env. A provider with no key is skipped rather than
reported as broken. Nothing is written and no configuration is changed - it
builds its own settings per provider, so the running app is untouched.
"""

import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.ai_service import (  # noqa: E402
    PROVIDER_PROFILES,
    catalogue_prompt,
    generate_openai_compatible_answer,
    provider_credentials,
)

SINHALA = re.compile(r"[඀-෿]")
TAMIL = re.compile(r"[஀-௿]")

PRODUCTS = [
    {
        "name": "T800 Ultra Smart Watch",
        "categoryName": "Smart watch",
        "description": (
            "Budget smartwatch, 1.99 inch touchscreen, Bluetooth calling with "
            "built-in microphone and speaker, fitness tracking, music control."
        ),
        "sellingPriceMinor": 130000,
        "warrantyPeriodMonths": 6,
        "availableStock": 48,
    },
    {
        "name": "T900 Ultra Smart Watch",
        "categoryName": "Smart watch",
        "description": (
            "2.09 inch touchscreen, Bluetooth calling, health monitoring, "
            "sports tracking, wireless charging."
        ),
        "sellingPriceMinor": 130000,
        "warrantyPeriodMonths": 6,
        "availableStock": 40,
    },
    {
        "name": "Zeblace Gts 3 Smart Watch",
        "categoryName": "Smart watch",
        "description": "AMOLED display, 30 day battery, heart rate monitor.",
        "sellingPriceMinor": 500000,
        "warrantyPeriodMonths": 12,
        "availableStock": 40,
    },
]

QUESTIONS = [
    ("comparison", "en", "which of these has the longest battery?"),
    ("recommendation", "en", "best one from these"),
    ("sinhala", "si", "me hatharen honda mokakda"),
]


def read_env():
    """The backend .env as a plain mapping, without importing the app."""
    values = {}
    path = Path(__file__).resolve().parents[1] / ".env"

    if not path.exists():
        return values

    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()

    return values


def settings_for(provider, env):
    """Config for one provider, using whichever key in .env belongs to it."""
    key = ""

    for prefix in ("AI_", "AI_FALLBACK_"):
        if env.get(f"{prefix}PROVIDER") == provider and env.get(f"{prefix}API_KEY"):
            key = env[f"{prefix}API_KEY"]
            break

    model = ""

    for prefix in ("AI_", "AI_FALLBACK_"):
        if env.get(f"{prefix}PROVIDER") == provider:
            model = env.get(f"{prefix}MODEL", "")
            break

    return {
        "AI_PROVIDER": provider,
        "AI_API_KEY": key,
        "AI_MODEL": model,
        "AI_FAST_MODEL": "",
        "AI_API_BASE_URL": "",
        "AI_TIMEOUT_SECONDS": None,
    }


def script(text):
    if TAMIL.search(text):
        return "Tamil"

    if SINHALA.search(text):
        return "Sinhala"

    return "Latin"


def main():
    env = read_env()

    for provider in sorted(PROVIDER_PROFILES):
        if provider == "openai-compatible":
            continue

        settings = settings_for(provider, env)
        resolved = provider_credentials(settings)

        print(f"\n{'=' * 68}\n{provider.upper()}  {resolved['model'] or '(no model set)'}")

        if not resolved["api_key"]:
            print("  skipped - no key for this provider in .env")
            continue

        if not resolved["model"]:
            print("  skipped - set AI_MODEL for this provider to try it")
            continue

        for label, language, question in QUESTIONS:
            prompt = catalogue_prompt(question, PRODUCTS, language)
            start = time.monotonic()

            try:
                answer = generate_openai_compatible_answer(
                    prompt,
                    provider,
                    settings,
                    max_tokens=1200,
                    credentials=resolved,
                )
                elapsed = time.monotonic() - start
                text = " ".join((answer or "").split())
                print(f"\n  {label} ({elapsed:.1f}s, {script(text)})")
                print(f"    {text[:200]}")
            except Exception as error:  # noqa: BLE001 - report, never raise
                print(f"\n  {label} FAILED after {time.monotonic() - start:.1f}s")
                print(f"    {type(error).__name__}: {str(error)[:140]}")


if __name__ == "__main__":
    main()

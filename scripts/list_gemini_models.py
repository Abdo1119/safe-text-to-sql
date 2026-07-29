"""List the Gemini models the configured key can call. Never prints the key.

Google keeps retired identifiers visible in the models listing but refuses to serve
them to new projects, so listing alone is not proof that a model works. This script
also probes the configured model with one minimal request and reports the outcome.
"""

from __future__ import annotations

from pathlib import Path

from google import genai
from google.genai import errors

from safe_text_to_sql.bootstrap import load_runtime_settings
from safe_text_to_sql.config import ConfigError


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    try:
        settings = load_runtime_settings(project_root=project_root)
    except ConfigError as exc:
        raise SystemExit(f"Configuration error: {exc}") from exc
    if settings.gemini_api_key is None:
        raise SystemExit("GEMINI_API_KEY is not set. Add it to .env or Streamlit Secrets.")

    client = genai.Client(api_key=settings.gemini_api_key.get_secret_value())

    try:
        names = sorted(
            model.name or ""
            for model in client.models.list()
            if "generateContent" in (model.supported_actions or ())
        )
    except errors.APIError as exc:
        raise SystemExit(f"Could not list models (HTTP {exc.code}).") from exc

    print(f"Models advertising generateContent for this key ({len(names)}):")
    for name in names:
        print(f"  {name}")

    print(f"\nProbing configured GEMINI_MODEL={settings.gemini_model}")
    try:
        client.models.generate_content(
            model=settings.gemini_model,
            contents="Reply with the single word OK.",
        )
    except errors.APIError as exc:
        print(f"  NOT CALLABLE (HTTP {exc.code}).")
        if exc.code == 404:
            print("  This identifier is retired for new projects. Choose another model above.")
        raise SystemExit(1) from exc
    print("  CALLABLE.")


if __name__ == "__main__":
    main()

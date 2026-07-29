"""Run one opt-in Gemini smoke test and print sanitized status fields only."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from time import perf_counter
from typing import Any

from safe_text_to_sql.bootstrap import build_components, load_runtime_settings
from safe_text_to_sql.config import ConfigError, LLMProviderMode
from safe_text_to_sql.llm.gemini import ProviderError
from safe_text_to_sql.service import ServiceError


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    started = perf_counter()
    status: dict[str, Any] = {
        "success": False,
        "selected_model": None,
        "sanitized_error_category": None,
        "sanitized_error_message": None,
        "elapsed_seconds": None,
        "valid_sql_produced": False,
        "validation_passed": False,
        "execution_succeeded": False,
        "answer_generated": False,
    }

    try:
        settings = load_runtime_settings(project_root=project_root)
        status["selected_model"] = settings.gemini_model
        if settings.llm_provider is not LLMProviderMode.GEMINI:
            status["sanitized_error_category"] = "gemini_not_selected"
        elif settings.gemini_api_key is None:
            status["sanitized_error_category"] = "configuration"
        else:
            components = build_components(settings, project_root=project_root)
            result = asyncio.run(components.service.ask("How many tracks are in the store?"))
            status.update(
                {
                    "success": True,
                    "valid_sql_produced": bool(result.candidate.sql),
                    "validation_passed": bool(result.validated_query.sql),
                    "execution_succeeded": True,
                    "answer_generated": bool(result.answer.answer.strip()),
                    "returned_rows": len(result.query_result.rows),
                    "repair_attempts": result.repair_attempts,
                }
            )
    except ConfigError as exc:
        status["sanitized_error_category"] = "configuration"
        status["sanitized_error_message"] = str(exc)
    except ServiceError as exc:
        cause = exc.__cause__
        # ProviderError messages are fixed, author-written strings that exclude prompts,
        # credentials, rows, and raw provider responses. Surfacing the message is what
        # makes an ambiguous category such as "configuration" actionable.
        if isinstance(cause, ProviderError):
            status["sanitized_error_category"] = cause.code.value
            status["sanitized_error_message"] = str(cause)
        else:
            status["sanitized_error_category"] = exc.code.value
            status["sanitized_error_message"] = str(exc)
    except Exception:
        status["sanitized_error_category"] = "internal"
    finally:
        status["elapsed_seconds"] = round(perf_counter() - started, 3)

    print(json.dumps(status, sort_keys=True))
    if not status["success"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

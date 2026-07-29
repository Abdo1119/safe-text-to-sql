"""Streamlit entry point for the Safe Text-to-SQL workbench."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


def ensure_source_path(project_root: Path = PROJECT_ROOT) -> None:
    """Import the application package from this checkout, not a cached install.

    Streamlit Community Cloud executes this file from the repository mount but resolves
    imports from an environment it reuses between deploys. A push that changes `src/`
    without changing the dependency set otherwise keeps serving the previously
    installed package, which fails as a missing attribute rather than as a clear error.
    """

    source_root = project_root / "src"
    if not source_root.is_dir():
        return
    entry = str(source_root)
    if sys.path and sys.path[0] == entry:
        return
    while entry in sys.path:
        sys.path.remove(entry)
    sys.path.insert(0, entry)


ensure_source_path()

# Imported after the path shim so the checkout's package wins over a cached install.
import streamlit as st  # noqa: E402
from streamlit.errors import StreamlitSecretNotFoundError  # noqa: E402

from safe_text_to_sql.bootstrap import (  # noqa: E402
    build_components,
    load_runtime_settings,
    provision_database,
)
from safe_text_to_sql.config import ConfigError  # noqa: E402
from safe_text_to_sql.database.initializer import (  # noqa: E402
    DatabaseInitializationError,
    DatabaseProvisionState,
)
from safe_text_to_sql.ui import render_app  # noqa: E402


def main() -> None:
    st.set_page_config(
        page_title="Safe Text-to-SQL",
        page_icon="◫",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    project_root = PROJECT_ROOT
    try:
        secrets = st.secrets.to_dict()
    except StreamlitSecretNotFoundError:
        secrets = {}

    try:
        settings = load_runtime_settings(
            project_root=project_root,
            streamlit_secrets=secrets,
        )
    except ConfigError as exc:
        st.error(str(exc))
        st.info(
            "Use fake mode without a cloud key, or configure Gemini through local "
            "environment variables or Streamlit Secrets."
        )
        st.stop()
    except Exception:
        st.error("The application could not start with the current local configuration.")
        st.stop()

    try:
        with st.spinner("Initializing the synthetic demo database…"):
            provisioning = provision_database(settings, project_root=project_root)
    except DatabaseInitializationError as exc:
        # DatabaseInitializationError messages are fixed, author-written strings with no
        # path or driver text, so naming the failing stage stays safe and is the only
        # way to diagnose this on a host whose logs are not reachable.
        st.error(
            "The synthetic demo database could not be prepared, so queries are "
            f"disabled. No data was modified. Reason: {exc}"
        )
        st.stop()
    except Exception:
        st.error("The synthetic demo database could not be prepared.")
        st.stop()

    try:
        components = build_components(
            settings,
            project_root=project_root,
            database_path=provisioning.path,
        )
    except Exception:
        st.error("The application could not start with the current configuration.")
        st.stop()

    render_app(
        settings,
        components,
        database_created=provisioning.state is DatabaseProvisionState.CREATED,
        used_fallback_location=provisioning.used_fallback_location,
    )


if __name__ == "__main__":
    main()

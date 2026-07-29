# Deployment

## Streamlit Community Cloud

1. Fork or connect the public GitHub repository.
2. Select `app.py` as the entry point.
3. Use Python 3.12.
4. Leave secrets unset for the deterministic public fake demo.
5. To enable Gemini, add these values in Streamlit's encrypted Secrets settings:

   ```toml
   LLM_PROVIDER = "gemini"
   GEMINI_API_KEY = "configured_in_streamlit_cloud"
   GEMINI_MODEL = "gemini-3.6-flash"
   ```

Do not create or commit `.streamlit/secrets.toml`. The bootstrap layer accepts only
known configuration keys and environment variables take precedence.

## Container platforms

Build the provided Dockerfile, publish the image to a trusted registry, and expose the
runtime `PORT` (default `8501`). Inject provider credentials only through the
platform's secret manager. Preserve the non-root user, health check, and read-only
filesystem where supported.

## Production readiness

This repository demonstrates production-oriented boundaries; it is not a claim of a
production deployment. Before serving private data, add authentication, per-user
authorization, rate limiting, centralized redacted logs, monitoring, provider and data
governance, abuse controls, and a database role with the minimum possible privileges.

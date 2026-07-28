# Docker

Build and run the default offline application:

```bash
docker compose up --build
```

The image:

- uses Python 3.12 slim;
- installs exact versions from `requirements.lock`;
- generates the synthetic database during the build;
- runs as an unprivileged user;
- starts in fake mode;
- binds Streamlit to `0.0.0.0`;
- includes a health check;
- does not copy `.env`, tests, private migration evidence, or legacy source.

To use Gemini, inject `LLM_PROVIDER`, `GEMINI_API_KEY`, and optionally `GEMINI_MODEL`
through the deployment platform's secret manager. Do not add the key to the Dockerfile,
Compose file, image, or build arguments.

The Compose service uses a read-only root filesystem, a temporary `/tmp`, and
`no-new-privileges`. The generated SQLite database is already part of the image and is
opened read-only by the application.

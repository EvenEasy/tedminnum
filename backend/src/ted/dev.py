"""Explicit loopback-only native development entrypoint. Never migrates or seeds."""

import argparse
import os

import uvicorn

from ted.infrastructure.config import Settings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run native Tedminnum development using existing DATABASE_URL; leave .env unchanged"
    )
    parser.add_argument(
        "--frontend-origin",
        action="append",
        help="Exact allowed frontend origin; repeat to configure multiple origins",
    )
    parser.add_argument(
        "--reload", action="store_true", help="Restart the backend on source changes"
    )
    args = parser.parse_args()
    origins = args.frontend_origin or [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000",
    ]
    config = Settings(
        app_env="development",
        app_origin="http://localhost:8000",
        dev_origins=origins,
        secure_cookies=False,
    )
    # Explicit development command: overrides apply to this process (and reload child) only.
    # DATABASE_URL is deliberately untouched and is resolved from existing config/environment.
    os.environ.update(
        APP_ENV="development",
        APP_ORIGIN=config.app_origin,
        DEV_ORIGINS=",".join(config.dev_origins),
        SECURE_COOKIES="false",
    )
    print(
        "Native development on loopback; allowed origins: "
        + ", ".join(sorted(config.allowed_origins))
    )
    uvicorn.run(
        "ted.presentation.api:app",
        host="127.0.0.1",
        port=8000,
        reload=args.reload,
        proxy_headers=False,
    )


if __name__ == "__main__":
    main()

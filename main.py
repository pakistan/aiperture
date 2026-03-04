"""Aperture server entry point."""

import os

import uvicorn

import aiperture.config
from aiperture.api import create_app

app = create_app()

if __name__ == "__main__":
    settings = aiperture.config.settings
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=os.environ.get("AIPERTURE_DEBUG", "").lower() in ("1", "true"),
    )

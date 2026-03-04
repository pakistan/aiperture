"""Configuration API — GET /config and PATCH /config for tunable settings."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import aiperture.config

router = APIRouter()


class ConfigPatchRequest(BaseModel):
    settings: dict[str, Any]


@router.get("")
def get_config():
    """Return current tunable settings and their descriptions."""
    return {
        "settings": aiperture.config.get_tunable_config(),
        "descriptions": dict(aiperture.config.Settings.TUNABLE_DESCRIPTIONS),
    }


@router.patch("")
def patch_config(body: ConfigPatchRequest):
    """Update tunable settings at runtime. Persists to .aiperture.env."""
    try:
        aiperture.config.update_settings(body.settings)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "updated": True,
        "settings": aiperture.config.get_tunable_config(),
    }

"""Permission engine — deterministic RBAC + ReBAC + learning + intelligence."""

from aiperture.permissions.challenge import create_challenge, verify_challenge
from aiperture.permissions.crowd import compute_auto_approve_distance, compute_trend, get_org_signal
from aiperture.permissions.engine import PermissionEngine
from aiperture.permissions.explainer import explain_action
from aiperture.permissions.intelligence import IntelligenceEngine
from aiperture.permissions.learning import PermissionLearner, PermissionPattern
from aiperture.permissions.presets import (
    PRESET_DEVELOPER,
    PRESET_MINIMAL,
    PRESET_READONLY,
    PRESETS,
    PresetDecision,
    apply_preset,
    get_preset,
    get_preset_names,
)
from aiperture.permissions.resource import extract_resource
from aiperture.permissions.risk import classify_risk
from aiperture.permissions.scope_normalize import normalize_scope
from aiperture.permissions.similarity import find_similar_patterns

__all__ = [
    "IntelligenceEngine",
    "PRESET_DEVELOPER",
    "PRESET_MINIMAL",
    "PRESET_READONLY",
    "PRESETS",
    "PermissionEngine",
    "PermissionLearner",
    "PermissionPattern",
    "PresetDecision",
    "apply_preset",
    "classify_risk",
    "compute_auto_approve_distance",
    "compute_trend",
    "create_challenge",
    "explain_action",
    "extract_resource",
    "find_similar_patterns",
    "get_org_signal",
    "get_preset",
    "get_preset_names",
    "normalize_scope",
    "verify_challenge",
]

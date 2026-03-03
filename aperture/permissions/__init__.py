"""Permission engine — deterministic RBAC + ReBAC + learning + intelligence."""

from aperture.permissions.challenge import create_challenge, verify_challenge
from aperture.permissions.crowd import compute_auto_approve_distance, compute_trend, get_org_signal
from aperture.permissions.engine import PermissionEngine
from aperture.permissions.explainer import explain_action
from aperture.permissions.intelligence import IntelligenceEngine
from aperture.permissions.learning import PermissionLearner, PermissionPattern
from aperture.permissions.presets import (
    PRESET_DEVELOPER,
    PRESET_MINIMAL,
    PRESET_READONLY,
    PRESETS,
    PresetDecision,
    apply_preset,
    get_preset,
    get_preset_names,
)
from aperture.permissions.resource import extract_resource
from aperture.permissions.risk import classify_risk
from aperture.permissions.scope_normalize import normalize_scope
from aperture.permissions.similarity import find_similar_patterns

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

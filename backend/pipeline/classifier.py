"""Layer 4 — Fingerprint Classifier (rule-based, no LLM needed)."""

FINGERPRINT_RULES = {
    "GHOST":    {"drift_min": 0.8,  "drift_max": 1.0},
    "INVERT":   {"drift_min": 0.6,  "drift_max": 0.85},
    "HOLLOW":   {"drift_min": 0.5,  "drift_max": 0.75},
    "ORPHAN":   {"drift_min": 0.4,  "drift_max": 0.7},
    "FRAGMENT": {"drift_min": 0.3,  "drift_max": 0.55},
}


def classify(drift_score: float, match_result: dict) -> str:
    """Map drift score + activation pattern to exactly one fingerprint."""
    wrong = match_result.get("wrong_claims", [])
    activated = match_result.get("activated_nodes", [])
    skipped = match_result.get("skipped_nodes", [])
    total_nodes = len(activated) + len(skipped) or 1

    has_wrong_claims = len(wrong) > 0
    has_inverted = any("inverted" in w for w in wrong)
    activation_ratio = len(activated) / total_nodes

    if has_wrong_claims and has_inverted and drift_score >= 0.6:
        return "INVERT"

    if drift_score >= 0.8 and has_wrong_claims:
        return "GHOST"

    if drift_score >= 0.5 and activation_ratio > 0.5 and not has_wrong_claims:
        return "HOLLOW"

    if drift_score >= 0.4 and len(skipped) == 1:
        return "ORPHAN"

    if drift_score >= 0.3 and 0.3 < activation_ratio < 0.8:
        return "FRAGMENT"

    for fp, rules in FINGERPRINT_RULES.items():
        if rules["drift_min"] <= drift_score <= rules["drift_max"]:
            return fp

    if drift_score < 0.3:
        return "FRAGMENT"
    return "GHOST"

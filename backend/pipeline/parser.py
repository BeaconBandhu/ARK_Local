"""Layer 1 — Surface Parser: tokenize and extract claims from raw student answer."""

import re

FILLER_WORDS = {
    "um", "uh", "like", "you know", "basically", "actually", "i mean",
    "sort of", "kind of", "maybe", "perhaps", "i think", "i believe",
    "right", "okay", "ok", "so", "well", "just", "very", "really",
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "it", "its", "this", "that", "these", "those"
}

SENTENCE_SPLIT = re.compile(r'[.!?;,]+')


def parse(raw_text: str) -> list[str]:
    """Extract meaningful claim strings from raw student answer."""
    if not raw_text or not raw_text.strip():
        return []

    text = raw_text.lower().strip()
    text = re.sub(r"[\"'`]", "", text)
    text = re.sub(r"\s+", " ", text)

    segments = [s.strip() for s in SENTENCE_SPLIT.split(text) if s.strip()]

    claims = []
    for seg in segments:
        tokens = seg.split()
        meaningful = [t for t in tokens if t not in FILLER_WORDS and len(t) > 2]
        if len(meaningful) >= 2:
            claims.append(" ".join(meaningful))

    return claims if claims else [text]

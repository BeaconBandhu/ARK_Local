"""Layer 3 — Temporal Misunderstanding Decay Scorer."""

import json
import os

_GRAPH_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "science_grade6.json")
_graph: dict = {}


def _load():
    global _graph
    if not _graph:
        with open(_GRAPH_PATH, encoding="utf-8") as f:
            _graph = json.load(f)


def calculate_drift(match_result: dict, topic: str) -> float:
    """
    drift = (skipped_critical_nodes * 0.4 + wrong_claims * 0.6) / total_concept_weight
    Returns float 0.0–1.0
    """
    _load()
    topic_data = _graph.get(topic.lower().replace(" ", "_"), {})
    node_weights: dict[str, float] = topic_data.get("node_weights", {})

    skipped = match_result.get("skipped_nodes", [])
    wrong = match_result.get("wrong_claims", [])
    activated = match_result.get("activated_nodes", [])

    skipped_weight = sum(node_weights.get(n, 0.15) for n in skipped)
    activated_weight = sum(node_weights.get(n, 0.15) for n in activated)
    total_weight = skipped_weight + activated_weight or 1.0

    wrong_count = len(wrong)
    skipped_count = len(skipped)

    raw_drift = (skipped_count * 0.4 + wrong_count * 0.6) / max(total_weight * 10, 1)
    raw_drift += (wrong_count * 0.1)

    drift = min(max(round(raw_drift, 2), 0.0), 1.0)
    return drift

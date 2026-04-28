"""Layer 2 — H-6 Concept Hexgraph Matcher."""

import json
import os
from typing import Any

_GRAPH_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "science_grade6.json")
_graph: dict[str, Any] = {}


def load_graph() -> None:
    global _graph
    with open(_GRAPH_PATH, encoding="utf-8") as f:
        _graph = json.load(f)


def get_topic(topic: str) -> dict | None:
    return _graph.get(topic.lower().replace(" ", "_"))


def match(claims: list[str], topic: str) -> dict:
    """Compare claims against H-6 graph, return activated/skipped nodes."""
    topic_data = get_topic(topic)
    if not topic_data:
        return {"activated_nodes": [], "skipped_nodes": [], "prerequisite_gaps": [], "wrong_claims": []}

    node_keywords: dict[str, list[str]] = topic_data.get("node_keywords", {})
    prerequisites: list[str] = topic_data.get("prerequisites", [])
    topic_keywords: list[str] = topic_data.get("keywords", [])

    claim_text = " ".join(claims).lower()

    activated: list[str] = []
    skipped: list[str] = []

    for node in prerequisites:
        kws = node_keywords.get(node, [node.replace("_", " ")])
        if any(kw in claim_text for kw in kws):
            activated.append(node)
        else:
            skipped.append(node)

    wrong_claims = _detect_wrong_claims(claim_text, topic, topic_data)

    return {
        "activated_nodes": activated,
        "skipped_nodes": skipped,
        "prerequisite_gaps": skipped[:3],
        "wrong_claims": wrong_claims,
        "topic_keywords_found": [kw for kw in topic_keywords if kw in claim_text],
    }


def _detect_wrong_claims(text: str, topic: str, topic_data: dict) -> list[str]:
    wrong = []
    if topic == "photosynthesis":
        if ("release co2" in text or "release carbon" in text or "give out co2" in text):
            wrong.append("inverted_gas_exchange")
        if ("absorb oxygen" in text or "take in oxygen" in text or "breathe in o2" in text):
            wrong.append("inverted_o2_absorption")
        if ("plants eat" in text or "plants consume" in text):
            wrong.append("plants_are_consumers")
    elif topic == "water_cycle":
        if ("rain causes evaporation" in text or "rain makes clouds" in text):
            wrong.append("inverted_cycle_order")
        if ("clouds are smoke" in text or "clouds are dust" in text):
            wrong.append("wrong_cloud_composition")
    elif topic == "food_chain":
        if ("plants eat animals" in text or "carnivore eats plants" in text):
            wrong.append("inverted_food_direction")
        if ("energy increases" in text or "more energy higher" in text):
            wrong.append("wrong_energy_direction")
    return wrong

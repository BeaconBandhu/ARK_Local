"""Layer 5 — Remediation Engine: Ollama-first, cache fallback."""

import json
import os
import logging
from typing import Any

logger = logging.getLogger(__name__)

_CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "cache.json")
_cache: dict[str, Any] = {}


def _load_cache():
    global _cache
    if not _cache and os.path.exists(_CACHE_PATH):
        with open(_CACHE_PATH, encoding="utf-8") as f:
            _cache = json.load(f)


REMEDIATION_PROMPT = """You are ECHO, a comprehension analysis system for low-resource classrooms in rural India.

Topic: {topic}
Correct explanation: {correct_model}
Student's answer: {student_answer}
Fingerprint type: {fingerprint_type}
Student's language: {language}

Rules:
- Age 12 level language only, no scientific jargon
- Story analogy must use farming, cooking, breathing, or daily village life — nothing urban or western
- Be warm and encouraging, never say the student is wrong bluntly
- If language is not English, write story_fix and follow_up_question in that language (keep what_is_wrong in English for teacher view)

Return ONLY valid JSON, no preamble, no markdown:
{{
  "what_is_wrong": "one sentence, plain language, English",
  "story_fix": "two sentences using a relatable analogy",
  "follow_up_question": "one Socratic question to make them self-correct"
}}"""


async def get_remediation(
    topic: str,
    fingerprint: str,
    student_answer: str,
    language: str,
    ollama_service=None,
    correct_model: str = "",
) -> dict:
    _load_cache()

    cache_key = f"{topic}_{fingerprint}"
    if language == "english" and cache_key in _cache:
        return _cache[cache_key]

    if ollama_service:
        try:
            prompt = REMEDIATION_PROMPT.format(
                topic=topic,
                correct_model=correct_model,
                student_answer=student_answer,
                fingerprint_type=fingerprint,
                language=language,
            )
            raw = await ollama_service.generate(prompt)
            parsed = json.loads(raw)
            if all(k in parsed for k in ("what_is_wrong", "story_fix", "follow_up_question")):
                return parsed
        except Exception as e:
            logger.warning("Ollama remediation failed: %s — using cache fallback", e)

    if cache_key in _cache:
        return _cache[cache_key]

    return {
        "what_is_wrong": "There is a gap in your understanding of this concept.",
        "story_fix": "Think about this topic step by step, like following a recipe from the beginning.",
        "follow_up_question": "Can you explain this concept in your own words, starting from the very first step?",
    }

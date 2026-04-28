"""Ollama HTTP client — text generation and vision (image) analysis."""

import base64
import json
import logging
import os
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
TEXT_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-vl:7b")
VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "qwen2.5-vl:7b")
TIMEOUT = 120.0


class OllamaService:
    def __init__(self):
        self.client = httpx.AsyncClient(base_url=OLLAMA_BASE, timeout=TIMEOUT)

    async def generate(self, prompt: str, model: str | None = None) -> str:
        model = model or TEXT_MODEL
        payload = {"model": model, "prompt": prompt, "stream": False}
        resp = await self.client.post("/api/generate", json=payload)
        resp.raise_for_status()
        return resp.json().get("response", "")

    async def generate_with_image(self, prompt: str, image_path: str | None = None, image_bytes: bytes | None = None) -> str:
        if image_path:
            image_bytes = Path(image_path).read_bytes()
        if not image_bytes:
            return await self.generate(prompt)

        b64 = base64.b64encode(image_bytes).decode()
        payload = {
            "model": VISION_MODEL,
            "prompt": prompt,
            "images": [b64],
            "stream": False,
        }
        resp = await self.client.post("/api/generate", json=payload)
        resp.raise_for_status()
        return resp.json().get("response", "")

    async def chat(self, messages: list[dict], model: str | None = None) -> str:
        """Multi-turn chat with Ollama."""
        model = model or TEXT_MODEL
        payload = {"model": model, "messages": messages, "stream": False}
        resp = await self.client.post("/api/chat", json=payload)
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "")

    async def is_available(self) -> bool:
        try:
            resp = await self.client.get("/api/tags", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        try:
            resp = await self.client.get("/api/tags")
            resp.raise_for_status()
            return [m["name"] for m in resp.json().get("models", [])]
        except Exception:
            return []

    async def close(self):
        await self.client.aclose()

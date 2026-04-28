"""Obsidian Vault service — indexes markdown notes and images for RAG."""

import asyncio
import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

VAULT_PATH = os.getenv("OBSIDIAN_VAULT_PATH", "")
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}


class ObsidianService:
    def __init__(self, mongo_service=None, redis_service=None, ollama_service=None):
        self.vault = Path(VAULT_PATH) if VAULT_PATH else None
        self.mongo = mongo_service
        self.redis = redis_service
        self.ollama = ollama_service

    def is_configured(self) -> bool:
        return self.vault is not None and self.vault.exists()

    async def index_vault(self) -> int:
        """Walk vault directory, index all .md files + linked images."""
        if not self.is_configured():
            logger.warning("Obsidian vault not configured or not found: %s", VAULT_PATH)
            return 0

        count = 0
        for md_file in self.vault.rglob("*.md"):
            try:
                text = md_file.read_text(encoding="utf-8")
                images = self._extract_image_paths(text, md_file.parent)
                if self.mongo:
                    await self.mongo.upsert_vault_file(str(md_file), text, images)
                count += 1
            except Exception as e:
                logger.warning("Failed to index %s: %s", md_file, e)

        logger.info("Indexed %d vault files", count)
        return count

    def _extract_image_paths(self, text: str, base_dir: Path) -> list[str]:
        """Extract image paths from Obsidian markdown (wikilinks + standard)."""
        paths = []
        wikilink_images = re.findall(r'!\[\[([^\]]+)\]\]', text)
        for name in wikilink_images:
            for ext in IMAGE_EXTS:
                candidate = base_dir / name if name.endswith(tuple(IMAGE_EXTS)) else base_dir / (name + ext)
                if candidate.exists():
                    paths.append(str(candidate))
                    break

        standard_images = re.findall(r'!\[[^\]]*\]\(([^)]+)\)', text)
        for rel in standard_images:
            candidate = (base_dir / rel).resolve()
            if candidate.exists() and candidate.suffix.lower() in IMAGE_EXTS:
                paths.append(str(candidate))

        return paths

    async def answer_query(self, query: str, image_path: str | None = None) -> str:
        """RAG: retrieve context from vault, then ask Ollama."""
        if not self.ollama:
            return "Ollama is not available."

        context_chunks: list[str] = []

        if self.mongo:
            docs = await self.mongo.search_vault(query, limit=3)
            context_chunks = [d.get("content", "")[:800] for d in docs]

        if self.redis:
            cached = await self.redis.get_vault_chunk(f"query:{hash(query)}")
            if cached:
                return cached

        context = "\n---\n".join(context_chunks) if context_chunks else "No relevant notes found."

        if image_path and Path(image_path).exists():
            prompt = (
                f"You are a teacher assistant. The student has attached an image and asks:\n\n"
                f"Question: {query}\n\n"
                f"Relevant notes from teacher's Obsidian vault:\n{context}\n\n"
                f"Please answer clearly using the notes and the image."
            )
            response = await self.ollama.generate_with_image(prompt, image_path=image_path)
        else:
            prompt = (
                f"You are a helpful teacher assistant with access to the teacher's Obsidian notes.\n\n"
                f"Relevant notes:\n{context}\n\n"
                f"Question: {query}\n\n"
                f"Answer clearly and concisely:"
            )
            response = await self.ollama.generate(prompt)

        if self.redis:
            await self.redis.cache_vault_chunk(f"query:{hash(query)}", response, ttl=300)

        return response

    async def watch_vault(self):
        """Periodically re-index vault to pick up new notes."""
        if not self.is_configured():
            return
        while True:
            await asyncio.sleep(300)
            await self.index_vault()

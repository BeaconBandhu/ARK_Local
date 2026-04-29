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
        self.ollama = ollama_service  # fallback only

    def is_configured(self) -> bool:
        return self.vault is not None and self.vault.exists()

    async def index_vault(self) -> int:
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
        paths = []
        for name in re.findall(r'!\[\[([^\]]+)\]\]', text):
            for ext in IMAGE_EXTS:
                candidate = base_dir / name if name.endswith(tuple(IMAGE_EXTS)) else base_dir / (name + ext)
                if candidate.exists():
                    paths.append(str(candidate))
                    break
        for rel in re.findall(r'!\[[^\]]*\]\(([^)]+)\)', text):
            candidate = (base_dir / rel).resolve()
            if candidate.exists() and candidate.suffix.lower() in IMAGE_EXTS:
                paths.append(str(candidate))
        return paths

    async def answer_query(self, query: str, image_path: str | None = None) -> str:
        """RAG: retrieve context from vault, then generate with Gemini (fallback: Ollama)."""
        context_chunks: list[str] = []

        if self.mongo:
            docs = await self.mongo.search_vault(query, limit=3)
            context_chunks = [d.get("content", "")[:800] for d in docs]

        if self.redis:
            cached = await self.redis.get_vault_chunk(f"query:{hash(query)}")
            if cached:
                return cached

        context = "\n---\n".join(context_chunks) if context_chunks else "No relevant notes found."

        answer = await self._gemini(query, context, image_path)
        if answer is None:
            answer = await self._ollama_fallback(query, context, image_path)
        if answer is None:
            return "Could not generate an answer — check your Gemini API key or start Ollama."

        if self.redis:
            await self.redis.cache_vault_chunk(f"query:{hash(query)}", answer, ttl=300)

        return answer

    async def _gemini(self, query: str, context: str, image_path: str | None) -> str | None:
        key = os.getenv("OPENAI_API_KEY", "")
        if not key:
            return None
        try:
            import base64
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=key)

            if image_path and Path(image_path).exists():
                img_bytes  = Path(image_path).read_bytes()
                img_b64    = base64.standard_b64encode(img_bytes).decode()
                ext        = Path(image_path).suffix.lower().lstrip(".")
                media_map  = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                              "png": "image/png", "webp": "image/webp", "gif": "image/gif"}
                media_type = media_map.get(ext, "image/jpeg")
                content = [
                    {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{img_b64}"}},
                    {"type": "text", "text": (
                        f"You are a teacher assistant with access to the teacher's Obsidian vault notes.\n\n"
                        f"Relevant notes:\n{context}\n\n"
                        f"Question: {query}\n\nAnswer clearly using both the notes and the image."
                    )},
                ]
            else:
                content = (
                    f"You are a helpful teacher assistant with access to the teacher's Obsidian notes.\n\n"
                    f"Relevant notes:\n{context}\n\nQuestion: {query}\n\nAnswer clearly and concisely:"
                )

            resp = await client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=1024,
                messages=[{"role": "user", "content": content}],
            )
            return resp.choices[0].message.content
        except Exception as e:
            logger.warning("OpenAI RAG failed: %s", e)
            return None

    async def _ollama_fallback(self, query: str, context: str, image_path: str | None) -> str | None:
        if not self.ollama:
            return None
        try:
            if image_path and Path(image_path).exists():
                prompt = (
                    f"You are a teacher assistant. Question: {query}\n\n"
                    f"Relevant notes:\n{context}\n\nAnswer using the notes and image."
                )
                return await self.ollama.generate_with_image(prompt, image_path=image_path)
            else:
                prompt = (
                    f"You are a helpful teacher assistant.\n\n"
                    f"Relevant notes:\n{context}\n\nQuestion: {query}\n\nAnswer clearly:"
                )
                return await self.ollama.generate(prompt)
        except Exception as e:
            logger.warning("Ollama RAG fallback failed: %s", e)
            return None

    async def watch_vault(self):
        if not self.is_configured():
            return
        while True:
            await asyncio.sleep(300)
            await self.index_vault()

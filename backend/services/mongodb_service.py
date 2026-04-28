"""MongoDB service — persistent student records and vault index."""

import logging
import os
from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "echo_ark")


class MongoService:
    def __init__(self):
        self.client: AsyncIOMotorClient | None = None
        self.db = None

    async def connect(self):
        self.client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        self.db = self.client[MONGO_DB]
        await self.db.students.create_index("student_id")
        await self.db.students.create_index("timestamp")
        await self.db.vault_index.create_index("file_path")
        logger.info("MongoDB connected: %s / %s", MONGO_URI, MONGO_DB)

    async def close(self):
        if self.client:
            self.client.close()

    async def is_available(self) -> bool:
        try:
            await self.client.admin.command("ping")
            return True
        except Exception:
            return False

    # --- Student results ---

    async def upsert_student_result(self, result: dict) -> None:
        result["synced_at"] = datetime.utcnow().isoformat()
        await self.db.students.replace_one(
            {"student_id": result["student_id"]},
            result,
            upsert=True,
        )

    async def bulk_upsert(self, results: list[dict]) -> int:
        count = 0
        for r in results:
            await self.upsert_student_result(r)
            count += 1
        return count

    async def get_session_results(self, topic: str | None = None) -> list[dict]:
        query = {}
        if topic:
            query["topic"] = topic
        cursor = self.db.students.find(query, {"_id": 0})
        return await cursor.to_list(length=500)

    async def get_student(self, student_id: str) -> dict | None:
        return await self.db.students.find_one({"student_id": student_id}, {"_id": 0})

    async def clear_session(self) -> None:
        await self.db.students.delete_many({})

    # --- Obsidian vault index ---

    async def upsert_vault_file(self, file_path: str, content: str, images: list[str]) -> None:
        await self.db.vault_index.replace_one(
            {"file_path": file_path},
            {"file_path": file_path, "content": content, "images": images, "indexed_at": datetime.utcnow().isoformat()},
            upsert=True,
        )

    async def search_vault(self, query: str, limit: int = 5) -> list[dict]:
        words = query.lower().split()
        regex_parts = "|".join(words[:5])
        cursor = self.db.vault_index.find(
            {"content": {"$regex": regex_parts, "$options": "i"}},
            {"_id": 0, "content": {"$slice": 500}},
        ).limit(limit)
        return await cursor.to_list(length=limit)

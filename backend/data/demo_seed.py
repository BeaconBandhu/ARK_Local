"""Seed demo student data for hackathon presentation."""

import asyncio
import sys
sys.path.insert(0, '..')

import httpx

BASE = "http://localhost:8000"

DEMO_STUDENTS = [
    {"student_id": "S01", "student_name": "Priya R.", "topic": "photosynthesis",
     "answer_text": "Plants absorb sunlight and release CO2 into the air and they take in oxygen"},
    {"student_id": "S02", "student_name": "Arjun M.", "topic": "photosynthesis",
     "answer_text": "Plants make food from sunlight"},
    {"student_id": "S03", "student_name": "Divya G.", "topic": "photosynthesis",
     "answer_text": "Plants use sunlight to combine carbon dioxide from air and water from roots to make glucose and release oxygen through their leaves"},
    {"student_id": "S04", "student_name": "Ravi K.", "topic": "photosynthesis",
     "answer_text": "Sunlight hits the leaves and the plant uses CO2 and water to make glucose but I forget what gas comes out"},
    {"student_id": "S05", "student_name": "Ananya S.", "topic": "photosynthesis",
     "answer_text": "Plants breathe in oxygen like us and breathe out CO2 just like animals do to make energy from the sun"},
    {"student_id": "S06", "student_name": "Karthik B.", "topic": "water_cycle",
     "answer_text": "Water evaporates from lakes and oceans when the sun heats it then it forms clouds and falls as rain"},
    {"student_id": "S07", "student_name": "Meena T.", "topic": "water_cycle",
     "answer_text": "There is evaporation and condensation and precipitation and the rain comes back"},
    {"student_id": "S08", "student_name": "Suresh P.", "topic": "food_chain",
     "answer_text": "Grass is eaten by deer then deer is eaten by tiger and the tiger has most energy because it is at the top"},
    {"student_id": "S09", "student_name": "Lakshmi N.", "topic": "food_chain",
     "answer_text": "Sun gives energy to plants, plants are eaten by herbivores, herbivores by carnivores, decomposers break dead things and return nutrients"},
]


async def seed():
    async with httpx.AsyncClient(base_url=BASE, timeout=30) as client:
        for s in DEMO_STUDENTS:
            try:
                r = await client.post("/analyse", json={**s, "language": "english"})
                print(f"  {s['student_name']}: {r.json().get('fingerprint')} (drift {r.json().get('drift_score')})")
            except Exception as e:
                print(f"  {s['student_name']}: FAILED — {e}")
    print("Seeding complete.")


if __name__ == "__main__":
    asyncio.run(seed())

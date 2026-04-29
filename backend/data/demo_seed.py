"""
Seed 30 demo students into MongoDB for ARK dashboard + student portal demo.
Inserts directly into MongoDB (no Ollama calls needed -- fast).
Run: C:\\Python314\\python.exe demo_seed.py
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URI = "mongodb://localhost:27017"
DB_NAME   = "echo_ark"


# ── REMEDIATION TEXTS ────────────────────────────────────────────────────────
# Pre-written so we don't need Ollama during seeding

REM = {
    "photosynthesis_GHOST": {
        "what_is_wrong": "You believe plants breathe in oxygen and breathe out CO2, just like animals. This is the opposite of what happens.",
        "story_fix": "Plants are food factories, not breathers. The factory takes raw materials (CO2 + water) and uses sunlight as the power source to make its product (glucose) and releases a waste product (oxygen). You breathe that oxygen.",
        "follow_up_question": "If plants breathed in oxygen like us, what would happen at night when there is no sunlight?"
    },
    "photosynthesis_INVERT": {
        "what_is_wrong": "You have the gases reversed. Plants take IN carbon dioxide and release OXYGEN — not the other way around.",
        "story_fix": "Think of it as a trade: the plant borrows CO2 from the air and water from the soil, uses sunlight to combine them into glucose, and pays back the atmosphere with oxygen.",
        "follow_up_question": "If plants released CO2 instead of oxygen, would humans be able to breathe? What would happen to life on Earth?"
    },
    "photosynthesis_HOLLOW": {
        "what_is_wrong": "You named the right parts (sunlight, chlorophyll, glucose) but could not explain how they connect. Naming parts is not the same as understanding the process.",
        "story_fix": "The mechanism is: chlorophyll inside leaf cells captures sunlight energy. That energy splits water molecules. The hydrogen from water combines with CO2 from air to build glucose. Oxygen is released as a byproduct through stomata.",
        "follow_up_question": "If you covered a plant's leaves with black paint, blocking chlorophyll from sunlight, what would happen to glucose production?"
    },
    "photosynthesis_FRAGMENT": {
        "what_is_wrong": "You described part of photosynthesis correctly but missed one or more key steps — either the role of chlorophyll, the source of CO2, or what glucose is used for.",
        "story_fix": "Complete chain: Roots absorb water → Stomata absorb CO2 → Chlorophyll captures sunlight → Energy converts CO2 + H2O → Glucose + O2. Each step depends on the one before.",
        "follow_up_question": "What would happen to a plant that gets sunlight and water but is kept in a CO2-free atmosphere?"
    },
    "photosynthesis_ORPHAN": {
        "what_is_wrong": "You are confused about what gas exchange means, which makes the rest of photosynthesis hard to understand. Gas exchange is simply: CO2 goes in, O2 comes out, through tiny pores called stomata.",
        "story_fix": "Stomata are like a plant's nostrils — but they breathe CO2 in (not oxygen) and exhale oxygen out. Once you know this, the rest of photosynthesis makes sense as a manufacturing process using those raw materials.",
        "follow_up_question": "If a plant's stomata were all blocked by dust, which raw material would it be unable to get, and how would that affect glucose production?"
    },

    "water_cycle_GHOST": {
        "what_is_wrong": "You believe clouds are made of smoke or dust, or that water is permanently destroyed by the sun. In reality, clouds are made entirely of tiny water droplets.",
        "story_fix": "Water never disappears — it just changes form. Heat turns liquid water into invisible water vapour. As this vapour rises and cools, it condenses into visible droplets — that is a cloud. The cloud grows heavy and water falls back as rain. Same water, different forms.",
        "follow_up_question": "If you breathe on a cold mirror, tiny droplets appear. What process is this an example of, and how does it relate to cloud formation?"
    },
    "water_cycle_INVERT": {
        "what_is_wrong": "You have the order reversed — you said rain causes evaporation, but it is evaporation that eventually causes rain. The cycle goes: evaporation → condensation → precipitation.",
        "story_fix": "The sun starts the cycle by heating water surfaces, causing evaporation. Vapour rises, cools, condenses into clouds. When clouds hold too much water, precipitation happens. Rain is the end of one cycle and feeds the start of the next.",
        "follow_up_question": "If evaporation stopped happening (suppose the sun disappeared), would rain eventually stop too? Why?"
    },
    "water_cycle_HOLLOW": {
        "what_is_wrong": "You can name the stages — evaporation, condensation, precipitation — but cannot explain what physically happens at each stage or what drives them.",
        "story_fix": "Evaporation: sun's heat energy breaks water molecules free from the liquid surface, turning them into gas. Condensation: as water vapour rises into cooler air, molecules slow down and stick together, forming droplets around dust particles. Precipitation: droplets merge until gravity pulls them down as rain.",
        "follow_up_question": "Why does condensation happen when warm moist air meets a cold surface? What is physically happening to the water molecules?"
    },
    "water_cycle_FRAGMENT": {
        "what_is_wrong": "You described evaporation and precipitation correctly but forgot condensation (cloud formation) or the role of solar energy as the driver of the whole cycle.",
        "story_fix": "The missing link is condensation: water vapour does not automatically become rain. It must first cool and condense into cloud droplets. Only when enough droplets merge does precipitation occur. Without this step, you cannot explain where clouds come from.",
        "follow_up_question": "Why do clouds form at a certain height in the atmosphere rather than at ground level, even though water evaporates from the ground?"
    },
    "water_cycle_ORPHAN": {
        "what_is_wrong": "You do not understand evaporation — the idea that heat can turn liquid water into invisible gas. Without this, the rest of the cycle seems like magic.",
        "story_fix": "Evaporation is just water molecules escaping from the surface when they get enough energy from sunlight. You see this when wet clothes dry — the water did not vanish, it turned into water vapour in the air. The water cycle is this happening at a massive scale over oceans.",
        "follow_up_question": "Why do puddles dry up faster on a sunny day than on a cloudy day? What does this tell you about what drives evaporation?"
    },

    "food_chain_GHOST": {
        "what_is_wrong": "You believe energy increases as it moves up the food chain — that lions have more energy than grass. In reality, about 90% of energy is lost at each level as heat.",
        "story_fix": "Imagine passing a bucket of water up a chain of people. Each person drinks some before passing it on. By the time it reaches the top, the bucket is nearly empty. Energy in a food chain works the same way — each organism uses most of its energy to live, passing only ~10% to the next.",
        "follow_up_question": "Why are there far more rabbits than foxes in an ecosystem? How does energy loss at each trophic level explain this?"
    },
    "food_chain_INVERT": {
        "what_is_wrong": "You reversed who eats whom — you said carnivores eat plants or plants eat animals. The direction is: plants → herbivores → carnivores.",
        "story_fix": "Energy always flows from the organism that makes it to the one that eats it. Plants make energy from sunlight. Herbivores eat plants to get that energy. Carnivores eat herbivores. Nothing in this chain eats its predator — it flows in one direction only.",
        "follow_up_question": "If a new disease killed all herbivores in an ecosystem, how would this affect both the plant population and the carnivore population?"
    },
    "food_chain_HOLLOW": {
        "what_is_wrong": "You can name producers, consumers, and decomposers but cannot explain why energy flows in one direction or what role each plays in the ecosystem.",
        "story_fix": "Producers make energy using sunlight (photosynthesis). Consumers cannot make their own energy — they must eat to get it. Decomposers break down dead matter, recycling nutrients back to soil for producers. Each role is essential: remove any one and the whole system collapses.",
        "follow_up_question": "If decomposers were removed from an ecosystem, what would happen to the soil nutrients over time, and how would this affect producers?"
    },
    "food_chain_FRAGMENT": {
        "what_is_wrong": "You described the predator-prey relationships correctly but forgot decomposers or the concept of energy loss at each trophic level — both are essential parts of the chain.",
        "story_fix": "Decomposers complete the cycle. Without them, dead organisms would pile up and nutrients would be locked away permanently, starving the producers. Also, at each level, ~90% of energy is lost as heat — which is why you need many more plants than rabbits and many more rabbits than foxes.",
        "follow_up_question": "Why can a food chain rarely have more than 4 or 5 levels? What happens to the available energy at each step?"
    },
    "food_chain_ORPHAN": {
        "what_is_wrong": "You do not understand what producers do — you think they just exist in the chain without a special role. Producers are the only organisms that create energy from scratch using sunlight.",
        "story_fix": "All energy in a food chain originally came from the sun. Producers (plants) are the only organisms that can capture this solar energy and turn it into food. Every other organism in the chain ultimately depends on this process. Without producers, no energy enters the system at all.",
        "follow_up_question": "Could a food chain exist without producers? Could it exist without decomposers? Which removal would collapse the chain faster?"
    },
}


# ── 30 STUDENTS ───────────────────────────────────────────────────────────────

STUDENTS = [
    # ── PHOTOSYNTHESIS ──────────────────────────────────────────────────────
    {
        "student_id": "S01", "student_name": "Priya Raghavan",
        "topic": "photosynthesis", "fingerprint": "INVERT", "drift_score": 0.71,
        "activated_nodes": ["gas_exchange", "sunlight_energy", "water_absorption"],
        "skipped_nodes":   ["chlorophyll", "glucose_production", "cellular_respiration"],
        "wrong_claims":    ["release co2"],
        "answer": "Plants absorb oxygen from air and release CO2 just like humans do through breathing, and they use the sun's energy to make food.",
    },
    {
        "student_id": "S02", "student_name": "Arjun Mehta",
        "topic": "photosynthesis", "fingerprint": "FRAGMENT", "drift_score": 0.41,
        "activated_nodes": ["sunlight_energy", "water_absorption", "glucose_production"],
        "skipped_nodes":   ["gas_exchange", "chlorophyll", "cellular_respiration"],
        "wrong_claims":    [],
        "answer": "Plants use sunlight and water from the soil to make food for themselves.",
    },
    {
        "student_id": "S03", "student_name": "Divya Gowda",
        "topic": "photosynthesis", "fingerprint": "HOLLOW", "drift_score": 0.58,
        "activated_nodes": ["chlorophyll", "sunlight_energy", "glucose_production", "gas_exchange"],
        "skipped_nodes":   ["water_absorption", "cellular_respiration"],
        "wrong_claims":    [],
        "answer": "Photosynthesis uses chlorophyll to absorb sunlight and the plant makes glucose and oxygen is released.",
    },
    {
        "student_id": "S04", "student_name": "Ravi Kumar",
        "topic": "photosynthesis", "fingerprint": "FRAGMENT", "drift_score": 0.38,
        "activated_nodes": ["sunlight_energy", "gas_exchange", "water_absorption", "glucose_production"],
        "skipped_nodes":   ["chlorophyll", "cellular_respiration"],
        "wrong_claims":    [],
        "answer": "Sunlight hits the leaves and the plant uses CO2 and water to make glucose but I forget what gas comes out.",
    },
    {
        "student_id": "S05", "student_name": "Ananya Singh",
        "topic": "photosynthesis", "fingerprint": "GHOST", "drift_score": 0.88,
        "activated_nodes": ["sunlight_energy"],
        "skipped_nodes":   ["gas_exchange", "chlorophyll", "glucose_production", "water_absorption", "cellular_respiration"],
        "wrong_claims":    ["breathe in oxygen", "breathe out co2"],
        "answer": "Plants breathe in oxygen like us and breathe out CO2 to make energy from the sun just like animals.",
    },
    {
        "student_id": "S06", "student_name": "Keerthi Nair",
        "topic": "photosynthesis", "fingerprint": "HOLLOW", "drift_score": 0.64,
        "activated_nodes": ["chlorophyll", "sunlight_energy", "glucose_production"],
        "skipped_nodes":   ["gas_exchange", "water_absorption", "cellular_respiration"],
        "wrong_claims":    [],
        "answer": "Chlorophyll absorbs light and plants produce glucose and oxygen comes out of the leaves.",
    },
    {
        "student_id": "S07", "student_name": "Mohan Pillai",
        "topic": "photosynthesis", "fingerprint": "FRAGMENT", "drift_score": 0.47,
        "activated_nodes": ["sunlight_energy", "water_absorption", "glucose_production"],
        "skipped_nodes":   ["gas_exchange", "chlorophyll", "cellular_respiration"],
        "wrong_claims":    [],
        "answer": "The sun heats plants and they use water from soil and roots to produce their own food.",
    },
    {
        "student_id": "S08", "student_name": "Sneha Iyer",
        "topic": "photosynthesis", "fingerprint": "ORPHAN", "drift_score": 0.53,
        "activated_nodes": ["chlorophyll", "sunlight_energy", "glucose_production"],
        "skipped_nodes":   ["gas_exchange", "water_absorption", "cellular_respiration"],
        "wrong_claims":    [],
        "answer": "Photosynthesis makes glucose using chlorophyll and sunlight but I don't understand what happens to the carbon dioxide.",
    },
    {
        "student_id": "S09", "student_name": "Vijay Sharma",
        "topic": "photosynthesis", "fingerprint": "FRAGMENT", "drift_score": 0.34,
        "activated_nodes": ["gas_exchange", "sunlight_energy", "water_absorption", "glucose_production", "chlorophyll"],
        "skipped_nodes":   ["cellular_respiration"],
        "wrong_claims":    [],
        "answer": "Leaves absorb CO2 through stomata, roots absorb water, chlorophyll traps sunlight and the plant converts these into glucose and releases oxygen.",
    },
    {
        "student_id": "S10", "student_name": "Kavitha Bose",
        "topic": "photosynthesis", "fingerprint": "GHOST", "drift_score": 0.84,
        "activated_nodes": ["chlorophyll", "sunlight_energy"],
        "skipped_nodes":   ["gas_exchange", "glucose_production", "water_absorption", "cellular_respiration"],
        "wrong_claims":    ["release co2", "absorb oxygen"],
        "answer": "Plants use their green leaves to breathe and they absorb oxygen and give out CO2 just like we do.",
    },

    # ── WATER CYCLE ─────────────────────────────────────────────────────────
    {
        "student_id": "S11", "student_name": "Rahul Reddy",
        "topic": "water_cycle", "fingerprint": "FRAGMENT", "drift_score": 0.36,
        "activated_nodes": ["solar_energy", "evaporation", "condensation", "precipitation", "collection"],
        "skipped_nodes":   ["transpiration"],
        "wrong_claims":    [],
        "answer": "Sun heats ocean water, it evaporates, forms clouds, and falls as rain which collects in rivers and lakes.",
    },
    {
        "student_id": "S12", "student_name": "Meena Krishnan",
        "topic": "water_cycle", "fingerprint": "HOLLOW", "drift_score": 0.67,
        "activated_nodes": ["evaporation", "condensation", "precipitation"],
        "skipped_nodes":   ["collection", "transpiration", "solar_energy"],
        "wrong_claims":    [],
        "answer": "There is evaporation and condensation and precipitation and the water goes around in a cycle.",
    },
    {
        "student_id": "S13", "student_name": "Suresh Patel",
        "topic": "water_cycle", "fingerprint": "INVERT", "drift_score": 0.76,
        "activated_nodes": ["evaporation", "condensation", "precipitation"],
        "skipped_nodes":   ["collection", "transpiration", "solar_energy"],
        "wrong_claims":    ["rain causes evaporation"],
        "answer": "Rain causes water to evaporate from puddles because the rain falls on hot ground and heats up.",
    },
    {
        "student_id": "S14", "student_name": "Lakshmi Nair",
        "topic": "water_cycle", "fingerprint": "FRAGMENT", "drift_score": 0.28,
        "activated_nodes": ["solar_energy", "evaporation", "condensation", "precipitation", "collection"],
        "skipped_nodes":   ["transpiration"],
        "wrong_claims":    [],
        "answer": "Sun heats water, it turns to vapour, vapour cools to form clouds, rain falls and flows back to rivers and the sea.",
    },
    {
        "student_id": "S15", "student_name": "Kiran Joshi",
        "topic": "water_cycle", "fingerprint": "GHOST", "drift_score": 0.91,
        "activated_nodes": ["solar_energy"],
        "skipped_nodes":   ["evaporation", "condensation", "precipitation", "collection", "transpiration"],
        "wrong_claims":    ["clouds are dust", "water disappears"],
        "answer": "Water just disappears from the ocean when the sun burns it and then it rains randomly from clouds which are made of dust.",
    },
    {
        "student_id": "S16", "student_name": "Deepa Kumar",
        "topic": "water_cycle", "fingerprint": "FRAGMENT", "drift_score": 0.32,
        "activated_nodes": ["solar_energy", "evaporation", "condensation", "precipitation", "collection"],
        "skipped_nodes":   ["transpiration"],
        "wrong_claims":    [],
        "answer": "Sun heats ocean water, vapour rises and condenses into clouds, rain falls and flows back to the sea.",
    },
    {
        "student_id": "S17", "student_name": "Arun Thomas",
        "topic": "water_cycle", "fingerprint": "HOLLOW", "drift_score": 0.60,
        "activated_nodes": ["evaporation", "condensation", "precipitation", "collection"],
        "skipped_nodes":   ["transpiration", "solar_energy"],
        "wrong_claims":    [],
        "answer": "The water cycle has evaporation then condensation then precipitation and then the water collects and starts again.",
    },
    {
        "student_id": "S18", "student_name": "Pooja Menon",
        "topic": "water_cycle", "fingerprint": "INVERT", "drift_score": 0.73,
        "activated_nodes": ["evaporation", "precipitation"],
        "skipped_nodes":   ["condensation", "collection", "transpiration", "solar_energy"],
        "wrong_claims":    ["rain causes evaporation"],
        "answer": "When it rains the water evaporates because the rain falls on the hot ground and makes steam that goes up.",
    },
    {
        "student_id": "S19", "student_name": "Ganesh Rao",
        "topic": "water_cycle", "fingerprint": "FRAGMENT", "drift_score": 0.21,
        "activated_nodes": ["solar_energy", "evaporation", "transpiration", "condensation", "precipitation", "collection"],
        "skipped_nodes":   [],
        "wrong_claims":    [],
        "answer": "Transpiration from plants adds water vapour to the air, the sun evaporates water from seas, both form clouds, rain falls and collects in rivers.",
    },
    {
        "student_id": "S20", "student_name": "Harini Pillai",
        "topic": "water_cycle", "fingerprint": "GHOST", "drift_score": 0.86,
        "activated_nodes": ["solar_energy"],
        "skipped_nodes":   ["evaporation", "condensation", "precipitation", "collection", "transpiration"],
        "wrong_claims":    ["water turns to smoke", "clouds are dust"],
        "answer": "Water gets really hot and turns to smoke which floats up and becomes clouds made of dust and dirt in the air.",
    },

    # ── FOOD CHAIN ───────────────────────────────────────────────────────────
    {
        "student_id": "S21", "student_name": "Inder Singh",
        "topic": "food_chain", "fingerprint": "FRAGMENT", "drift_score": 0.31,
        "activated_nodes": ["producer", "primary_consumer", "secondary_consumer", "decomposer", "energy_flow"],
        "skipped_nodes":   ["trophic_levels"],
        "wrong_claims":    [],
        "answer": "Grass is producer, rabbit is primary consumer, fox is secondary consumer, bacteria decompose dead things and energy flows down the chain.",
    },
    {
        "student_id": "S22", "student_name": "Janaki Reddy",
        "topic": "food_chain", "fingerprint": "GHOST", "drift_score": 0.85,
        "activated_nodes": ["producer", "primary_consumer", "secondary_consumer"],
        "skipped_nodes":   ["decomposer", "energy_flow", "trophic_levels"],
        "wrong_claims":    ["energy increases up the chain"],
        "answer": "Plants make food, herbivores eat plants, carnivores eat herbivores and the energy increases as it goes up the chain.",
    },
    {
        "student_id": "S23", "student_name": "Kewal Nair",
        "topic": "food_chain", "fingerprint": "FRAGMENT", "drift_score": 0.44,
        "activated_nodes": ["producer", "primary_consumer", "secondary_consumer", "energy_flow"],
        "skipped_nodes":   ["decomposer", "trophic_levels"],
        "wrong_claims":    [],
        "answer": "Sun gives energy to plants, plants eaten by rabbits, rabbits by wolves, energy transfers at each level but I forgot decomposers.",
    },
    {
        "student_id": "S24", "student_name": "Lalitha Sharma",
        "topic": "food_chain", "fingerprint": "HOLLOW", "drift_score": 0.62,
        "activated_nodes": ["producer", "primary_consumer", "secondary_consumer", "decomposer"],
        "skipped_nodes":   ["energy_flow", "trophic_levels"],
        "wrong_claims":    [],
        "answer": "There are producers and consumers and decomposers in a food chain and they all depend on each other.",
    },
    {
        "student_id": "S25", "student_name": "Manoj Kumar",
        "topic": "food_chain", "fingerprint": "FRAGMENT", "drift_score": 0.39,
        "activated_nodes": ["producer", "primary_consumer", "secondary_consumer", "energy_flow"],
        "skipped_nodes":   ["decomposer", "trophic_levels"],
        "wrong_claims":    [],
        "answer": "Grass is eaten by deer then deer by tiger, each level has less energy available for the next organism.",
    },
    {
        "student_id": "S26", "student_name": "Neeraja Iyer",
        "topic": "food_chain", "fingerprint": "INVERT", "drift_score": 0.79,
        "activated_nodes": ["secondary_consumer", "energy_flow"],
        "skipped_nodes":   ["producer", "primary_consumer", "decomposer", "trophic_levels"],
        "wrong_claims":    ["carnivores eat plants"],
        "answer": "Carnivores eat plants at the bottom and energy flows upward so the top animals make their own energy from eating.",
    },
    {
        "student_id": "S27", "student_name": "Omkar Pillai",
        "topic": "food_chain", "fingerprint": "ORPHAN", "drift_score": 0.56,
        "activated_nodes": ["decomposer", "primary_consumer"],
        "skipped_nodes":   ["producer", "secondary_consumer", "energy_flow", "trophic_levels"],
        "wrong_claims":    [],
        "answer": "Decomposers are the most important because they eat everything and make the chain work but I don't understand where plants fit in.",
    },
    {
        "student_id": "S28", "student_name": "Padma Bose",
        "topic": "food_chain", "fingerprint": "FRAGMENT", "drift_score": 0.26,
        "activated_nodes": ["producer", "primary_consumer", "secondary_consumer", "decomposer", "energy_flow"],
        "skipped_nodes":   ["trophic_levels"],
        "wrong_claims":    [],
        "answer": "Plants use photosynthesis as producers, rabbits as primary consumers eat plants, snakes eat rabbits, fungi break down dead matter returning nutrients to soil.",
    },
    {
        "student_id": "S29", "student_name": "Rishi Gowda",
        "topic": "food_chain", "fingerprint": "FRAGMENT", "drift_score": 0.19,
        "activated_nodes": ["producer", "primary_consumer", "secondary_consumer", "decomposer", "energy_flow", "trophic_levels"],
        "skipped_nodes":   [],
        "wrong_claims":    [],
        "answer": "Energy flows from sun to plants to herbivores to carnivores and about 10 percent is transferred at each trophic level, the rest is lost as heat.",
    },
    {
        "student_id": "S30", "student_name": "Savita Menon",
        "topic": "food_chain", "fingerprint": "ORPHAN", "drift_score": 0.52,
        "activated_nodes": ["producer", "primary_consumer"],
        "skipped_nodes":   ["secondary_consumer", "decomposer", "energy_flow", "trophic_levels"],
        "wrong_claims":    [],
        "answer": "I know grass is eaten by deer but I don't understand where decomposers fit in or how energy is measured at each level.",
    },
]


# ── HISTORY TEMPLATES (drift progression per fingerprint) ─────────────────────
# Each tuple: (days_ago, drift_delta)  — drift_delta added to final drift score
HIST_TEMPLATE = {
    "GHOST":    [(14, +0.08), (9, +0.05), (4, +0.02)],
    "INVERT":   [(13, +0.12), (8, +0.06), (3, +0.03)],
    "HOLLOW":   [(12, +0.10), (7, +0.05), (2, +0.02)],
    "FRAGMENT": [(11, +0.14), (6, +0.07), (2, +0.03)],
    "ORPHAN":   [(13, +0.09), (7, +0.05), (3, +0.02)],
}


async def seed():
    client = AsyncIOMotorClient(MONGO_URI)
    db     = client[DB_NAME]

    # Clear old seed data
    await db.students.delete_many({})
    await db.students_history.delete_many({})
    print(f"Cleared existing student data from '{DB_NAME}'")

    now = datetime.now()

    for s in STUDENTS:
        key  = f"{s['topic']}_{s['fingerprint']}"
        rem  = REM.get(key, {
            "what_is_wrong":     "Review this topic with your teacher.",
            "story_fix":         "Practice the concept step by step.",
            "follow_up_question":"Can you explain this to a classmate?",
        })

        doc = {
            "student_id":      s["student_id"],
            "student_name":    s["student_name"],
            "topic":           s["topic"],
            "answer":          s["answer"],
            "fingerprint":     s["fingerprint"],
            "drift_score":     s["drift_score"],
            "activated_nodes": s["activated_nodes"],
            "skipped_nodes":   s["skipped_nodes"],
            "wrong_claims":    s["wrong_claims"],
            "remediation": {
                "what_is_wrong":     rem["what_is_wrong"],
                "story_fix":         rem["story_fix"],
                "follow_up_question":rem["follow_up_question"],
            },
            "language":   "english",
            "timestamp":  now.isoformat(),
        }

        await db.students.insert_one(doc)

        # History — progression over the past 2 weeks
        template = HIST_TEMPLATE.get(s["fingerprint"], [(10, +0.10), (5, +0.05)])
        for days_ago, delta in template:
            drift_hist = min(1.0, round(s["drift_score"] + delta, 3))
            hist_doc   = {
                "student_id":  s["student_id"],
                "drift_score": drift_hist,
                "fingerprint": s["fingerprint"],
                "topic":       s["topic"],
                "timestamp":   (now - timedelta(days=days_ago)).isoformat(),
            }
            await db.students_history.insert_one(hist_doc)

        # Latest state also in history
        await db.students_history.insert_one({
            "student_id":  s["student_id"],
            "drift_score": s["drift_score"],
            "fingerprint": s["fingerprint"],
            "topic":       s["topic"],
            "timestamp":   now.isoformat(),
        })

        print(f"  [{s['fingerprint']:<8}] {s['student_id']} {s['student_name']:<20} {s['topic']:<15} drift={s['drift_score']}")

    total_students = len(STUDENTS)
    total_history  = sum(len(HIST_TEMPLATE.get(s["fingerprint"], [(0,0),(0,0)])) + 1 for s in STUDENTS)
    print(f"\nSeeded {total_students} students + {total_history} history records into MongoDB '{DB_NAME}'")
    print("Open the teacher dashboard: http://localhost:8000/dashboard")
    print("Open the student portal:    http://localhost:8000/student")
    client.close()


if __name__ == "__main__":
    asyncio.run(seed())

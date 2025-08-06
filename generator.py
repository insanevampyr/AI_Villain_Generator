import openai
import os
import streamlit as st
from dotenv import load_dotenv
import random
import json
import re

if not st.secrets:
    load_dotenv()
openai.api_key = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY"))

def generate_villain(tone="dark"):
    # Variety + originality boost
    variety_prompt = random.choice([
        "Avoid using shadow or darkness-based powers.",
        "Avoid doctors and scientists as characters.",
        "Do not repeat any powers or names from previous villains.",
        "Use a bizarre or uncommon origin story.",
        "Give them a name and alias not based on 'dark' or 'shadow'.",
        "Use a power that sounds impractical but terrifying.",
        "Make the character totally unpredictable or strange."
    ])

    prompt = f"""
Create a unique and original supervillain character profile in a {tone} tone. 
You must not use shadow/darkness powers or doctor/scientist names.
{variety_prompt}

Return JSON with the following keys:

name: A villainous full name (not a doctor)
alias: A creative codename that is not 'dark' or 'shadow' themed
power: Unique primary superpower
weakness: Core vulnerability
nemesis: Their heroic enemy
lair: Where they operate from
catchphrase: A short quote they often say
crimes: List of crimes or signature actions
threat_level: One of [Low, Moderate, High, Extreme]
faction: Group or syndicate name
origin: A 2–3 sentence origin story
"""

    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a creative villain generator."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.95,
        )

        raw = response.choices[0].message.content.strip()
        raw = re.sub(r",\s*}", "}", raw)
        raw = re.sub(r",\s*]", "]", raw)
        data = json.loads(raw)

        return {
            "name": data.get("name", "Unknown"),
            "alias": data.get("alias", "Unknown"),
            "power": data.get("power", "Unknown"),
            "weakness": data.get("weakness", "Unknown"),
            "nemesis": data.get("nemesis", "Unknown"),
            "lair": data.get("lair", "Unknown"),
            "catchphrase": data.get("catchphrase", "Unknown"),
            "crimes": data.get("crimes", "Unknown"),
            "threat_level": data.get("threat_level", "Unknown"),
            "faction": data.get("faction", "Unknown"),
            "origin": data.get("origin", "Unknown"),
        }
    except Exception as e:
        return {
            "name": "Error",
            "alias": "Parse Failure",
            "power": "Unknown",
            "weakness": "Unknown",
            "nemesis": "Unknown",
            "lair": "Unknown",
            "catchphrase": str(e),
            "crimes": "Unknown",
            "threat_level": "Unknown",
            "faction": "Unknown",
            "origin": "The generator failed to parse the villain data.",
        }

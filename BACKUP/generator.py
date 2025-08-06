import openai
import os
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

def generate_villain(tone="dark"):
    prompt = f"""
Create a fictional supervillain character profile in a {tone} style. Return the details as JSON with the following keys:

name: A villainous full name
alias: A dramatic or mysterious codename
power: Primary superpower
weakness: Main vulnerability
nemesis: A hero or rival
lair: Where they operate from
catchphrase: Short and bold quote they use
crimes: List of crimes or notorious actions
threat_level: Low, Moderate, High, or Extreme
faction: Name of group they belong to
origin: A brief 2–3 sentence origin story
"""

    response = openai.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a creative villain generator."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=500,
        temperature=0.9,
    )

    try:
        import json
        raw = response.choices[0].message.content.strip()
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

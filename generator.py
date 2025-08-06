import openai
import os
import streamlit as st
from dotenv import load_dotenv

# Load local .env only if not running on Streamlit Cloud
if not st.secrets:
    load_dotenv()

# Fallback to os.getenv if not running on cloud
openai.api_key = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY"))

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
        model="gpt-3.5-turbo",
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

        # 💡 Fix: remove illegal trailing commas
        import re
        raw = re.sub(r",\s*}", "}", raw)
        raw = re.sub(r",\s*]", "]", raw)

        # Show the raw response in Streamlit so we can debug
        import streamlit as st
        st.subheader("🔍 DEBUG: Raw AI Output")
        st.code(raw)

        # Then try to load it as JSON
        import json
        try:
            data = json.loads(raw)
        except Exception as e:
            st.error(f"JSON Parse Error: {e}")
            st.stop()  # stops the app here if it fails

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

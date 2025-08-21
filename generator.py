# generator.py
import os
import re
import json
import time
import random
from typing import Dict, List, Deque, Optional, Tuple, Any
from collections import deque

import streamlit as st
from dotenv import load_dotenv
import openai

from optimization_utils import set_debug_info
from config import POWER_POOLS, POWER_CRIME_MAP, POWER_FAMILIES, GENERIC_CRIMES

# --- API key bootstrap ---
if not st.secrets:
    load_dotenv()
openai.api_key = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))

# -------- Names: import pools from config --------
try:
    from config import MALE_NAMES, FEMALE_NAMES, NEUTRAL_NAMES, LAST_NAMES
except Exception:
    # safe fallbacks
    MALE_NAMES = ["Alex", "Benjamin", "Carter", "Diego", "Ethan", "Gavin", "Hunter", "Isaac", "Jacob", "Liam"]
    FEMALE_NAMES = ["Ava", "Bella", "Camila", "Chloe", "Elena", "Emma", "Hannah", "Isabella", "Layla", "Lily"]
    NEUTRAL_NAMES = ["Avery", "Blair", "Casey", "Charlie", "Dakota", "Eden", "Emery", "Jordan", "Quinn", "Riley"]
    LAST_NAMES = ["Reed", "Hart", "Lane", "Sloan", "Hayes", "Quinn", "Rivera", "Nguyen", "Khan", "Silva"]

# --- small de-dupe so neutral names don't dominate gendered lists
def _dedup_across_pools():
    neutral_set = {n.lower() for n in NEUTRAL_NAMES}
    def _filter(pool):
        return [n for n in pool if n and n.strip() and n.lower() not in neutral_set]
    return _filter(MALE_NAMES), _filter(FEMALE_NAMES)

MALE_NAMES, FEMALE_NAMES = _dedup_across_pools()

# ============= Shuffle-bag for non-repeating names =============
class ShuffleBag:
    def __init__(self, items: List[str]):
        self.pool: List[str] = list(dict.fromkeys([i.strip() for i in items if i and i.strip()]))
        self.queue: Deque[str] = deque()
        self._reshuffle()

    def _reshuffle(self):
        if not self.pool:
            self.queue = deque()
            return
        tmp = self.pool[:]
        random.shuffle(tmp)
        self.queue = deque(tmp)

    def draw(self) -> Optional[str]:
        if not self.queue:
            self._reshuffle()
        if not self.queue:
            return None
        return self.queue.popleft()

    def __len__(self):
        return len(self.queue)

def _ensure_bags():
    if "name_bags" not in st.session_state:
        st.session_state.name_bags = {
            "male": ShuffleBag(MALE_NAMES),
            "female": ShuffleBag(FEMALE_NAMES),
            "nonbinary": ShuffleBag(NEUTRAL_NAMES),
            "last": ShuffleBag(LAST_NAMES),
        }
    if "name_cooldown" not in st.session_state:
        st.session_state.name_cooldown = {"first": deque(maxlen=10), "last": deque(maxlen=10)}

def _draw_nonrepeating(kind: str, role: str) -> str:
    _ensure_bags()
    bags = st.session_state.name_bags
    cdq = st.session_state.name_cooldown["first" if role == "first" else "last"]
    bag = bags[kind]
    tried = set()
    for _ in range(max(3, len(bag) + 3)):
        pick = bag.draw()
        if pick is None:
            break
        key = pick.lower()
        if key in tried:
            continue
        tried.add(key)
        if key not in (n.lower() for n in cdq):
            cdq.append(pick)
            return pick
    pick = bag.draw() or "Alex"
    cdq.append(pick)
    return pick

# --------------------------- Theme profiles ---------------------------
THEME_PROFILES: Dict[str, dict] = {
    "funny": {
        "temperature": 0.98,
        "encourage": ["prank", "slapstick", "gag", "spoof", "ridiculous", "banana", "rubber chicken", "confetti",
                      "prop comedy", "improv", "farce", "pie", "whoopee", "balloon"],
        "ban": ["quantum", "nanotech", "plasma", "neural", "cyber", "singularity", "neutrino", "lattice"],
        "tech_allow_ratio": 0.12,
        "threat_dist": {"Laughable Low": 0.60, "Moderate": 0.30, "High": 0.10, "Extreme": 0.00},
        "variety_prompts": [
            "Lean into slapstick physics or improbable gags that sometimes backfire.",
            "Make the motive comedic or petty; the villain often defeats themselves.",
            "Prefer analog props and clownish contraptions over technology."
        ],
        "tone": "witty, playful, deadpan humor, punchy sentences"
    },
    "satirical": {
        "temperature": 0.98,
        "encourage": ["parody", "irony", "meme", "spoof", "absurd", "bureaucracy", "red tape", "clickbait",
                      "propaganda", "inflated ego", "farce"],
        "ban": ["quantum", "nanotech", "plasma", "neural", "singularity"],
        "tech_allow_ratio": 0.15,
        "threat_dist": {"Laughable Low": 0.50, "Moderate": 0.35, "High": 0.15, "Extreme": 0.00},
        "variety_prompts": [
            "Skewer institutions, brands, or trends without naming real companies.",
            "Let the crimes be pranks with social commentary.",
            "Keep the tone clever and self-aware."
        ],
        "tone": "arch, ironic, punchy commentary"
    },
    "dark": {
        "temperature": 0.86,
        "encourage": ["dread", "chiaroscuro", "wither", "void", "decay", "entropy", "curse", "sigil", "mirror", "hush"],
        "ban": ["quirky", "goofy", "neon", "brand", "corporate meme"],
        "threat_dist": {"Laughable Low": 0.00, "Moderate": 0.20, "High": 0.50, "Extreme": 0.30},
        "variety_prompts": [
            "Lean occult or psychological rather than sci-fi.",
            "Give the lair a predatory, oppressive vibe.",
            "Make the catchphrase unsettling or ritualistic."
        ],
        "tone": "ominous, predatory, heavy cadence"
    },
    "mythic": {
        "temperature": 0.85,
        "encourage": ["oath", "wyrd", "totem", "beast-command", "fate", "stormcalling", "relic", "underworld"],
        "ban": ["neon", "cyber", "nanotech", "brand"],
        "threat_dist": {"Laughable Low": 0.00, "Moderate": 0.20, "High": 0.50, "Extreme": 0.30},
        "variety_prompts": [
            "Root the power in old law, bargains, or ancient places.",
            "Let imagery pull from rivers, forests, mountains, or the underworld.",
            "Use timeless phrasing; no hard sci-fi jargon."
        ],
        "tone": "timeless, poetic, folkloric"
    },
    "sci-fi": {
        "temperature": 0.80,
        "encourage": ["lattice", "protocol", "phase", "singularity", "substrate", "nanite", "field", "synthetic"],
        "ban": ["ritual", "spell", "mythic", "oath", "totem"],
        "threat_dist": {"Laughable Low": 0.00, "Moderate": 0.30, "High": 0.50, "Extreme": 0.20},
        "variety_prompts": [
            "Use clean, precise techno-jargon and crisp mechanisms.",
            "Crimes hit infrastructure, orbit, or data.",
            "Tone should be clinical with occasional techno-poetry."
        ],
        "tone": "precise, technical, cool"
    },
    "cyberpunk": {
        "temperature": 0.82,
        "encourage": ["corpo", "ICE", "splice", "wetware", "aug", "drone swarm", "neon", "grid", "firmware", "black ICE"],
        "ban": ["ritual", "mythic", "divine", "sacred"],
        "threat_dist": {"Laughable Low": 0.00, "Moderate": 0.40, "High": 0.40, "Extreme": 0.20},
        "variety_prompts": [
            "Keep it street-level grime with corporate tyranny.",
            "Use slang and cynicism; avoid myth words.",
            "Crimes include ransoms, credential siphons, neural intrusion."
        ],
        "tone": "noir, neon-grime, terse"
    },
    "chaotic": {
        "temperature": 0.98,
        "encourage": ["glitch", "dice", "rollback", "probability", "flicker", "unlucky", "misfire", "coin toss"],
        "ban": [],
        "threat_dist": {"Laughable Low": 0.25, "Moderate": 0.25, "High": 0.25, "Extreme": 0.25},
        "variety_prompts": [
            "Let cause and effect wobble; odd metaphors are welcome.",
            "Include at least one unpredictable ‘chaos quirk’.",
            "Sentence lengths should oscillate: short, then long."
        ],
        "tone": "unstable, mischievous, reality-bending"
    },
}

LEVEL_ORDER = ["Laughable Low", "Moderate", "High", "Extreme"]
LEVEL_INDEX = {lvl: i for i, lvl in enumerate(LEVEL_ORDER)}

# --------------------------- helpers ---------------------------
TITLE_PATTERN = re.compile(r"^(dr\.?|mr\.?|mrs\.?|ms\.?|mx\.?)\s+", re.I)

def infer_gender_from_origin(origin: str):
    o = (origin or "").lower()
    if " she " in o or o.startswith("she "):
        return "female"
    if " he " in o or o.startswith("he "):
        return "male"
    return None

def normalize_real_name(name: str) -> str:
    if not name:
        return "Unknown Unknown"
    n = TITLE_PATTERN.sub("", name.strip())
    n = re.sub(r"\s+", " ", n)
    parts = n.split(" ")
    if len(parts) < 2:
        parts = [parts[0], random.choice(["Gray", "Reed", "Cole", "Hart", "Lane", "Sloan", "Hayes", "Quinn"])]
    parts = [p.capitalize() for p in parts[:2]]
    return " ".join(parts)

THREAT_KEYWORDS = [
    ("Laughable Low", ["prank", "pranks", "petty", "mischief", "small", "balloon", "confetti"]),
    ("Moderate", ["stealth", "toxins", "poisons", "hacking", "gadgets", "marksman", "acrobat",
                  "illusion", "hypnosis", "ice", "fire", "weather", "electric", "sonic", "plant"]),
    ("High", ["telekinesis", "biokinesis", "mind control", "energy manipulation", "gravity",
              "time dilation", "dimensional", "nanotech", "plague", "nuclear", "stormcalling"]),
    ("Extreme", ["reality", "time travel", "cosmic", "planetary", "universal", "multiverse",
                 "quantum rewriting", "space-time", "apocalyptic", "godlike", "celestial"]),
]

def classify_threat_from_power(power: str) -> str:
    p = (power or "").lower()
    level = "Moderate"
    for lvl, words in THREAT_KEYWORDS:
        if any(w in p for w in words):
            level = lvl
    return level

def sample_from_dist(dist: Dict[str, float]) -> str:
    levels, weights = zip(*dist.items())
    return random.choices(list(levels), weights=list(weights), k=1)[0]

def adjust_threat_for_theme(theme: str, computed: str, power_text: str) -> str:
    profile = THEME_PROFILES.get(theme, THEME_PROFILES["dark"])
    target = sample_from_dist(profile["threat_dist"])
    comp_i = LEVEL_INDEX.get(computed, 1)
    targ_i = LEVEL_INDEX.get(target, 1)

    if theme in ("funny", "satirical"):
        if LEVEL_INDEX.get(computed, 1) >= 3 and random.random() < (0.10 if theme == "funny" else 0.15):
            return "Extreme"
        return target
    if theme == "chaotic":
        return target
    final_i = max(comp_i, targ_i)
    return LEVEL_ORDER[final_i]

def tech_term_count(text: str) -> int:
    terms = ["quantum", "nanotech", "plasma", "neural", "cyber", "singularity", "neutrino", "lattice"]
    t = (text or "").lower()
    return sum(1 for w in terms if w in t)

# --------------------------- OpenAI helpers ---------------------------
def _chat_with_retry(messages, max_tokens=500, temperature=0.95, attempts=2, **kwargs):
    last_err = None
    for i in range(attempts):
        try:
            return openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs,
            )
        except Exception as e:
            last_err = e
            time.sleep(1.0 + i * 1.5)
    raise last_err

def _coerce_json(raw: str):
    try:
        return json.loads(raw)
    except Exception:
        pass
    if raw and "{" in raw and "}" in raw:
        try:
            s = raw[raw.find("{"): raw.rfind("}") + 1]
            s = re.sub(r",\s*}", "}", s)
            s = re.sub(r",\s*]", "]", s)
            return json.loads(s)
        except Exception:
            pass
    return None

def _fix_json_with_llm(bad_text: str):
    try:
        response = _chat_with_retry(
            messages=[
                {"role": "system", "content": "You fix malformed JSON. Output VALID JSON only, no commentary."},
                {"role": "user", "content": bad_text[:6000]},
            ],
            max_tokens=500,
            temperature=0.0,
            attempts=1,
        )
        txt = response.choices[0].message.content.strip()
        return _coerce_json(txt)
    except Exception:
        return None

def _normalize_origin_names(text: str, real_name: str, alias: str) -> str:
    if not text:
        return text
    system = (
        "You are editing a short villain origin paragraph. "
        "Keep the style and facts, but normalize names: "
        "use the provided REAL NAME for real identity mentions, and the provided ALIAS for codename mentions. "
        "Remove or replace any other names. Do not add new characters or quotations. "
        "Return only the edited paragraph."
    )
    user = f"REAL NAME: {real_name}\nALIAS: {alias}\n\nParagraph:\n{text}"
    try:
        resp = _chat_with_retry(
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            max_tokens=180, temperature=0.2, attempts=1,
        )
        out = (resp.choices[0].message.content or "").strip()
        return out if len(out) > 20 else text
    except Exception:
        return text

# =========================== Power-first helpers ===========================
def _infer_family(power: str) -> Tuple[str, Optional[str]]:
    p = (power or "").lower()
    for fam, keys in POWER_FAMILIES.items():
        if any(k in p for k in keys):
            return fam, next((k for k in keys if k in p), None)
    if "shadow" in p or "night" in p or "gloom" in p:
        return "shadow", "shadow"
    if "electro" in p or "lightning" in p or "ion" in p or "plasma" in p:
        return "electric", "electric"
    return "tech", None

def _ai_power_prompt(theme: str, encourage: List[str], ban: List[str]) -> str:
    style_line = f"Theme: {theme}. Encourage: {', '.join(encourage[:8])}. Avoid: {', '.join(ban[:8])}."
    rules = (
        "Return ONE power line ONLY in this exact format:\n"
        "Title — short cinematic description\n\n"
        "Constraints:\n- 5–9 words after the em dash; under 100 chars total.\n"
        "- Use an em dash (—), not a hyphen.\n- No real names, no quotes, no lists, no numbers, no emojis.\n- Fit the theme; obey 'Avoid' terms.\n"
    )
    return f"{style_line}\n{rules}"

def _valid_power_line(s: str, ban: List[str]) -> bool:
    if not s: return False
    if "—" not in s: return False
    if len(s) > 110: return False
    low = s.lower()
    if any(b in low for b in (ban or [])): return False
    if any(tok in low for tok in ["unknown", "lorem", "http", "www", "{", "}", "[", "]"]): return False
    if "\n" in s.strip(): return False
    return True

def _generate_ai_power(theme: str) -> Optional[str]:
    profile = THEME_PROFILES.get(theme, THEME_PROFILES["dark"])
    prompt = _ai_power_prompt(theme, profile.get("encourage", []), profile.get("ban", []))
    set_debug_info(context="AI Power (30%)", prompt=prompt, max_output_tokens=60,
                   cost_only=False, is_cache_hit=False)
    try:
        resp = _chat_with_retry(
            messages=[
                {"role": "system", "content": "You invent a single superpower line. Output exactly one line; no extra text."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=60,
            temperature=min(1.0, profile.get("temperature", 0.9) + 0.05),
            attempts=2,
        )
        cand = (resp.choices[0].message.content or "").strip()
        if _valid_power_line(cand, profile.get("ban", [])):
            return cand
        fix = _chat_with_retry(
            messages=[
                {"role": "system", "content": "Return ONE valid power line only: Title — short cinematic description."},
                {"role": "user", "content": prompt + "\nThe previous output failed validation. Obey all constraints."},
            ],
            max_tokens=60, temperature=0.7, attempts=1,
        )
        cand2 = (fix.choices[0].message.content or "").strip()
        if _valid_power_line(cand2, profile.get("ban", [])):
            return cand2
    except Exception:
        pass
    return None

def _cache_ai_power(theme: str, power: str) -> None:
    key = "ai_power_cache"
    if key not in st.session_state:
        st.session_state[key] = {}
    theme_cache = st.session_state[key].setdefault(theme, [])
    if power not in theme_cache:
        theme_cache.append(power)
        if len(theme_cache) > 20:
            theme_cache.pop(0)

def _is_cached(theme: str, power: str) -> bool:
    cache = st.session_state.get("ai_power_cache", {})
    return power in cache.get(theme, [])

def select_power(theme: str, ai_power_hint: Optional[str] = None) -> Tuple[str, str]:
    """
    70/30 rule:
      - 70%: pick from POWER_POOLS by theme (fast, consistent)
      - 30%: generate a theme-aware AI power, with validation & caching
    Returns (power_text, source) where source ∈ {"listed","ai"}
    """
    key = (theme or "").strip().lower()
    pool = POWER_POOLS.get(key, [])
    use_list = (random.random() < 0.70)

    if use_list and pool:
        return random.choice(pool), "listed"

    if ai_power_hint and "—" in ai_power_hint and len(ai_power_hint) < 110:
        cand = ai_power_hint.strip()
    else:
        cand = _generate_ai_power(key)

    if cand and cand.strip() and cand.strip().lower() != "unknown":
        if not _is_cached(key, cand):
            _cache_ai_power(key, cand)
        return cand.strip(), "ai"

    if pool:
        return random.choice(pool), "listed"
    try:
        from config import ALL_POWERS
        if ALL_POWERS:
            return random.choice(ALL_POWERS), "listed"
    except Exception:
        pass
    return "Shadowstep — slip between nearby patches of darkness", "listed"

# ---------- Crimes: examples + anti‑cliché logic (AI invents the final list) ----------
def _crime_examples_for_power(power: str) -> List[str]:
    fam, _ = _infer_family(power)
    base = POWER_CRIME_MAP.get(fam, GENERIC_CRIMES)
    k = min(5, len(base))
    return random.sample(base, k=k) if k > 0 else GENERIC_CRIMES[:3]

# clichés we hard‑ban verbatim from the UI
CICHE_CRIMES = [
    "ai drone heists of armored trucks",
    "city-wide ransomware blackouts",
    "weaponized autonomous car hijackings",
    "critical infrastructure intrusions",
]

FAMILY_SYNONYMS = {
    "shadow": [
        "staging mass blackouts of courage in crowded plazas",
        "abductions through lightless corridors no camera can see",
        "fear-pageants that stampede districts after midnight",
        "silencing witnesses by swallowing their silhouettes",
        "smothering search teams beneath living darkness",
    ],
    "mind": [
        "crowd hypnosis that redirects entire rallies",
        "memory swaps that make officials confess to others’ crimes",
        "cult initiations that bind targets with implanted devotion",
        "invisible suggestion heists during live broadcasts",
        "mass loyalty flips inside courtrooms",
    ],
    "fire": [
        "ritual burnlines that cut evacuation routes",
        "melting safes into slag mid‑heist",
        "arson mosaics as extortion signatures",
        "flare storms that torch drone patrols",
        "ember rain over financial districts",
    ],
    "funny": [
        "confetti avalanches that jam turnstiles",
        "banana‑slick evacuations of corporate lobbies",
        "rubber‑anvil air drops on armored convoys",
        "seltzer flood drills that short out alarms",
        "sticker nets that cocoon security teams",
    ],
    "tech": [
        "firmware ghosting of emergency sirens",
        "worm‑ridden escrow swaps mid‑transaction",
        "deepfake evacuations that empty vault floors",
        "neural decoy loops for response AIs",
        "smart‑grid misrouting that cooks substations silently",
    ],
    "sci-fi": [
        "phase‑through smash‑and‑grabs on bonded vaults",
        "gravity nicks that fold bridges for tolls",
        "hardlight barricades that trap police columns",
        "tachyon stutters to undo witness timelines",
        "plasma scoring of armored rail convoys",
    ],
    "chaotic": [
        "probability spikes that crash stock auctions",
        "roulette disasters in crowded terminals",
        "jammed destinies that misplace rescue teams",
        "dice‑weighted evacuations with the wrong exits",
        "catastrophe seeds that bloom in traffic grids",
    ],
    "mythic": [
        "oath‑bound kidnappings at crossroads shrines",
        "thorn mazes that swallow pursuit teams",
        "storm‑tithes demanded from coastal districts",
        "relic curses that turn evidence to salt",
        "underworld tolls charged on river crossings",
    ],
    "satirical": [
        "paperwork sieges that shut down hospitals",
        "sponsor‑mandated evacuations as ad campaigns",
        "ratio mobs hired to paralyze juries",
        "contract switches that repossess public parks",
        "brand excommunications of city departments",
    ],
    "air": [
        "hurricane‑force terror strikes",
        "weaponized sonic booms over cities",
        "skyway thefts using pressure corridors",
        "oxygen‑snatch raids inside high‑rises",
        "drone squall scatterings (without autonomy hacks)",
    ],
}

def _infer_family_soft(power: str) -> str:
    p = (power or "").lower()
    for fam, keys in POWER_FAMILIES.items():
        if any(k in p for k in keys):
            return fam
    if "shadow" in p or "night" in p: return "shadow"
    if "electro" in p or "lightning" in p or "ion" in p or "plasma" in p: return "tech"
    return "tech"

def _crime_bans_and_style(power: str, theme: str) -> str:
    fam = _infer_family_soft(power)
    bans = []
    # hard-ban cliché tech crimes unless we're clearly tech/sci-fi/cyberpunk
    if fam not in ("tech",) and theme not in ("sci-fi", "cyberpunk"):
        bans.extend(CICHE_CRIMES)
    # always ban exact copy of the clichés
    bans.extend(CICHE_CRIMES)
    ban_line = "; ".join(sorted(set(bans)))
    variety = (
        "Crimes must be distinct from each other, avoid repeating nouns ('drones', 'ransomware', 'cars'), "
        "and vary targets (people, finance, transit, comms, landmarks)."
    )
    return f"HARD BANS (verbatim): {ban_line or '—'}\nVARIETY CONSTRAINTS: {variety}"

def _diversify_crimes_after(power: str, theme: str, crimes: List[str]) -> List[str]:
    fam = _infer_family_soft(power)
    base = FAMILY_SYNONYMS.get(fam, FAMILY_SYNONYMS.get(theme, [])) or FAMILY_SYNONYMS.get("tech", [])
    seen = set()
    out = []
    for c in crimes:
        low = c.strip().lower()
        if not low or low in seen:
            continue
        seen.add(low)
        if any(low == bad for bad in CICHE_CRIMES):
            out.append(random.choice(base))
        else:
            out.append(c.strip())
    while len(out) < 3 and base:
        pick = random.choice(base)
        if pick.lower() not in (x.lower() for x in out):
            out.append(pick)
    return out[:5]

# --- normalize weird LLM crime shapes into clean strings ---
_KEY_DROP = {"crime", "crime1", "crime2", "crime3", "target", "victim", "where", "who", "how"}

def _flatten_text(v: Any) -> str:
    s = " ".join(str(x) for x in v) if isinstance(v, (list, tuple)) else str(v)
    s = re.sub(r"^\s*[-•]\s*", "", s.strip())
    s = re.sub(r"^\s*['\"{[(]+|['\"})\]]+\s*$", "", s)  # strip wrapping quotes/braces
    s = re.sub(r"\s+", " ", s)
    return s.strip("-• ").strip()

def _normalize_crime_item(x: Any) -> Optional[str]:
    if x is None:
        return None
    if isinstance(x, dict):
        parts = []
        for k, v in x.items():
            kl = str(k).strip().lower()
            if kl in _KEY_DROP:
                parts.append(_flatten_text(v))
            else:
                parts.append(_flatten_text(v))
        s = ", ".join(p for p in parts if p)
    else:
        s = _flatten_text(x)
        # kill obvious dict-likes accidentally stringified
        s = re.sub(r"^['\"]?\{.*?:.*\}['\"]?$", "", s)
    s = s.strip()
    if not s:
        return None
    # basic length + no braces
    if any(ch in s for ch in "{}[]"):
        s = re.sub(r"[{}\[\]]", "", s).strip()
    # keep between ~4..14 words
    if not (4 <= len(s.split()) <= 14):
        return None
    return s

# --------------------------- Origin helpers ---------------------------
def ensure_crime_mentions_in_origin(origin: str, crimes: List[str]) -> bool:
    o = (origin or "").lower()
    return any(c.lower() in o for c in crimes)

def _origin_prompt(theme: str, power: str, crimes: List[str], alias: str, real_name: str) -> str:
    profile = THEME_PROFILES.get(theme, THEME_PROFILES["dark"])
    style_line = f"Theme: {theme}. Tone: {profile['tone']}."
    crime_line = "Crimes involved: " + ", ".join(crimes) + "."
    rules = (
        "Write a single-paragraph origin (4–5 sentences, 80–120 words). "
        "It MUST explicitly mention the given POWER and at least one of the CRIMES. "
        "No dialogue. Keep it safe-for-work. Use the REAL NAME for civilian identity and the ALIAS once."
    )
    return f"{style_line}\nPOWER: {power}\n{crime_line}\nREAL NAME: {real_name}\nALIAS: {alias}\n\n{rules}"

def generate_origin(theme: str, power: str, crimes: List[str], alias: str, real_name: str) -> str:
    prompt = _origin_prompt(theme, power, crimes, alias, real_name)
    set_debug_info(context="Origin", prompt=prompt, max_output_tokens=180, cost_only=False, is_cache_hit=False)
    try:
        resp = _chat_with_retry(
            messages=[
                {"role": "system", "content": "You craft tight, vivid villain origins. Output only the paragraph."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=180,
            temperature=THEME_PROFILES.get(theme, THEME_PROFILES["dark"])["temperature"],
            attempts=2,
        )
        text = (resp.choices[0].message.content or "").strip()
        if power.lower() not in (text or "").lower() or not ensure_crime_mentions_in_origin(text, crimes):
            fix = _chat_with_retry(
                messages=[
                    {"role": "system", "content": "Edit to ensure the paragraph explicitly mentions the power and at least one listed crime. Keep voice; no quotes."},
                    {"role": "user", "content": f"POWER: {power}\nCRIMES: {', '.join(crimes)}\n\nParagraph:\n{text}"},
                ],
                max_tokens=180, temperature=0.2, attempts=1,
            )
            text = (fix.choices[0].message.content or "").strip() or text
        return text
    except Exception:
        return f"{real_name}, now known as {alias}, awakened {power.lower()} and turned to {crimes[0]} after a fateful break. The city learned too late."

# =========================== selection rules ===========================
def select_real_name(gender: str, ai_name_hint: Optional[str] = None) -> str:
    gender = (gender or "nonbinary").strip().lower()
    pool_key = gender if gender in ("male", "female", "nonbinary") else "nonbinary"

    use_list = (random.random() < 0.70)
    if use_list:
        first = _draw_nonrepeating(pool_key, role="first") or "Alex"
        last = _draw_nonrepeating("last", role="last") or "Reed"
        return normalize_real_name(f"{first} {last}")

    raw = (ai_name_hint or "").strip()
    if raw:
        nm = normalize_real_name(raw)
        if len(nm.split()) < 2:
            last = _draw_nonrepeating("last", role="last") or "Reed"
            return normalize_real_name(f"{nm} {last}")
        return nm

    first = _draw_nonrepeating(pool_key, role="first") or "Alex"
    last = _draw_nonrepeating("last", role="last") or "Reed"
    return normalize_real_name(f"{first} {last}")

# =========================== main entry ===========================
def generate_villain(tone: str = "dark", force_new: bool = False):
    """
    POWER-FIRST PIPELINE:
      1) Select power (70% listed / 30% AI-generated).
      2) Provide example crimes for that power family (context only) + HARD BANS/variety constraints.
      3) Ask LLM for the remaining fields AND a fresh crimes[] list tailored to the power.
      4) Normalize/clean crimes (strings only), de‑cliché, and generate the origin.
    """
    theme = (tone or "dark").strip().lower()
    profile = THEME_PROFILES.get(theme, THEME_PROFILES["dark"])

    # ---- Step 1: Power first
    power, power_source = select_power(theme, ai_power_hint=None)

    # ---- Step 2: Crime examples (context only) + bans/variety guidance
    crime_examples = _crime_examples_for_power(power)
    bans_and_style = _crime_bans_and_style(power, theme)

    # ---- Step 3: Build JSON shell prompt (includes crimes[] to be invented)
    preface_lines: List[str] = [
        f"Theme: {theme}",
        f"Tone words: {profile['tone']}.",
        f"Prefer concepts like: {', '.join(profile['encourage'][:8])}.",
    ]
    if profile.get("ban"):
        preface_lines.append(f"Avoid terms like: {', '.join(profile['ban'][:8])}.")
    if theme in ("funny", "satirical"):
        preface_lines.append("Technology is rare; mild gadgets allowed only occasionally.")
    if theme == "chaotic":
        preface_lines.append("Inject one unpredictable chaos quirk in flavor text (not in JSON).")
    lines_block = "\n".join(preface_lines)

    ex_line = "; ".join(crime_examples)
    prompt = f"""
Fill this villain JSON. The POWER is fixed. Use the EXAMPLE CRIMES as inspiration only (do not copy them verbatim).

{lines_block}

POWER: {power}
EXAMPLE CRIMES (inspiration only): {ex_line}

{bans_and_style}

Rules:
- Invent 3–5 unique, power-specific crimes. No duplicates. No generic phrasing.
- Vary targets (people, finance, transit, comms, landmarks). Keep each crime 5–12 words.
- Do NOT reuse the example crimes verbatim; remix or escalate to suit the power.
- Real name is modern FIRST + LAST only (no titles), unrelated to power.
- Gender ∈ ["male","female","nonbinary"]; if unsure, pick one.
- Alias creative and distinct from real name; avoid overused 'dark'/'shadow' unless theme demands it.
- Keep JSON valid and compact. No comments.

Return JSON with keys ONLY:
gender, name, alias, weakness, nemesis, lair, catchphrase, faction, crimes
""".strip()

    set_debug_info(context="Villain Shell (AI crimes)", prompt=prompt, max_output_tokens=360,
                   cost_only=False, is_cache_hit=False)

    resp = _chat_with_retry(
        messages=[{"role": "system", "content": "You are a creative villain generator that returns VALID JSON only."},
                  {"role": "user", "content": prompt}],
        max_tokens=360,
        temperature=profile["temperature"],
        presence_penalty=0.6,
        frequency_penalty=0.7,
        attempts=2,
    )
    txt = (resp.choices[0].message.content or "").strip()
    data = _coerce_json(txt) or _fix_json_with_llm(txt) or {}

    # gender
    gender = (data.get("gender") or "").lower().strip()
    if gender not in {"male", "female", "nonbinary"}:
        gender = "nonbinary"

    # names
    _ensure_bags()
    real_name = select_real_name(gender=gender, ai_name_hint=data.get("name", ""))
    alias = data.get("alias", "Unknown") or "Unknown"

    # crimes: normalize -> de‑cliché -> ensure 3–5
    raw_crimes = data.get("crimes") or []
    # coerce different shapes
    if isinstance(raw_crimes, (str, dict)):
        raw_crimes = [raw_crimes]
    crimes: List[str] = []
    for item in (raw_crimes if isinstance(raw_crimes, list) else []):
        s = _normalize_crime_item(item)
        if s:
            crimes.append(s)
    crimes = _diversify_crimes_after(power, theme, crimes)
    if len(crimes) < 3:
        base = crime_examples[:]
        random.shuffle(base)
        # lightly remix words to avoid exact duplicates
        remix = [re.sub(r"\b(city|cities)\b", "the capital", c, flags=re.I) for c in base[:3]]
        crimes = (crimes + remix)[:5]

    # threat
    computed = classify_threat_from_power(power)
    threat_level = adjust_threat_for_theme(theme, computed, power)

    # origin
    origin = generate_origin(theme=theme, power=power, crimes=crimes, alias=alias, real_name=real_name)
    origin = _normalize_origin_names(origin, real_name, alias)

    result = {
        "name": real_name,
        "alias": alias,
        "power": power,
        "weakness": data.get("weakness", "Unknown"),
        "nemesis": data.get("nemesis", "Unknown"),
        "lair": data.get("lair", "Unknown"),
        "catchphrase": data.get("catchphrase", "Unknown"),
        "crimes": crimes,
        "threat_level": threat_level,
        "faction": data.get("faction", "Unknown"),
        "origin": origin,
        "gender": gender,
        "theme": theme,
        "power_source": power_source,  # "listed" or "ai"
    }
    return result

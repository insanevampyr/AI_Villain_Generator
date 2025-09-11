# config.py
import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# --- Uber Tier Feature Flag ---
# Default OFF; can be enabled by env VILLAINS_ENABLE_UBER=true
# Also allows a temporary in-process override via set_uber_enabled_runtime(True)
_ENABLE_UBER_DEFAULT = False

# Runtime flip (dev-only) that lasts until process restart.
# DevDash will call set_uber_enabled_runtime(True/False).
_UBER_ENABLED_RUNTIME = None  # None means "no override, use env/default"

def is_uber_enabled() -> bool:
    """
    Returns whether Uber tier is enabled.
    Priority: runtime override (if set) -> env var -> default.
    """
    global _UBER_ENABLED_RUNTIME
    if _UBER_ENABLED_RUNTIME is not None:
        return bool(_UBER_ENABLED_RUNTIME)

    raw = os.getenv("VILLAINS_ENABLE_UBER", "").strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    return _ENABLE_UBER_DEFAULT

def set_uber_enabled_runtime(value: bool) -> None:
    """
    Dev-only: flip Uber on/off at runtime. Persisting this for production
    will be done later (e.g., write to .env or a small KV file).
    """
    global _UBER_ENABLED_RUNTIME
    _UBER_ENABLED_RUNTIME = bool(value)

def get_theme_description(theme_key: str) -> str:
    """
    Return a short description for a theme. If not present, fall back to:
    'Tier: <tier> • <N> powers'
    """
    key = (theme_key or "").strip().lower()
    for t in COMPENDIUM.get("themes", []):
        if (t.get("key") or "").strip().lower() == key:
            desc = (t.get("description") or "").strip()
            if desc:
                return desc
            powers = t.get("powers") or []
            tier = (t.get("tier") or "core").strip().lower()
            return f"Tier: {tier.title()} • {len(powers)} powers"
    return "Theme details unavailable"


# ===== App / Model Settings =====
APP_NAME = os.getenv("APP_NAME", "AI Villain Generator")
OPENAI_MODEL_NAME  = os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini")
OPENAI_IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "dall-e-3")
OPENAI_IMAGE_SIZE  = os.getenv("OPENAI_IMAGE_SIZE", "1024x1024")
APP_URL = os.getenv("APP_URL", "https://ai-villain-generator.streamlit.app")
DEFAULT_SHARE_TEXT = os.getenv("DEFAULT_SHARE_TEXT", "I just made a villain with #AIVillains — try it:")


# ===== Power Compendium =====
COMPENDIUM = {
    "themes": [
        # ---------- CORE THEMES ----------
        {
            "key": "elemental",            # must match a style key shown in your app’s theme dropdown
            "name": "Elemental / Nature",
            "tier": "core",                # "core" or "uber"
            "powers": [
                # EXAMPLE: copy from your doc (Pyrokinesis)
                {
                    "name": "Pyrokinesis",
                    "aka": "Fire Control",             # optional
                    "description": "Control and generate fire.",
                    "threat_levels": {
                        "Laughably Low": "Light matches, scorch walls.",
                        "Moderate": "Burn homes, melt locks.",
                        "High": "Torch city blocks, create firestorms.",
                        "Extreme": "Ignite wildfires, engulf cities."
                    },
                    "crimes": ["Arson", "Intimidation by fire", "Destroying evidence"]
                },
                {
                    "name": "Hydrokinesis",
                    "aka": "Water Control",   # optional; delete line if none
                    "description": "Control and shape water.",
                    "threat_levels": {
                        "Laughably Low": "Spill cups, burst pipes.",      # OMIT this line for Uber powers
                        "Moderate": "Flood homes, drown targets.",
                        "High": "Capsize ships, destroy bridges.",
                        "Extreme": "Summon tsunamis."
                    },
                    "crimes": ["Flood vaults", "Sink evidence", "Sabotage ports"]
                },
                {
                    "name": "Terrakinesis",
                    "aka": "Earth Control",   # optional; delete line if none
                    "description": "Move and reshape earth and stone.",
                    "threat_levels": {
                        "Laughably Low": "Toss rocks, crack pavement.",      # OMIT this line for Uber powers
                        "Moderate": "Open sinkholes, bury cars.",
                        "High": "Level buildings, split highways.",
                        "Extreme": "Trigger citywide quakes."
                    },
                    "crimes": ["Tunnel heists", "Collapse government buildings", "Trap police"]
                },
                {
                    "name": "Aerokinesis",
                    "aka": "Air Control",   # optional; delete line if none
                    "description": "Manipulate air pressure and wind.",
                    "threat_levels": {
                        "Laughably Low": "Knock over papers.",      # OMIT this line for Uber powers
                        "Moderate": "Push crowds, disrupt vehicles.",
                        "High": "Rip roofs, create tornadoes.",
                        "Extreme": "Suck oxygen from entire sectors."
                    },
                    "crimes": ["Suffocation", "Storm extortion", "Crash aircraft"]
                },
                {
                    "name": "Cryokinesis",
                    "aka": "Ice Control",   # optional; delete line if none
                    "description": "Create and manipulate ice and cold.",
                    "threat_levels": {
                        "Laughably Low": "Frost glass.",      # OMIT this line for Uber powers
                        "Moderate": "Freeze locks, immobilize guards.",
                        "High": "Freeze rivers, paralyze squads.",
                        "Extreme": "Flash-freeze city blocks."
                    },
                    "crimes": ["Freeze vaults", "Disable vehicles", "Trap civilians"]
                },
                {
                    "name": "Plant Manipulation",
                    "description": "Accelerate growth and command plants.",
                    "threat_levels": {
                        "Laughably Low": "Trip people with vines.",      # OMIT this line for Uber powers
                        "Moderate": "Bind guards, grow barriers.",
                        "High": "Choke districts with jungle growth.",
                        "Extreme": "Cities consumed by forests."
                    },
                    "crimes": ["Ambushes", "Eco-terror", "Block highways"]
                },
                {
                    "name": "Sand/Dust Control",
                    "description": "Command sand and particulates as weapons and cover.",
                    "threat_levels": {
                        "Laughably Low": "Blind individuals.",      # OMIT this line for Uber powers
                        "Moderate": "Sandblast vehicles.",
                        "High": "Suffocate crowds.",
                        "Extreme": "Bury cities in dunes."
                    },
                    "crimes": ["Ambushes", "Destroy evidence in storms", "Smother evacuations"]
                },
                {
                    "name": "Storm Calling",
                    "description": "Summon and direct thunder, rain, and winds.",
                    "threat_levels": {
                        "Laughably Low": "Static shocks.",      # OMIT this line for Uber powers
                        "Moderate": "Direct lightning strikes.",
                        "High": "Blackouts, rolling thunderstorms.",
                        "Extreme": "Summon super-hurricanes."
                    },
                    "crimes": ["Government blackmail via storms", "Grid sabotage", "Maritime extortion"]
                },
                {
                    "name": "Volcanic/Magma Control",
                    "description": "Manipulate lava and geothermal forces.",
                    "threat_levels": {
                        "Laughably Low": "Melt small surfaces.",      # OMIT this line for Uber powers
                        "Moderate": "Release lava flows.",
                        "High": "Flood neighborhoods with magma.",
                        "Extreme": "Trigger volcanic eruptions."
                    },
                    "crimes": ["Destroy bunkers", "Extort cities with eruptions", "Incinerate evidence depots"]
                },
                {
                    "name": "Weather Manipulation",
                    "description": "Broadly alter weather patterns.",
                    "threat_levels": {
                        "Laughably Low": "Cause drizzle or fog.",      # OMIT this line for Uber powers
                        "Moderate": "Hailstorms, dense fog for cover.",
                        "High": "Droughts, blizzards, tornadoes.",
                        "Extreme": "Reshape global climates."
                    },
                    "crimes": ["Conceal crimes", "Cause economic collapse", "Disrupt agriculture at scale"]
                }           
            ]
        },
        {
            "key": "energy",
            "name": "Energy & Physics",
            "tier": "core",
            "powers": [
                {
                    "name": "Electrokinesis",
                    "aka": "Electricity Control",             # optional
                    "description": "Generate and direct electricity.",
                    "threat_levels": {
                        "Laughably Low": "Static zaps.",
                        "Moderate": "Short out electronics.",
                        "High": "Blackout cities.",
                        "Extreme": "Electrocute entire grids."
                    },
                    "crimes": ["Disable alarms", "Torture victims", "Destroy communications"]
                },
                {
                    "name": "Magnetism Control",
                    "aka": "Magnetic Field Manipulation",             # optional
                    "description": "Manipulate magnetic fields to move or deform metals.",
                    "threat_levels": {
                        "Laughably Low": "Bend nails.",
                        "Moderate": "Rip weapons away.",
                        "High": "Derail trains.",
                        "Extreme": "Move skyscrapers."
                    },
                    "crimes": ["Disarm cops", "Crack safes", "Collapse bridges"]
                },
                {
                    "name": "Gravity Manipulation",
                    "description": "Increase, decrease, or redirect gravitational forces.",
                    "threat_levels": {
                        "Laughably Low": "Make objects heavier.",
                        "Moderate": "Pin enemies down.",
                        "High": "Crush vehicles.",
                        "Extreme": "Reverse gravity city-wide."
                    },
                    "crimes": ["Ground aircraft", "Smash vaults", "Crush-response tactics"]
                },
                {
                    "name": "Sonic Manipulation",
                    "description": "Project and shape destructive sound waves.",
                    "threat_levels": {
                        "Laughably Low": "Ringing noises.",
                        "Moderate": "Shatter glass.",
                        "High": "Collapse tunnels.",
                        "Extreme": "Flatten armies with waves."
                    },
                    "crimes": ["Riot-inducing blasts", "Sonic heists", "Perimeter denial"]
                },
                {
                    "name": "Radiation Emission",
                    "description": "Emit harmful ionizing radiation.",
                    "threat_levels": {
                        "Laughably Low": "Mild nausea.",
                        "Moderate": "Poison blocks.",
                        "High": "Melt armored vehicles.",
                        "Extreme": "Render cities uninhabitable."
                    },
                    "crimes": ["Radiation blackmail", "Assassination", "Contaminate facilities"]
                },
                {
                    "name": "Kinetic Absorption",
                    "description": "Absorb and redirect kinetic energy.",
                    "threat_levels": {
                        "Laughably Low": "Absorb punches.",
                        "Moderate": "Redirect bullets.",
                        "High": "Tank grenades.",
                        "Extreme": "Absorb city-shaking blasts."
                    },
                    "crimes": ["Unstoppable robberies", "Counterattack mayhem", "Siege tanking"]
                },
                {
                    "name": "Force Fields",
                    "description": "Create protective barriers and domes.",
                    "threat_levels": {
                        "Laughably Low": "Bubble shields.",
                        "Moderate": "Block bullets.",
                        "High": "Tank missiles.",
                        "Extreme": "Dome over cities."
                    },
                    "crimes": ["Shield hideouts", "Fortify gangs", "Block law enforcement"]
                },
                {
                    "name": "Plasma Control",
                    "description": "Form and launch superheated plasma.",
                    "threat_levels": {
                        "Laughably Low": "Glow faintly.",
                        "Moderate": "Burn holes in steel.",
                        "High": "Launch plasma bombs.",
                        "Extreme": "Vaporize skyscrapers."
                    },
                    "crimes": ["Meltdown terror", "Plasma extortion", "Industrial sabotage"]
                },
                {
                    "name": "Friction Manipulation",
                    "description": "Increase or remove friction on demand.",
                    "threat_levels": {
                        "Laughably Low": "Make floors slippery or sticky.",
                        "Moderate": "Halt cars.",
                        "High": "Immobilize crowds.",
                        "Extreme": "Freeze entire districts."
                    },
                    "crimes": ["Road disasters", "Mass immobilization", "Facility shutdowns"]
                },
                {
                    "name": "Nuclear Detonation",
                    "description": "Generate localized nuclear-level explosions.",
                    "threat_levels": {
                        "Laughably Low": "Small blasts.",
                        "Moderate": "Level buildings.",
                        "High": "Flatten city blocks.",
                        "Extreme": "Nuclear-scale explosions."
                    },
                    "crimes": ["Doomsday blackmail", "Catastrophic terror", "Erasure of evidence"]
                }
            ]
        },
        {
            "key": "biological",
            "name": "Biological / Mutation",
            "tier": "core",
            "powers": [
                {
                    "name": "Super Strength",
                    "description": "Perform feats of overwhelming physical power.",
                    "threat_levels": {
                        "Laughably Low": "Lift furniture.",
                        "Moderate": "Smash vaults.",
                        "High": "Toss tanks.",
                        "Extreme": "Collapse skyscrapers."
                    },
                    "crimes": ["Smash-and-grab heists", "Terror raids", "Breach fortified sites"]
                },
                {
                    "name": "Regeneration",
                    "description": "Rapidly heal from wounds and damage.",
                    "threat_levels": {
                        "Laughably Low": "Heal cuts.",
                        "Moderate": "Recover from bullets.",
                        "High": "Survive explosions.",
                        "Extreme": "Near-immortal."
                    },
                    "crimes": ["Survive raids", "Frontline boss", "Ignore imprisonment"]
                },
                {
                    "name": "Shapeshifting",
                    "description": "Alter appearance or form at will.",
                    "threat_levels": {
                        "Laughably Low": "Change hair.",
                        "Moderate": "Copy faces.",
                        "High": "Mimic anyone.",
                        "Extreme": "Become monsters."
                    },
                    "crimes": ["Infiltration", "Impersonation", "Image assassinations"]
                },
                {
                    "name": "Animal Control",
                    "description": "Command animals and swarms.",
                    "threat_levels": {
                        "Laughably Low": "Cats or rats.",
                        "Moderate": "Swarms of birds.",
                        "High": "Wolves, predators.",
                        "Extreme": "Ecosystem domination."
                    },
                    "crimes": ["Swarm assassins", "Animal armies", "Sabotage with pests"]
                },
                {
                    "name": "Poisonous Physiology",
                    "description": "Produce toxins through skin, breath, or blood.",
                    "threat_levels": {
                        "Laughably Low": "Mild stings.",
                        "Moderate": "Deadly touch.",
                        "High": "Airborne poison.",
                        "Extreme": "City-level plagues."
                    },
                    "crimes": ["Poison leaders", "Contaminate water", "Toxic extortion"]
                },
                {
                    "name": "Elasticity",
                    "description": "Stretch, compress, and deform the body.",
                    "threat_levels": {
                        "Laughably Low": "Stretch arms.",
                        "Moderate": "Slither into vents.",
                        "High": "Crush cops.",
                        "Extreme": "Envelop entire squads."
                    },
                    "crimes": ["Infiltration", "Ambushes", "Contain targets"]
                },
                {
                    "name": "Claws & Fangs",
                    "description": "Natural weapons capable of shredding armor and steel.",
                    "threat_levels": {
                        "Laughably Low": "Scratch.",
                        "Moderate": "Rip armor.",
                        "High": "Slice cars.",
                        "Extreme": "Shred fortresses."
                    },
                    "crimes": ["Assassination", "Mutilation terror", "High-value hits"]
                },
                {
                    "name": "Camouflage",
                    "description": "Blend into surroundings or vanish from sight.",
                    "threat_levels": {
                        "Laughably Low": "Blend in shadows.",
                        "Moderate": "Hide from sight.",
                        "High": "Full invisibility.",
                        "Extreme": "Shared Invisibility or Invisible Areas"
                    },
                    "crimes": ["Spy work", "Stealth murders", "Hidden bases"]
                },
                {
                    "name": "Insectoid Mutation",
                    "description": "Develop insect-like traits and bioweapons.",
                    "threat_levels": {
                        "Laughably Low": "Small limbs.",
                        "Moderate": "Hardened shell.",
                        "High": "Acid spit.",
                        "Extreme": "Hive overlord."
                    },
                    "crimes": ["Bio-terror", "Swarm control", "Acid attacks"]
                },
                {
                    "name": "Venom Breath",
                    "description": "Exhale toxic or corrosive clouds.",
                    "threat_levels": {
                        "Laughably Low": "Foul air.",
                        "Moderate": "Choke groups.",
                        "High": "Suffocate crowds.",
                        "Extreme": "Poison city sectors."
                    },
                    "crimes": ["Silent assassinations", "Extortion", "Area denial"]
                }
            ]   # close Biological powers
        },     # close Biological theme

        {
            "key": "psychic",
            "name": "Psychic & Mental",
            "tier": "core",
            "powers": [
                {
                    "name": "Telepathy",
                    "description": "Read and influence minds.",
                    "threat_levels": {
                        "Laughably Low": "Read surface thoughts, unfocused.",
                        "Moderate": "Read intentions.",
                        "High": "Extract memories.",
                        "Extreme": "Rewrite personalities."
                    },
                    "crimes": ["Force confessions", "Blackmail secrets", "Erase witnesses"]
                },
                {
                    "name": "Telekinesis",
                    "description": "Move and crush objects with the mind.",
                    "threat_levels": {
                        "Laughably Low": "Move pencils.",
                        "Moderate": "Yank weapons away.",
                        "High": "Crush vehicles.",
                        "Extreme": "Flatten skyscrapers."
                    },
                    "crimes": ["Remote theft", "Large-scale destruction", "Weaponize debris"]
                },
                {
                    "name": "Illusion Casting",
                    "description": "Project convincing illusions and false realities.",
                    "threat_levels": {
                        "Laughably Low": "Minor distractions.",
                        "Moderate": "Disguise identities.",
                        "High": "Create false realities.",
                        "Extreme": "Trap entire cities in illusions."
                    },
                    "crimes": ["Conceal heists", "Psychological warfare", "Mass panic"]
                },
                {
                    "name": "Fear Projection",
                    "description": "Induce fear and panic directly in targets.",
                    "threat_levels": {
                        "Laughably Low": "Startle individuals.",
                        "Moderate": "Induce panic attacks.",
                        "High": "Drive crowds insane.",
                        "Extreme": "Collapse cities with terror."
                    },
                    "crimes": ["Riot inducement", "Hostage control", "Citywide intimidation"]
                }
            ]   # close Psychic powers
        },     # close Psychic theme

        {
            "key": "chemical",            # must match a style key shown in your app’s theme dropdown
            "name": "Chemical / Corruptive",
            "tier": "core",                # "core" or "uber"
            "powers": [
                {
                    "name": "Toxin Mastery",
                    "description": "Create, refine, and deploy poisons/gases.",
                    "threat_levels": {
                        "Laughably Low": "Poison small food/drinks.",
                        "Moderate": "Gas enclosed areas.",
                        "High": "Biohazard bomb deployment.",
                        "Extreme": "Citywide contamination."
                    },
                    "crimes": ["Assassinations", "Extortion via poisoning", "Area denial"]
                },
                {
                    "name": "Acid Projection",
                    "description": "Excrete or launch corrosive acids.",
                    "threat_levels": {
                        "Laughably Low": "Burn paper/surfaces.",
                        "Moderate": "Melt locks and safes.",
                        "High": "Dissolve vehicles and barriers.",
                        "Extreme": "Erode skyscrapers and bridges."
                    },
                    "crimes": ["Vault penetration", "Destructive sabotage", "Building destruction"]
                },
                {
                    "name": "Disease Control",
                    "description": "Engineer and spread pathogens.",
                    "threat_levels": {
                        "Laughably Low": "Spread mild illness.",
                        "Moderate": "Targeted outbreaks.",
                        "High": "Regional epidemics.",
                        "Extreme": "Global pandemics."
                    },
                    "crimes": ["Bio-warfare", "Mass extortion", "Government building shutdowns"]
                },
                {
                    "name": "Corrosive Touch",
                    "description": "Corrode matter on contact.",
                    "threat_levels": {
                        "Laughably Low": "Rust small items.",
                        "Moderate": "Break chains/doors.",
                        "High": "Melt vehicles.",
                        "Extreme": "Reduce structures to slag."
                    },
                    "crimes": ["Destroy evidence", "Sabotage and terror", "Disfigurements"]
                },
                {
                    "name": "Venom Spitting",
                    "description": "Projected toxins from the mouth.",
                    "threat_levels": {
                        "Laughably Low": "Irritate skin/eyes.",
                        "Moderate": "Blind/disable guards.",
                        "High": "Instantly lethal sprays.",
                        "Extreme": "Street-wide venom coverage."
                    },
                    "crimes": ["Silent assassinations", "Area suppression", "Blinding justice officials"]
                },
                {
                    "name": "Chemical Alchemy",
                    "description": "Transmute common materials into chemicals/explosives.",
                    "threat_levels": {
                        "Laughably Low": "Minor chemical tricks.",
                        "Moderate": "On-demand explosives/solvents.",
                        "High": "Recreate banned WMDs.",
                        "Extreme": "Reshape matter into toxins at scale."
                    },
                    "crimes": ["Bomb-making", "Industrial sabotage", "Turning government buildings into toxic gas emission zones"]
                },
                {
                    "name": "Pollution Generation",
                    "description": "Emit hazardous smog and waste.",
                    "threat_levels": {
                        "Laughably Low": "Bad odors/smog.",
                        "Moderate": "Smog whole blocks.",
                        "High": "Poison rivers/harbors.",
                        "Extreme": "Render cities unlivable."
                    },
                    "crimes": ["Environmental terrorism", "Economic sabotage", "Area denial"]
                },
                {
                    "name": "Neurotoxin Release",
                    "description": "Spread nerve agents that impair function.",
                    "threat_levels": {
                        "Laughably Low": "Dizziness/disorientation.",
                        "Moderate": "Paralysis in targets.",
                        "High": "Permanent brain damage.",
                        "Extreme": "Erase higher brain function citywide."
                    },
                    "crimes": ["Subdue resistance", "Mass blackmail via toxin threats", "Official assassination"]
                },
                {
                    "name": "Flammable Gas Generation",
                    "description": "Exude/seed explosive gases.",
                    "threat_levels": {
                        "Laughably Low": "Small flammable puffs.",
                        "Moderate": "Fill rooms for ignition.",
                        "High": "Explode entire blocks.",
                        "Extreme": "Blanket sectors in explosive haze."
                    },
                    "crimes": ["Firestorm extortion", "Coordinated detonations","Resident removal"]
                },
                {
                    "name": "Parasitic Infection",
                    "description": "Breed/control parasites that inhabit hosts.",
                    "threat_levels": {
                        "Laughably Low": "Minor sickness.",
                        "Moderate": "Control individuals.",
                        "High": "Hive-mind spread.",
                        "Extreme": "Enslave cities biologically."
                    },
                    "crimes": ["Infiltration via hosts", "Cult-like mass control", "Population control"]
                }
            ]   # close Chemical / Corruptive powers
        },     # close Chemical / Corruptive theme
        {
            "key": "chaos",            # must match a style key shown in your app’s theme dropdown
            "name": "Chaos & Trickery",
            "tier": "core",                # "core" or "uber"
            "powers": [
                {
                    "name": "Probability Manipulation",
                    "description": "Tilt odds to favorable outcomes.",
                    "threat_levels": {
                        "Laughably Low": "Win small bets.",
                        "Moderate": "Guns jam/guards stumble.",
                        "High": "Opponents continually fail.",
                        "Extreme": "Armies undone by impossible bad luck."
                    },
                    "crimes": ["Rig casinos", "Flawless heists", "Sabotage operations"]
                },
                {
                    "name": "Luck Theft",
                    "description": "Drain good fortune from targets.",
                    "threat_levels": {
                        "Laughably Low": "Victims trip.",
                        "Moderate": "Rivals suffer accidents.",
                        "High": "Systems catastrophically fail.",
                        "Extreme": "Citywide fortune collapse."
                    },
                    "crimes": ["Gambling rackets", "Industrial sabotage", "Unlucky criminal investigators"]
                },
                {
                    "name": "Trick Gadgets",
                    "description": "Weaponized toys/props and deceptive devices.",
                    "threat_levels": {
                        "Laughably Low": "Exploding gum.",
                        "Moderate": "Acid toys/smoke balloons.",
                        "High": "Hidden bombs as gifts.",
                        "Extreme": "Weaponized carnivals/streets."
                    },
                    "crimes": ["Disguised assassinations", "Themed heists", "Changing important items into oversized props"]
                },
                {
                    "name": "Chaos Magic",
                    "description": "Unpredictable reality tweaks and glitches.",
                    "threat_levels": {
                        "Laughably Low": "Random pranks.",
                        "Moderate": "Disrupt tech.",
                        "High": "Alter battle outcomes.",
                        "Extreme": "Break physical laws unpredictably."
                    },
                    "crimes": ["Untraceable sabotage", "Riot creation", "Undoing scientific studies & discoveries"]
                },
                {
                    "name": "Trickster Disguise",
                    "description": "Extreme deception tactics and mimicry.",
                    "threat_levels": {
                        "Laughably Low": "Passable masks.",
                        "Moderate": "Fool security teams.",
                        "High": "Replace officials.",
                        "Extreme": "Collapse trust in leadership."
                    },
                    "crimes": ["Political infiltration", "False flag operations", "Officials becoming untrustable"]
                },
                {
                    "name": "Confetti Bombs",
                    "description": "Festive munitions with hidden effects.",
                    "threat_levels": {
                        "Laughably Low": "Harmless pop.",
                        "Moderate": "Blinding bursts.",
                        "High": "Explosives disguised as fun.",
                        "Extreme": "Block bombing disguised as celebration."
                    },
                    "crimes": ["Public chaos", "Crowd-targeted attacks", "Changing a serious matter into a laugh riot"]
                },
                {
                    "name": "Shadow Duplicates",
                    "description": "Create illusory or semi-solid copies.",
                    "threat_levels": {
                        "Laughably Low": "One decoy.",
                        "Moderate": "Dozens of copies.",
                        "High": "Armies of shadows.",
                        "Extreme": "Endless tide of attackers."
                    },
                    "crimes": ["Overwhelm responders", "Confuse defenders", "Attacks in numbers"]
                },
                {
                    "name": "Card Tricks",
                    "description": "Weaponized playing cards and sleight-of-hand.",
                    "threat_levels": {
                        "Laughably Low": "Harmless flicks.",
                        "Moderate": "Razor throws.",
                        "High": "Explosive decks.",
                        "Extreme": "Card storms that slice structures."
                    },
                    "crimes": ["Flashy assassinations", "Signature heists", "Card gambling crimes"]
                },
                {
                    "name": "Misdirection Mastery",
                    "description": "Expert distraction, feints, and decoys.",
                    "threat_levels": {
                        "Laughably Low": "Distract one guard.",
                        "Moderate": "Fool squads.",
                        "High": "Turn allies against each other.",
                        "Extreme": "Confuse entire armies."
                    },
                    "crimes": ["Bank escapes", "Divide-and-conquer robberies", "Stock market manipulation"]
                },
                {
                    "name": "Trickster’s Escape",
                    "description": "Inescapability via deception and stunts.",
                    "threat_levels": {
                        "Laughably Low": "Slip cuffs.",
                        "Moderate": "Vanish with smoke.",
                        "High": "Escape max-security prisons.",
                        "Extreme": "Evade unrealistic-level restraints."
                    },
                    "crimes": ["Uncatchable fugitive acts", "Serial escape artistry", "Debt evasion"]
                }
            ]   # close Chaos & Trickery powers
        },     # close Chaos & Trickery theme
        {
            "key": "satirical",            # must match a style key shown in your app’s theme dropdown
            "name": "Satirical / Funny",
            "tier": "core",                # "core" or "uber"
            "powers": [
                {
                    "name": "Exploding Rubber Chickens",
                    "description": "Prank props escalating into lethal devices.",
                    "threat_levels": {
                        "Laughably Low": "Harmless squeaks.",
                        "Moderate": "Stun grenades.",
                        "High": "Acid/explosive fillings.",
                        "Extreme": "Citywide chicken storm."
                    },
                    "crimes": ["Humiliation assassinations", "Disguised bomb heists", "Shipping & transportation chaos"]
                },
                {
                    "name": "Joy Buzzer of Doom",
                    "description": "Handshake shocker from prank to lethal.",
                    "threat_levels": {
                        "Laughably Low": "Mild shocks.",
                        "Moderate": "Knockout jolt.",
                        "High": "Instant lethal surge.",
                        "Extreme": "Shockwave through crowds."
                    },
                    "crimes": ["Handshake assassinations", "Crowd control", "Killing the vibes of parties"]
                },
                {
                    "name": "Banana Peel Mastery",
                    "description": "Slapstick slicks causing chaos.",
                    "threat_levels": {
                        "Laughably Low": "Single slip gag.",
                        "Moderate": "Vehicle crashes.",
                        "High": "Armies collapse.",
                        "Extreme": "Streets become chaos zones."
                    },
                    "crimes": ["Public humiliation ops", "Traffic sabotage", "City incapacitation"]
                },
                {
                    "name": "Meme Manipulation",
                    "description": "Weaponize virality and memetics.",
                    "threat_levels": {
                        "Laughably Low": "Alter billboards.",
                        "Moderate": "Force officials into memes.",
                        "High": "Citywide frenzy.",
                        "Extreme": "Meme riots topple governments."
                    },
                    "crimes": ["Reputation sabotage", "Info-warfare", "Misinformation"]
                },
                {
                    "name": "Lethal Custard Pies",
                    "description": "Pastry projectiles with payloads.",
                    "threat_levels": {
                        "Laughably Low": "Harmless splats.",
                        "Moderate": "Acid fillings.",
                        "High": "Explosive desserts.",
                        "Extreme": "Custard bombardment."
                    },
                    "crimes": ["Food-themed terror", "Signature assassinations", "Deli disasters"]
                },
                {
                    "name": "Comedy Minions",
                    "description": "Clownish henchmen escalating to armies.",
                    "threat_levels": {
                        "Laughably Low": "Slapstick goons.",
                        "Moderate": "Armed clowns.",
                        "High": "Explosive circus gangs.",
                        "Extreme": "Carnival armies overwhelm cities."
                    },
                    "crimes": ["Circus takeovers", "Mass distraction raids", "Comedic takeovers"]
                },
                {
                    "name": "Karaoke Torture",
                    "description": "Weaponized music and cringe.",
                    "threat_levels": {
                        "Laughably Low": "Bad singing.",
                        "Moderate": "Deafen guards.",
                        "High": "Cause riots.",
                        "Extreme": "Hypnotize cities via songs."
                    },
                    "crimes": ["Hostage control", "Public disruption", "Party crashing"]
                },
                {
                    "name": "Rubber Body",
                    "description": "Cartoon elasticity for slapstick and captures.",
                    "threat_levels": {
                        "Laughably Low": "Bouncy pratfalls.",
                        "Moderate": "Ricochet bullets.",
                        "High": "Crush vehicles.",
                        "Extreme": "Envelop squads as traps."
                    },
                    "crimes": ["Surprise ambushes", "Infiltration", "Area denial"]
                },
                {
                    "name": "Gas of Giggles",
                    "description": "Laugh-inducing gas.",
                    "threat_levels": {
                        "Laughably Low": "Fit of giggles.",
                        "Moderate": "Disable squads.",
                        "High": "Suffocation from hysterics.",
                        "Extreme": "Citywide laugh riots."
                    },
                    "crimes": ["Riot control", "Mass disruption", "Jokes that go on forever"]
                },
                {
                    "name": "Clown Car Summoning",
                    "description": "Summon improbably packed vehicles of goons.",
                    "threat_levels": {
                        "Laughably Low": "One car, many henchmen.",
                        "Moderate": "Endless thugs.",
                        "High": "Clown tanks.",
                        "Extreme": "Infinite carnival army."
                    },
                    "crimes": ["Overwhelm responders", "Flash-mob takeovers", "Circus-themed robberies"]
                }
            ]   # close Satirical / Funny powers
        },     # close Satirical / Funny theme
        {
            "key": "tragic",            # must match a style key shown in your app’s theme dropdown
            "name": "Tragic",
            "tier": "core",                # "core" or "uber"
            "powers": [
                {
                    "name": "Sorrow Aura",
                    "description": "Radiate grief that crushes will.",
                    "threat_levels": {
                        "Laughably Low": "Mild sadness.",
                        "Moderate": "Crush morale; induce surrender.",
                        "High": "Crowds collapse in despair.",
                        "Extreme": "Cities riot in hopelessness."
                    },
                    "crimes": ["Psychological warfare", "Surrender extortion", "Cries if they want to at parties"]
                },
                {
                    "name": "Ghostly Manifestation",
                    "description": "Summon/command apparitions of the dead.",
                    "threat_levels": {
                        "Laughably Low": "Harmless specters.",
                        "Moderate": "Fighting phantoms.",
                        "High": "Graveyards rise to serve.",
                        "Extreme": "Armies of spirits enslave cities."
                    },
                    "crimes": ["Terror campaigns", "Supernatural extortion", "Location hauntings"]
                },
                {
                    "name": "Cursed Form",
                    "description": "Power fueled by self-harm/decay.",
                    "threat_levels": {
                        "Laughably Low": "Sickly yet resilient.",
                        "Moderate": "Unstable mutations grant strength.",
                        "High": "Monstrous battle forms.",
                        "Extreme": "Apocalyptic self-destruction potential."
                    },
                    "crimes": ["Suicidal raids", "Shock assaults", "Predilection plans & projects"]
                },
                {
                    "name": "Remorse Projection",
                    "description": "Force victims to relive worst regrets.",
                    "threat_levels": {
                        "Laughably Low": "Twinges of regret.",
                        "Moderate": "Overwhelm leaders with guilt.",
                        "High": "Cities spiral into breakdown.",
                        "Extreme": "Nations collapse under shared remorse."
                    },
                    "crimes": ["Manipulate courts", "Break leadership resolve", "Manipulate stock markets"]
                },
                {
                    "name": "Sacrificial Power",
                    "description": "Gain power from sacrifice and loss.",
                    "threat_levels": {
                        "Laughably Low": "Small boosts from minor injuries.",
                        "Moderate": "Strength through kills/rituals.",
                        "High": "Cult offerings fuel immense power.",
                        "Extreme": "Mass death grants godlike might."
                    },
                    "crimes": ["Ritual murders", "Cult-driven offensives", "Torture"]
                },
                {
                    "name": "Loneliness Embodiment",
                    "description": "Drain warmth, hope, and connection.",
                    "threat_levels": {
                        "Laughably Low": "Chill a room’s mood.",
                        "Moderate": "Spread isolation across blocks.",
                        "High": "Cities fall into despair.",
                        "Extreme": "Erase collective hope entirely."
                    },
                    "crimes": ["Break communities", "Paralyze resistance", "Fundraising failures from lack of hope"]
                },
                {
                    "name": "Blood Curse",
                    "description": "Hex bloodlines with misfortune/weakness.",
                    "threat_levels": {
                        "Laughably Low": "Minor hexes.",
                        "Moderate": "Doom family lines.",
                        "High": "Curse entire clans/regions.",
                        "Extreme": "Generational suffering across nations."
                    },
                    "crimes": ["Extortion via hereditary curses", "Long-term coercion", "Hero hexing"]
                },
                {
                    "name": "Mourning Chains",
                    "description": "Bind with spectral chains of grief.",
                    "threat_levels": {
                        "Laughably Low": "Slow movements.",
                        "Moderate": "Immobilize squads.",
                        "High": "Imprison armies.",
                        "Extreme": "Cities locked in grief prisons."
                    },
                    "crimes": ["Mass detainment", "Hostage territories", "Armies and cities deadlocked"]
                },
                {
                    "name": "Eternal Wound",
                    "description": "Inflict injuries that refuse to heal.",
                    "threat_levels": {
                        "Laughably Low": "Symbolic scar.",
                        "Moderate": "Never-healing wounds.",
                        "High": "Crippling injuries to forces.",
                        "Extreme": "Regions unable to recover."
                    },
                    "crimes": ["Cripple response forces", "Long-term suppression", "Unleashing hell in hospitals"]
                },
                {
                    "name": "Tear Fuel",
                    "description": "Grow stronger from grief and mourning.",
                    "threat_levels": {
                        "Laughably Low": "Power from a single tear.",
                        "Moderate": "Feed on community grief.",
                        "High": "Draw strength from mass funerals.",
                        "Extreme": "Invincible amid citywide mourning."
                    },
                    "crimes": ["Terror to harvest grief", "Extortion through tragedy", "Collecting grief collectives"]
                }
            ]   # close Tragic powers
        },     # close Tragic theme
        {
            "key": "magical",            # must match a style key shown in your app’s theme dropdown
            "name": "Fantasy / Magical",
            "tier": "core",                # "core" or "uber"
            "powers": [
                {
                    "name": "Dark Sorcery",
                    "description": "Channel occult power for destructive spells.",
                    "threat_levels": {
                        "Laughably Low": "Parlor tricks.",
                        "Moderate": "Summon shadows/hexes.",
                        "High": "Devastating curses and blasts.",
                        "Extreme": "Apocalyptic rituals."
                    },
                    "crimes": ["Cult leadership", "Ritual killings", "Arcane extortion"]
                },
                {
                    "name": "Necromancy",
                    "description": "Animate and command the dead.",
                    "threat_levels": {
                        "Laughably Low": "Skeletons briefly animate.",
                        "Moderate": "Raise corpses as soldiers.",
                        "High": "Army of undead marches.",
                        "Extreme": "Nations enslaved to death."
                    },
                    "crimes": ["Undead gangs", "City seizures", "Shock-and-awe sieges"]
                },
                {
                    "name": "Blood Magic",
                    "description": "Use blood as a power source.",
                    "threat_levels": {
                        "Laughably Low": "Minor self-cuts empower spells.",
                        "Moderate": "Ritual sacrifices for strength.",
                        "High": "Cult-wide empowerment.",
                        "Extreme": "Drain cities to cast world-scale spells."
                    },
                    "crimes": ["Sacrificial cults", "Blood rite extortion", "Blood baths"]
                },
                {
                    "name": "Curse Casting",
                    "description": "Place lasting maledictions on targets.",
                    "threat_levels": {
                        "Laughably Low": "Petty bad luck.",
                        "Moderate": "Crippling long curses.",
                        "High": "Village-wide maledictions.",
                        "Extreme": "Generational/national curses."
                    },
                    "crimes": ["Blackmail via curses", "Slow-burn coercion", "Extortion via curses"]
                },
                {
                    "name": "Familiar Summoning",
                    "description": "Call animal spirits/demons to serve.",
                    "threat_levels": {
                        "Laughably Low": "Small animal spy.",
                        "Moderate": "Demonic beasts for combat.",
                        "High": "Monster platoons.",
                        "Extreme": "Dragons/titans unleashed."
                    },
                    "crimes": ["Summoned assassins", "Monster raids", "Destruction of non ecologically friendly corporations"]
                },
                {
                    "name": "Rune Carving",
                    "description": "Inscribe runes for traps, wards, and buffs.",
                    "threat_levels": {
                        "Laughably Low": "Magical graffiti.",
                        "Moderate": "Enchanted weapons and doors.",
                        "High": "Explosive wards/killzones.",
                        "Extreme": "City-scale runic prisons."
                    },
                    "crimes": ["Trap police corridors", "Seal escape routes", "Tricks and terrorizing civilians"]
                },
                {
                    "name": "Time-Limited Enchantments",
                    "description": "Temporary magical buffs for gear/people.",
                    "threat_levels": {
                        "Laughably Low": "Buff a trinket.",
                        "Moderate": "Enhance stolen gear.",
                        "High": "Enchant squads/armies.",
                        "Extreme": "Citywide enchantment effects."
                    },
                    "crimes": ["Heist enhancements", "Superpowered henchmen", "Making villains more powerful"]
                },
                {
                    "name": "Elemental Summoning",
                    "description": "Conjure elementals to fight or guard.",
                    "threat_levels": {
                        "Laughably Low": "Small elementals.",
                        "Moderate": "Basic fire/water/earth/wind golems",
                        "High": "Elemental platoons.",
                        "Extreme": "Elemental apocalypses."
                    },
                    "crimes": ["Elemental assaults", "Guarding strongholds", "Area denial"]
                },
                {
                    "name": "Hex Fog",
                    "description": "Mystic mists that blind and confound.",
                    "threat_levels": {
                        "Laughably Low": "Irritating mist.",
                        "Moderate": "Confuse squads.",
                        "High": "District-wide blindness.",
                        "Extreme": "Endless fogs trapping cities."
                    },
                    "crimes": ["Conceal crime scenes", "Fog-of-war raids", "Transportation terrors"]
                },
                {
                    "name": "Forbidden Knowledge",
                    "description": "Wield eldritch lore and grimoires.",
                    "threat_levels": {
                        "Laughably Low": "Minor grimoires.",
                        "Moderate": "Summon contained horrors.",
                        "High": "Command eldritch entities.",
                        "Extreme": "Reality-tearing rites."
                    },
                    "crimes": ["Apocalyptic cults", "Forbidden summonings", "Mass destruction"]
                }
            ]   # close Fantasy / Magical powers
        },     # close Fantasy / Magical theme
        {
            "key": "deranged",            # must match a style key shown in your app’s theme dropdown
            "name": "Maniacal",
            "tier": "core",                # "core" or "uber"
            "powers": [
                {
                    "name": "Frenzied Strength",
                    "description": "Rage-fueled physical power spikes.",
                    "threat_levels": {
                        "Laughably Low": "Mild rage boost.",
                        "Moderate": "Smash squads.",
                        "High": "Rip apart tanks.",
                        "Extreme": "Unstoppable berserker."
                    },
                    "crimes": ["Rampage killings", "Brute-force raids", "Crimes of anger or passion"]
                },
                {
                    "name": "Blood Frenzy",
                    "description": "Grows stronger as more blood is shed.",
                    "threat_levels": {
                        "Laughably Low": "Boost from scratches.",
                        "Moderate": "Power builds each takedown.",
                        "High": "Immense strength in battles.",
                        "Extreme": "Godlike during massacres."
                    },
                    "crimes": ["Mass violence", "Shock offensives", "Brute force attacks"]
                },
                {
                    "name": "Deranged Genius",
                    "description": "Invents lethal, theatrical contraptions.",
                    "threat_levels": {
                        "Laughably Low": "Harmless contraptions.",
                        "Moderate": "Murder machines.",
                        "High": "Trap-filled districts.",
                        "Extreme": "Doomsday inventions."
                    },
                    "crimes": ["Tech-driven terror", "Deathtrap cities", "Asylum animosities"]
                },
                {
                    "name": "Frenetic Speed",
                    "description": "Hyper-kinetic motion and attacks.",
                    "threat_levels": {
                        "Laughably Low": "Runs faster than average.",
                        "Moderate": "Blitz squads.",
                        "High": "Untouchable killer speed.",
                        "Extreme": "City terrorized in seconds."
                    },
                    "crimes": ["Blitz assassinations", "Smash-and-run robberies", "Uncaught theft sprees"]
                },
                {
                    "name": "Unstable Mutation",
                    "description": "Body warps unpredictably, granting power.",
                    "threat_levels": {
                        "Laughably Low": "Minor deformities.",
                        "Moderate": "Warped bodies with advantages.",
                        "High": "Twisted monstrosities.",
                        "Extreme": "Lovecraftian mega-forms."
                    },
                    "crimes": ["Fear-driven crime waves", "Monster-led raids", "Terrorizing for fun"]
                },
                {
                    "name": "Maniacal Laughter",
                    "description": "Cackle that unnerves and destabilizes minds.",
                    "threat_levels": {
                        "Laughably Low": "Creepy chuckle.",
                        "Moderate": "Drive squads to panic.",
                        "High": "Unsettle cities.",
                        "Extreme": "Spread national madness."
                    },
                    "crimes": ["Psychological terror", "Cult recruitment", "Crowd dispersal"]
                },
                {
                    "name": "Pain Mastery",
                    "description": "Ignores pain; grows stronger from it.",
                    "threat_levels": {
                        "Laughably Low": "Shrug off bruises.",
                        "Moderate": "Laugh off bullets.",
                        "High": "Power rises with torture.",
                        "Extreme": "Near-immortal masochist."
                    },
                    "crimes": ["Endless assaults", "Fearless shock troops", "Brute force attacks"]
                },
                {
                    "name": "Chaotic Improvisation",
                    "description": "Turn any object into an effective weapon.",
                    "threat_levels": {
                        "Laughably Low": "Makeshift weapons.",
                        "Moderate": "Deadly everyday items.",
                        "High": "Always armed from nothing.",
                        "Extreme": "Chaos itself becomes weapon."
                    },
                    "crimes": ["Chaotic heists", "Improvised rampages", "Improv night disasters"]
                },
                {
                    "name": "Weaponized Insanity",
                    "description": "Project madness as a tactical weapon.",
                    "threat_levels": {
                        "Laughably Low": "Unsettling presence.",
                        "Moderate": "Break minds in combat.",
                        "High": "Spread insanity.",
                        "Extreme": "Nations collapse into mania."
                    },
                    "crimes": ["Mass hysteria campaigns", "Cult state creation", "Mental destruction of government officials"]
                },
                {
                    "name": "Frenzied Puppeteer",
                    "description": "Control others like marionettes.",
                    "threat_levels": {
                        "Laughably Low": "Manipulate dolls.",
                        "Moderate": "Briefly control humans.",
                        "High": "Dominate districts.",
                        "Extreme": "Enslave populations."
                    },
                    "crimes": ["Puppet armies", "Mind-slave empires", "Writes own moral code"]
                }
            ]   # close Maniacal powers
        },     # close Maniacal theme

        # ---------- UBER THEMES (locked unless Uber is ON) ----------
        {
            "key": "celestial",
            "name": "Celestial / Godhood",
            "tier": "uber",                # uber themes exclude “Laughably Low”
            "powers": [
                {
                    "name": "Stellar Flames",
                    "description": "Channel stellar fire and solar flares.",
                    "threat_levels": {
                        "Moderate": "Scorch districts with focused stellar heat.",
                        "High": "Incinerate city blocks with miniature flares.",
                        "Extreme": "Drop miniature suns on cities."
                    },
                    "crimes": ["Solar blackmail", "Incinerate evidence", "Siege critical zones"]
                },
                {
                    "name": "Planetary Control",
                    "description": "Manipulate tides, seasons, and lunar forces.",
                    "threat_levels": {
                        "Moderate": "Disrupt tides and weather cycles regionally.",
                        "High": "Force seasonal shocks and megastorms.",
                        "Extreme": "Shift planetary axes."
                    },
                    "crimes": ["Climate sabotage", "Tidal destruction", "Geo-extortion"]
                },
                {
                    "name": "Constellation Binding",
                    "description": "Conjure star-chains that immobilize or convert targets.",
                    "threat_levels": {
                        "Moderate": "Bind squads in radiant chains.",
                        "High": "Seal districts in celestial lattices.",
                        "Extreme": "Turn people into constellations."
                    },
                    "crimes": ["Mass abductions", "Public petrification", "Mythic terror acts"]
                },
                {
                    "name": "Gravity Stars",
                    "description": "Create stellar gravity wells on demand.",
                    "threat_levels": {
                        "Moderate": "Pin armored units with intense gravity.",
                        "High": "Collapse structures along a corridor.",
                        "Extreme": "Crush districts under artificial stars."
                    },
                    "crimes": ["Urban implosions", "Infrastructure collapse", "Hostage cities via wells"]
                },
                {
                    "name": "Cosmic Beams",
                    "description": "Fire cosmos-charged energy beams.",
                    "threat_levels": {
                        "Moderate": "Bore through fortifications.",
                        "High": "Vaporize armored columns.",
                        "Extreme": "Split skyscrapers or fault-lines."
                    },
                    "crimes": ["Precision assassinations", "Demonstration strikes", "Orbital extortion"]
                }
         ]   # close Celestial powers
     },     # close Celestial theme

        {
            "key": "eldritch",
            "name": "Eldritch / Cosmic Horror",
            "tier": "uber",
            "powers": [
                {
                    "name": "Madness Aura",
                    "description": "Radiate paranoia that blossoms into mass insanity.",
                    "threat_levels": {
                        "Moderate": "Corrupt crowds during rallies.",
                        "High": "Collapse city governance via mass hysteria.",
                        "Extreme": "Nations spiral into cults."
                    },
                    "crimes": ["Mind-control cults", "Panic stampedes", "Institutional sabotage"]
                },
                {
                    "name": "Tentacle Spawn",
                    "description": "Summon horrors from beyond.",
                    "threat_levels": {
                        "Moderate": "Overrun streets with abominations.",
                        "High": "Breach fortified compounds.",
                        "Extreme": "Cities consumed by writhing monstrosities."
                    },
                    "crimes": ["Monstrous sieges", "Abduction sweeps", "Cathedral-level destructions"]
                },
                {
                    "name": "Eldritch Whispers",
                    "description": "Implant forbidden truths that enslave minds.",
                    "threat_levels": {
                        "Moderate": "Indoctrinate cells of officials.",
                        "High": "Subvert entire agencies.",
                        "Extreme": "Entire populations enslaved mentally."
                    },
                    "crimes": ["Turn leaders", "Coerce confessions", "Rewrite loyalties"]
                },
                {
                    "name": "Dream of the Old Ones",
                    "description": "Trap cities in nightmare-realms.",
                    "threat_levels": {
                        "Moderate": "Districts suffer waking nightmares.",
                        "High": "Replace civic order with dream logic.",
                        "Extreme": "Eternal dreamscape replaces reality."
                    },
                    "crimes": ["Nightmare blackmail", "Sleep-siege operations", "Reality displacement"]
                },
                {
                    "name": "Flesh Distortion",
                    "description": "Twist bodies into grotesque forms.",
                    "threat_levels": {
                        "Moderate": "Crippling transformations of squads.",
                        "High": "Warp crowds into abominations.",
                        "Extreme": "Warp whole cities into horrors."
                    },
                    "crimes": ["Biomorph terror", "Forced mutations", "Population control"]
                }
         ]   # close Eldritch powers
     },     # close Eldritch theme

        {
            "key": "divine",
            "name": "Divine / Judgment",
            "tier": "uber",
            "powers": [
                {
                    "name": "Wrath of Heaven",
                    "description": "Rain divine fire and judgment.",
                    "threat_levels": {
                        "Moderate": "Smite compounds and strongholds.",
                        "High": "Level districts with holy storms.",
                        "Extreme": "Annihilate nations with celestial fury."
                    },
                    "crimes": ["Apocalyptic extortion", "Religious terror", "Nation-scale coercion"]
                },
                {
                    "name": "Sin Consumption",
                    "description": "Feed on guilt and corruption to grow unstoppable.",
                    "threat_levels": {
                        "Moderate": "Drain corrupt elites.",
                        "High": "Consume cities steeped in vice.",
                        "Extreme": "Become an unstoppable juggernaut."
                    },
                    "crimes": ["Targeted purges", "Mafia dismantling by terror", "Power siphoning"]
                },
                {
                    "name": "Judgment Day",
                    "description": "Condemn entire populations.",
                    "threat_levels": {
                        "Moderate": "Enact divine trials on districts.",
                        "High": "Banish cities judged unworthy.",
                        "Extreme": "Destroy entire populations."
                    },
                    "crimes": ["Mass sentencing", "Collective punishment", "Show-trial executions"]
                },
                {
                    "name": "Angelic Binding",
                    "description": "Seal armies/nations in chains of holy light.",
                    "threat_levels": {
                        "Moderate": "Bind battalions.",
                        "High": "Cage cities in radiant prisons.",
                        "Extreme": "Nation-scale bondage."
                    },
                    "crimes": ["Mass detentions", "Permanent imprisonment", "Holy extortion"]
                },
                {
                    "name": "Divine Voice",
                    "description": "Command obedience with a word.",
                    "threat_levels": {
                        "Moderate": "Silence riots instantly.",
                        "High": "Force citywide compliance.",
                        "Extreme": "Nation-wide obedience."
                    },
                    "crimes": ["Compulsory decrees", "Election manipulation", "Forced surrenders"]
                }
            ]   # close Divine powers
        },     # close Divine theme

        {
            "key": "annihilation",

            "name": "Annihilation / Void",
            "tier": "uber",
            "powers": [
                {
                    "name": "Absolute Erasure",
                    "description": "Delete matter without trace.",
                    "threat_levels": {
                        "Moderate": "Erase vehicles and vaults.",
                        "High": "Cleanly remove buildings.",
                        "Extreme": "Erase entire city sectors."
                    },
                    "crimes": ["Evidence erasure", "Blackmail by deletion", "Strategic disappearances"]
                },
                {
                    "name": "Memory Deletion",
                    "description": "Remove people or places from collective memory.",
                    "threat_levels": {
                        "Moderate": "Erase key witnesses.",
                        "High": "Delete institutions from history.",
                        "Extreme": "Remove whole cities from memory."
                    },
                    "crimes": ["Wipe informants", "Rewrite history", "Obliterate scandals"]
                },
                {
                    "name": "Unmaking",
                    "description": "Undo events, disasters, or creation itself.",
                    "threat_levels": {
                        "Moderate": "Reverse single incidents.",
                        "High": "Rewrite major timelines in a region.",
                        "Extreme": "Unravel foundational events."
                    },
                    "crimes": ["Alibi perfection", "Retroactive sabotage", "Cause-reversal extortion"]
                },
                {
                    "name": "Black Hole Generation",
                    "description": "Spawn localized voids.",
                    "threat_levels": {
                        "Moderate": "Consume armored targets.",
                        "High": "Swallow buildings and bridges.",
                        "Extreme": "Progress to planetary annihilation."
                    },
                    "crimes": ["Vault annihilation", "Hostage infrastructure", "Orbital terror"]
                },
                {
                    "name": "Silence of the Void",
                    "description": "Enforce absolute silence and darkness.",
                    "threat_levels": {
                        "Moderate": "Nullify surveillance and communications.",
                        "High": "Suffocate districts in stillness.",
                        "Extreme": "World consumed by nothingness."
                    },
                    "crimes": ["Stealth dominion", "Total blackout extortion", "Mass disappearances"]
                }                      # closes last power
            ]   # close Annihilation powers
        },     # close Annihilation theme
    ]          # close themes list
}              # close COMPENDIUM

# ===== Style prompts per theme key =====
STYLE_PROMPTS = {
    # core
    "elemental": "Painterly comic realism, dynamic lighting, embers/fog/spray matching the element, dramatic Dutch angles.",
    "energy": "Clean hi-tech cyber look, neon rim-light, arcing energy effects, volumetric glow, sharp contrast.",
    "biological": "Gritty bio-organic textures, macro detail, chitin/bone/sinew motifs, muted cinematic palette.",
    "psychic": "Surreal telepathic aura, distortion ripples, lens warping, soft bloom, cool violets and teals.",
    "chemical": "Industrial grime, hazard signage, toxic vapor plumes, corroded metal, yellow-green accents.",
    "chaos": "Mischief-carnival vibe, bold colors, motion blur, non-Euclidean angles, glitch flourishes.",
    "satirical": "Dark comedy pulp poster style, exaggerated props, bold type, pop-art splashes.",
    "tragic": "Bleak cinematic noir, rain-slick streets, desaturated tones, long shadows, somber framing.",
    "magical": "Epic fantasy illustration, ornate runes, arcane circles, moody rim light, rich jewel tones.",
    "deranged": "Unhinged grindhouse poster, harsh grain, smeared motion, harsh reds and blacks.",

    # uber
    "celestial": "Mythic cosmic grandeur, starfields, god-rays, gold and white accents, architectural scale.",
    "eldritch": "Cosmic horror etching, impossible geometry, abyssal palette, fine inked textures.",
    "divine": "Cathedral-grade holy radiance, marble and gold, sacred sigils, high contrast chiaroscuro.",
    "annihilation": "Minimalist void, negative-space composition, extreme contrast, hard silhouettes.",
}

def get_style_prompt(theme_key: str) -> str:
    return STYLE_PROMPTS.get((theme_key or '').strip().lower(), "")


import random
ALLOWED_THREATS = {
    "core": ["Laughably Low", "Moderate", "High", "Extreme"],
    "uber": ["Moderate", "High", "Extreme"],
}

def compendium_available_themes(include_uber: bool):
    themes = []
    for t in COMPENDIUM.get("themes", []):
        if t.get("tier") == "core" or include_uber:
            themes.append(t)
    return themes

def normalize_style_key(k: str | None) -> str:
    """Pass-through: we only accept real compendium theme keys now."""
    k = (k or "").strip().lower()
    return k or _first_core_compendium_key()


def compendium_available_powers(style_key: str, include_uber: bool):
    powers = []
    for t in compendium_available_themes(include_uber):
        if not style_key or t.get("key") == style_key:
            powers.extend(t.get("powers", []))
    return powers

def _index_powers_by_name() -> dict:
    idx = {}
    for t in COMPENDIUM.get("themes", []):
        for p in t.get("powers", []) or []:
            n = (p.get("name") or "").strip().lower()
            if n and n not in idx:
                idx[n] = p
    return idx

def upconvert_power(raw):
    """
    Accepts either:
      - dict power entries (already new format) -> returns as-is with a 'legacy' flag False.
      - string power names (old saves)          -> returns matching dict from COMPENDIUM + legacy flag True.
    If no match is found, returns a minimal dict with legacy flag True.
    """
    if isinstance(raw, dict) and raw.get("name"):
        out = dict(raw)
        out.setdefault("_legacy", False)
        return out

    name = (str(raw or "")).strip()
    idx = getattr(upconvert_power, "_idx_cache", None)
    if idx is None:
        idx = _index_powers_by_name()
        upconvert_power._idx_cache = idx

    p = idx.get(name.lower())
    if p:
        out = dict(p)
        out["_legacy"] = True
        return out

    # Fallback minimal shape so UI doesn't crash
    return {
        "name": name or "Unknown Power",
        "description": "Imported from an old save. Details missing.",
        "threat_levels": {},
        "crimes": [],
        "_legacy": True,
    }

# --- Style → Compendium key normalizer (temporary bridge while UI still uses old labels) ---
def _first_core_compendium_key() -> str:
    for t in COMPENDIUM.get("themes", []):
        if (t or {}).get("tier") == "core":
            return (t or {}).get("key") or "dark"
    # fallback: first theme key or 'dark'
    return (COMPENDIUM.get("themes", [{}])[0].get("key") or "dark")



# super-light weighted pick for threat label
_THREAT_WEIGHTS = {
    "Laughably Low": 0.10,
    "Moderate": 0.40,
    "High": 0.30,
    "Extreme": 0.20,
}

def _weighted_choice(labels):
    bag = []
    for lbl in labels:
        w = _THREAT_WEIGHTS.get(lbl, 1.0)
        bag.extend([lbl] * max(1, int(w * 100)))
    return random.choice(bag) if bag else (labels[0] if labels else "Moderate")

def compendium_pick_power(style_key: str, include_uber: bool) -> dict | None:
    # 1) collect candidate powers by style key and Uber flag
    opts = compendium_available_powers(style_key, include_uber)
    if not opts:
        return None

    # 2) pick tier and allowed labels (Uber excludes "Laughably Low")
    #    We infer tier from themes list membership (unchanged behavior).
    #    Note: a single power may appear only in one theme; this keeps logic simple.
    def _power_tier(p):
        for t in COMPENDIUM["themes"]:
            if p in t.get("powers", []):
                return t.get("tier", "core")
        return "core"

    # 3) choose a label first, weighted by ALLOWED_THREATS + your weights
    #    (this is the behavior change: threat first, power second)
    #    We use tier="uber" if *any* uber power is present and uber is included; otherwise "core".
    has_uber = any(_power_tier(p) == "uber" for p in opts)
    tier = "uber" if (include_uber and has_uber) else "core"
    allowed = ALLOWED_THREATS[tier]
    label = _weighted_choice(allowed)

    # 4) filter powers that explicitly have this label in their threat_levels
    eligible = [p for p in opts if label in (p.get("threat_levels") or {})]
    picks = eligible if eligible else opts  # graceful fallback if no exact match

    p = random.choice(picks)

    # 5) build the bundle (exactly 3 crimes, safe if AKA missing)
    crimes = list(p.get("crimes", []))[:3]
    return {
        "theme_key": style_key,
        "name": p.get("name", ""),
        "aka": p.get("aka", ""),
        "description": p.get("description", ""),
        "threat_label": label,
        "threat_text": (p.get("threat_levels") or {}).get(label, ""),
        "crimes": crimes,
    }

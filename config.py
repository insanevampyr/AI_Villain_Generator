# config.py
import os

# ===== App / Model Settings =====
APP_NAME = os.getenv("APP_NAME", "AI Villain Generator")
OPENAI_MODEL_NAME  = os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini")
OPENAI_IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "dall-e-3")
OPENAI_IMAGE_SIZE  = os.getenv("OPENAI_IMAGE_SIZE", "1024x1024")

# ==============================================================
# POWER POOLS BY THEME
# Each power is "Title — short cinematic description" so it stands
# on its own without needing parentheses. Keep wording vivid.
# ==============================================================
POWER_POOLS = {
    # ----------------------------------------------------------
    # DARK: dread, decay, void, fear. No sci‑fi jargon here.
    # ----------------------------------------------------------
    "dark": [
        "Umbrakinesis — command living shadows that claw and bind",
        "Dread Pulse — project waves of terror that weaken will",
        "Soul Siphon — drain life‑force and grow stronger",
        "Night's Veil — smother light and sight in an absolute black",
        "Grave Whisper — commune with the dead for secrets and favors",
        "Blood Hex — curse a target so pain answers every action",
        "Null Halo — snuff hope and courage in a chilling radius",
        "Tombstep — pass through walls as if they were coffins",
        "Woe Stitching — mend wounds by threading agony into flesh",
        "Ashen Grip — rot whatever you touch to brittle ash",
        "Black Lantern — swallow lamps, torches, even moonlight",
        "Despair Beacon — a lingering gloom that saps resolve",
        "Bleak Fortune — hitch bad luck to a victim like a chain",
        "Morbid Insight — glimpse the final moments of any life",
        "Shivercraft — forge weapons from condensed fear",
        "Eclipse Brand — mark foes; their powers dim near you",
        "Quietus Breath — hush sound and spell alike",
        "Funeral March — drag enemies step by step toward you",
        "Nightmare Casting — seed waking visions that unravel sanity",
        "Coffin Warp — short jumps from one shadow to another",
        "Witherwave — ripple of entropy that weakens structures",
        "Nocturne Ward — a barrier woven of pure darkness",
        "Gloom Harvest — convert panic and dread into energy",
        "Deathknell Echo — amplify a dying sound into a shockwave",
        "Stygian Chains — conjure binding chains from the underdark",
        "Pale Fire — cold black flames that do not give light",
        "Sable Mirror — reflect an enemy's pain back upon them",
        "Obsidian Spines — shadow spikes erupt from the ground",
        "Wraithwalk — become incorporeal for a few heartbeats",
        "Mourner's Call — summon sorrowful shades to hinder foes",
        "Hollow Crown — dominate weakened minds with a word",
        "Rot Script — etch curses into the air that linger",
        "Gravecold — a touch that steals heat and hope",
    ],

    # ----------------------------------------------------------
    # FUNNY: slapstick, prop comedy, cartoon physics.
    # ----------------------------------------------------------
    "funny": [
        "Rubber Reality — stretch, squash, and bounce like a toon",
        "Banana Slipstream — create instant banana peels you can surf",
        "Explosive Whoopee Cushion — comedic airburst knocks foes flat",
        "Seltzer Jetpack — carbonated flight with fizzy evasions",
        "Anvil Orbit — drop comedic anvils from nowhere",
        "Slapstick Physics — improbable pratfalls hurt only the target",
        "Clown Car Conjuration — produce endless props from nowhere",
        "Confetti Storm — blinding flurry that also jams weapons",
        "Giggle Hex — laughter fits break enemy formation",
        "Prop Mastery — always pull the perfect gag gadget",
        "Cartoon Hole — portable doorway disc placed on any surface",
        "Foam Fortress — spray a safe but immovable barricade",
        "Kazooblast — weaponized kazoo note becomes a sonic beam",
        "Gummy Grapple — elastic candy tethers reel foes in",
        "Sticker Trap — peel‑and‑seal patches snare feet and hands",
        "Vaudeville Vanish — disappear via sudden trapdoor gag",
        "Canned Laughter — summon morale‑boosting laugh track",
        "Punchline Recall — rewind the last three seconds for a redo",
        "Streamers & Ribbons — bind enemies in colorful coils",
        "Party Pop — stun with dazzling poppers and flash",
        "Toon Mask — exaggerated expressions sway moods",
        "Bubble Barrage — floating orbs nudge and nudge and nudge",
        "Joke Magnetism — all attention drifts to your antics",
        "Cartoon Physics — once per scene, ignore normal physics",
    ],

       # ----------------------------------------------------------
    # SCI‑FI: clean techno‑poetry, energy, physics, devices.
    # ----------------------------------------------------------
    "sci-fi": [
        "Electrokinesis — shape lightning into blades and nets",
        "Nano‑Swarm — print micro‑machines that build or devour",
        "Hardlight Projectors — sculpt solid holograms as tools or walls",
        "Grav Shear — carve space with angled gravity planes",
        "Phase Tunneling — walk through matter like mist",
        "Neural Overclock — time stretches while your thoughts sprint",
        "Plasma Rail — fire a coherent lance of sun‑hot matter",
        "Quantum Anchor — lock teleportation and phasing in an area",
        "Drone Constellation — microunits orbit and obey",
        "Photonic Cloak — bend light to disappear in plain sight",
        "Ionic Net — EMP mesh that drops drones and armor",
        "Microforge — print the right tool from thin feedstock",
        "Cyber Symbiosis — merge mind and system for perfect control",
        "Kinetic Shunt — store impacts and release them back",
        "Inertial Dampers — walk through explosions unharmed",
        "Spectral Scanner — see through walls, floors, and vaults",
        "Retrovirus Edit — apply temporary biomods on the fly",
        "Null Field — a hush where powers and gadgets sputter",
        "Antimatter Pinprick — micro‑annihilation with surgical aim",
        "Tachyon Tag — mark a target and strike them a heartbeat later",
        "Magnetoform — reshape metal like wet clay",
        "Thermoptic Burst — blink the spectrum to erase visibility",
        "Data Leech — rip secrets from any connected device",
        "Railstep — glide on magnetic lines for instant movement",
        "Cryo Lattice — freeze‑web that locks machinery in ice",
        "Neural Mirage — injected AR hallucinations feel real",
        "Orbital Nudge — tiny thrusters shift heavy objects",
        "Smart Dust — clouds of sensors map every surface",
        "Entropic Scrambler — make weapons misfire and jam",
        "Bio‑Gel Patch — rapid foam that seals and heals",
        "Singularity Seed — brief micro‑well that drags and breaks",
        "Waveform Body — flicker into energy for a blink",
        "Ion Skates — airborne glide on charged rails",
        "Safeguard Daemon — a guardian AI that counters hacks",
    ],

    # ----------------------------------------------------------
    # MYTHIC: old law, vows, relics, nature spirits.
    # ----------------------------------------------------------
    "mythic": [
        "Rune Weaving — carve living sigils that bind and blaze",
        "Stormcalling — command thunderheads and rain spears",
        "Beast Tongue — bind great creatures with a spoken pact",
        "Fate Thread — tug destiny a finger‑width at a time",
        "Hearthfire Boon — warmth that wards and heals the worthy",
        "Underworld Gate — open a brief passage beneath the world",
        "Sun Chariot — dash in a trail of blazing daylight",
        "Moonbinding — cool silver shackles that hold the wild",
        "Verdant Pact — roots and vines heed your summons",
        "Stone Sleep — skin becomes granite, blows glance off",
        "Sky Harp — play weather like strings and notes",
        "Oathbinding — a promise enforced by ancient law",
        "Trickster's Mask — borrow a face and a voice",
        "Oracle's Sight — glimpse of several near futures",
        "Raven Post — spirit messenger that always finds its mark",
        "Tidal Crown — tides rise and fall to your step",
        "Titan Bone — quake strike that splits the earth",
        "Ember Rite — ritual spark that turns to sacred flame",
        "Wolfshadow — call a moon‑pack from the dark",
        "Worldroot Step — slip from tree to distant tree",
        "Ambrosia Surge — divine vigor floods your veins",
        "Dragon Tongue — a word that stills ancient beasts",
        "Mirror Lake — surface shows the memory you seek",
        "Ashen Ward — warding ash circle thwarts curses",
        "Valkyrie Lift — bear the fallen beyond harm",
        "Labyrinth Walk — conjure a maze around a foe",
        "Sun‑Rune Brand — a mark that purges corruption",
        "Thorn Oath — betrayal draws blood from the traitor",
        "Lantern of Hel — reveal hidden spirits and debts",
        "Basilisk Glare — petrify with a meeting of eyes",
        "Runic Recall — blink to a sigil you scribed",
        "Norn's Favor — reroll the fates once",
        "Wild Hunt — the riders answer your horn",
        "Totem Guard — spirit sentries patrol your ground",
        "Phoenix Gift — kindle a spark of rebirth",
    ],

    # ----------------------------------------------------------
    # CHAOTIC: probability, glitches, paradoxes. Embrace weird.
    # ----------------------------------------------------------
    "chaotic": [
        "Dice of Doom — weight the odds when it counts",
        "Probability Fracture — force the unlikely to occur",
        "Entropy Touch — speed decay in anything you handle",
        "Wild Surge — random beneficial burst when stressed",
        "Glitchstep — hop unpredictably between nearby spots",
        "Coinflip Aegis — block everything or nothing at all",
        "Catastrophe Seed — small change cascades to disaster",
        "Jinx Loop — misfortune rebounds again and again",
        "Schrodinger Palm — on/off superposition until observed",
        "Roulette Beam — damage type changes every shot",
        "Chaos Net — scramble formations and friend/foe ties",
        "Wobble Time — seconds stutter and skip around you",
        "Unstable Clone — brief double acts out of sync",
        "Cascade Error — one failure triggers many",
        "Disorder Aura — plans unravel in your presence",
        "Quantum Trick — swap places with an object or foe",
        "Gambler's Mark — leech luck from a chosen target",
        "Spiteback — random effect reflects to the source",
        "Unmake Knot — unravel complex constructs",
        "Anomaly Pin — nail a weird zone to one location",
        "Bug Report — reveal and exploit a hidden flaw",
        "Tilt Reality — physics skews at odd angles",
        "Loaded Chance — stack odds briefly in your favor",
        "Whimfire — flames pick a new element each burst",
        "Scatter Step — split into motes then reform",
        "Paradox Note — erase a tiny event from the record",
        "Chaos Bargain — gain power, pay with a glitch",
        "Jam Fate — pause destiny's next turn",
        "Entropic Bloom — a radius of creeping disarray",
        "Fortuna's Favor — one guaranteed critical success",
        "Tumbling Deck — shuffle everyone's positions",
        "Miscast Mirror — invert the next power used",
        "Glitch Armor — defense flickers in and out",
        "Random Recall — snap back to a prior spot",
        "Breakpoint — force a nearby system crash",
    ],

    # ----------------------------------------------------------
    # SATIRICAL: PR warfare, bureaucracy, narrative weapons.
    # ----------------------------------------------------------
    "satirical": [
        "Cancel Field — mute influence and outreach in an area",
        "Mandatory Recall — force products or people to roll back",
        "Spin Doctor — reframe events until truth loses",
        "Clout Siphon — steal attention and following",
        "Astroturf Engine — fabricate fake grassroots support",
        "Algorithmic Outrage — tune feeds to inflame emotions",
        "Brand Hex — logos twist into liabilities",
        "Red Tape Storm — bury the field in forms and stamps",
        "Virtue Signal Jammer — scramble performative posturing",
        "Narrative Rewrite — swap roles of villain and hero",
        "Terms & Conditions — compel compliance to small print",
        "Clickbait Lure — headlines drag crowds to you",
        "Echo Chamber — loops of opinion drown dissent",
        "Sponsored Shield — brand‑powered barrier so long as ads show",
        "Fine Print — twist contracts mid‑signature",
        "PR Cloak — image laundering hides your tracks",
        "Ratio Storm — overwhelm communications channels",
        "TL;DR — compress nuanced info into useless sludge",
        "Focus Group — conjure consensus to justify any plan",
        "Engagement Trap — can't look away once you start",
        "Shadowban — hide a target from search and sight",
        "Viral Hex — bad luck spreads like a meme",
        "Hot Take Overheat — tempers spike and reason melts",
        "Bureaucracy Bomb — paperwork erupts everywhere",
        "Compliance Ping — force an immediate acknowledgment",
        "Paywall — deny access until tribute is paid",
        "Comment Deluge — drown signal in noise",
        "Fact‑Check Flash — snap reality back for an instant",
        "Opt‑Out Null — negate an effect if consent was given",
        "Influencer Aura — misguided loyalty follows you",
        "Brand Switch — swap allegiances in a crowd",
        "NDA Veil — a hush falls under nondisclosure",
        "DM Leak — secrets spill from private channels",
        "Trendjack — steal momentum from another story",
        "Terms Revocation — void a boon by clause",
        "Viral Loop — retrigger the last action again",
        "Fourth Wall Tap — meta interference breaks the scene",
        "Plot Armor — survive one impossible blow",
    ],

    # ----------------------------------------------------------
    # CYBERPUNK: street‑level tech, grit, augments, the Grid.
    # ----------------------------------------------------------
    "cyberpunk": [
        "Ghost in the Grid — move unseen through networks",
        "Black ICE Bloom — unleash offensive counter‑AI thorns",
        "Synapse Overdrive — reflexes blaze, decisions sharpen",
        "Chrome Shield — reactive smart armor forms on impact",
        "Neural Jack — slot a new skill like software",
        "Optic Scramble — blind cameras and scopes",
        "Drone Wrangle — commandeer corporate swarms",
        "Data Spike — lance that shreds routines and locks",
        "Street Surgeon — battlefield med‑mods on demand",
        "Skimmer Blades — mono‑filaments that pass through steel",
        "Shock Gauntlets — grapple stun with brutal volts",
        "Cortex Grenade — flash‑memory overload and confusion",
        "Spline Runner — ride fiber paths at freeway speed",
        "Ghost Tag — trace anyone through the city mesh",
        "Adrenal Switch — dumpers flip you into feral focus",
        "SkinWeave — subdermal fibers disperse impact",
        "Black Market Backdoor — instant admin in dirty systems",
        "ICEbreaker Hymn — algorithmic chant breaks defenses",
        "EMP Kiss — close‑range disable and silence",
        "Sprawl Leap — grapple runs you rooftop to rooftop",
        "Chrome Mirage — decoy projections throw aim off",
        "Memory Scrub — erase the last hour clean",
        "Gridlock — freeze local traffic, drones, and lights",
        "Credit Siphon — drain digital funds in a breath",
        "Firmware Hex — corrupt upgrades mid‑install",
        "Neon Quiver — hardlight bolts that curve midair",
        "Biofeedback Lash — send pain back through a link",
        "Thermal Cascade — overclock heat to melt gear",
        "Ghostwalk Protocol — soundless movement at speed",
        "Corporate Seal — invoke false authority that opens doors",
        "Sandglass — bullet‑time burst around your body",
        "Packet Warp — sling data or yourself along a beam",
        "Subdermal Vault — hide contraband where scanners fail",
        "Drone Perch — perch‑cam shows the city from above",
        "Net Phantasm — fake system presence to mislead",
    ],
}

# Map UI labels to pools (kept for clarity)
STYLE_TO_POWER_POOL = {
    "dark": "dark",
    "funny": "funny",
    "sci-fi": "sci-fi",
    "mythic": "mythic",
    "chaotic": "chaotic",
    "satirical": "satirical",
    "cyberpunk": "cyberpunk",
}

# Helper: flattened, de‑duped list of every power (if needed)

def _dedupe(seq):
    seen, out = set(), []
    for s in seq:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out

ALL_POWERS = _dedupe([p for lst in POWER_POOLS.values() for p in lst])

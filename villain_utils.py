from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import os
import datetime
import textwrap
import streamlit as st
from openai import OpenAI
import base64
import io
import re
from typing import List, Tuple, Optional

from optimization_utils import hash_villain, set_debug_info, dalle_price

# === Constants ===
STYLE_THEMES = {
    "dark": {"accent": "#ff4b4b", "text": "#ffffff"},
    "funny": {"accent": "#ffcc00", "text": "#ffffff"},
    "epic": {"accent": "#00bfff", "text": "#ffffff"},
    "sci-fi": {"accent": "#00ffcc", "text": "#ffffff"},
    "mythic": {"accent": "#9933ff", "text": "#ffffff"},
    "chaotic": {"accent": "#ff66cc", "text": "#ffffff"},
    "satirical": {"accent": "#ff9900", "text": "#ffffff"},
    "cyberpunk": {"accent": "#39ff14", "text": "#ffffff"},
}

# Output & assets
CARD_FOLDER   = "C:/Users/VampyrLee/Desktop/AI_Villain/villain_cards"
IMAGE_FOLDER  = "C:/Users/VampyrLee/Desktop/AI_Villain/villain_images"
DEFAULT_IMAGE = "C:/Users/VampyrLee/Desktop/AI_Villain/assets/AI_Villain_logo.png"
FONT_PATH     = "C:/Users/VampyrLee/Desktop/AI_Villain/fonts/ttf"  # your custom fonts folder
LOG_FOLDER    = "C:/Users/VampyrLee/Desktop/AI_Villain/villain_logs"

# Strong portrait guidance to avoid icon/sticker/logo outcomes.
QUALITY_HINT = (
    "Cinematic bust portrait, 3/4 view, photorealistic skin texture, dramatic lighting, depth of field, "
    "rich background bokeh, intricate detail, volumetric light, high dynamic range. "
    "NOT an icon, NOT a logo, NOT a sticker, NOT flat vector art, no text or signage."
)

# Theme → visual style boosters for DALL·E
THEME_VISUALS = {
    "funny": "bright, comedic composition, exaggerated expressions, whimsical props, saturated but balanced colors",
    "satirical": "playful yet sharp composition, clever visual irony, poster-like framing without text",
    "dark": "low-key lighting, chiaroscuro, cold palette, occult hints, oppressive atmosphere",
    "epic": "grand scale, celestial glow, ethereal atmosphere, ultra-detailed, sweeping cinematic lighting",
    "mythic": "ancient textures, carved stone, sacred motifs, weathered materials, natural backdrops",
    "sci-fi": "clean industrial design, emissive panels, precise geometry, cool palette, subtle chromatic aberration",
    "cyberpunk": "neon grime, rain-slick surfaces, retro-futurist shapes, moody backlight, holographic haze",
    "chaotic": "glitch motifs, motion blur, double exposure, probabilistic artifacts, unexpected overlays",
}

# === Logging ===
def save_villain_to_log(villain):
    if not isinstance(villain, dict):
        return
    os.makedirs(LOG_FOLDER, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = os.path.join(LOG_FOLDER, f"villain_{timestamp}.txt")
    with open(filename, "w", encoding="utf-8") as f:
        for key, value in villain.items():
            f.write(f"{key}: {value}\n")

def save_visual_prompt_to_log(name, prompt):
    os.makedirs(LOG_FOLDER, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = os.path.join(LOG_FOLDER, f"prompt_{name}_{timestamp}.txt")
    with open(filename, "w", encoding="utf-8") as f:
        f.write(prompt.strip())

# ===================== SAFETY / SANITIZATION =====================

# Terms that often trigger content violations for image models.
BANNED_REGEXES = [
    r"\b(blood|bloody|bloodied|gore|gory|guts|entrails|decapitat\w*|behead\w*|mutilat\w*|tortur\w*|maim\w*|"
    r"throat\s*slit|knife\s*to\s*throat|dismember\w*|severed)\b",
    r"\b(suicide|self[-\s]*harm|overdose|self[-\s]*mutilation)\b",
    r"\b(rape|sexual|sex|nude|nudity|breasts?|nipples?|genitals?|explicit|fetish)\b",
    r"\b(child|children|minor|underage|schoolgirl|teen\b)\b",
    r"\b(hate\s*symbol|nazi|swastika|kkk|lynch\w*)\b",
    r"[\"“”‘’][^\"“”‘’]{0,80}[\"“”‘’]",  # strip quoted lines (names/slogans/signs)
]

def sanitize_for_images(text: str, max_len: int = 300) -> str:
    """
    PG-13 sanitize any freeform text before it gets near image prompts.
    - Remove/obfuscate risky words/phrases
    - Trim very long origins to avoid dragging in sensitive details
    """
    if not text:
        return ""
    s = text
    # Normalize whitespace
    s = re.sub(r"\s+", " ", s).strip()
    # Apply regex redactions
    for rx in BANNED_REGEXES:
        s = re.sub(rx, "redacted", s, flags=re.IGNORECASE)
    # Hard-trim length
    if len(s) > max_len:
        s = s[:max_len].rsplit(" ", 1)[0] + "…"
    return s

def safe_theme_line(villain: dict) -> str:
    t = (villain.get("theme") or "").lower()
    s = THEME_VISUALS.get(t)
    return f"Theme style: {s}." if s else ""

# ===================== FONT LOADING (bulletproof) =====================

def _first_existing(paths):
    for p in paths:
        if p and os.path.exists(p):
            return p
    return None

def _resolve_font_path(filename):
    """
    Try multiple locations so size really applies:
    1) Project FONT_PATH
    2) ./fonts/ttf relative to repo root
    3) Windows fonts (Arial/Arial Bold)
    4) PIL bundled DejaVu fonts
    """
    # 1) Project path
    candidates = [
        os.path.join(FONT_PATH, filename),
        os.path.join("fonts", "ttf", filename),
        os.path.join(".", "fonts", "ttf", filename),
    ]

    # 2) Windows common fallbacks
    win_map = {
        "DejaVuSans.ttf":       r"C:\Windows\Fonts\arial.ttf",
        "DejaVuSans-Bold.ttf":  r"C:\Windows\Fonts\arialbd.ttf",
        "DejaVuSans-Oblique.ttf": r"C:\Windows\Fonts\ariali.ttf",
    }
    if os.name == "nt" and filename in win_map:
        candidates.append(win_map[filename])

    # 3) PIL bundled fonts
    try:
        import PIL
        pil_fonts = os.path.join(os.path.dirname(PIL.__file__), "fonts")
        candidates.append(os.path.join(pil_fonts, filename))
    except Exception:
        pass

    return _first_existing(candidates)

def load_fonts():
    """
    Ensure TrueType fonts are loaded. If a TTF can't be found,
    warn and fall back (but that bitmap font will look tiny).
    """
    names = {
        "title":   "DejaVuSans-Bold.ttf",
        "section": "DejaVuSans-Bold.ttf",
        "body":    "DejaVuSans.ttf",
        "italic":  "DejaVuSans-Oblique.ttf",
    }

    paths = {k: _resolve_font_path(v) for k, v in names.items()}

    # Sizes tuned for social readability
    SIZE_TITLE   = 72   # big headline
    SIZE_SECTION = 44   # section labels
    SIZE_BODY    = 34   # paragraph text

    def _load(path, size, fallback_name):
        if path:
            try:
                return ImageFont.truetype(path, size)
            except Exception as e:
                print(f"[font] Failed to load {path}: {e}")
        print(f"[font] WARNING: Using PIL default for {fallback_name}. Text may look small if TrueType not found.")
        return ImageFont.load_default()

    title_font   = _load(paths["title"],   SIZE_TITLE,   "title")
    section_font = _load(paths["section"], SIZE_SECTION, "section")
    body_font    = _load(paths["body"],    SIZE_BODY,    "body")
    italic_font  = _load(paths["italic"],  SIZE_BODY,    "italic")

    # Log which paths were used for quick debugging
    try:
        set_debug_info(
            context="Card Fonts",
            prompt=f"title={paths['title']}, section={paths['section']}, body={paths['body']}, italic={paths['italic']}",
            cost_only=True
        )
    except Exception:
        pass

    return title_font, section_font, body_font, italic_font

# ===================== TEXT MEASUREMENT HELPERS =====================

def text_height(font: ImageFont.FreeTypeFont, sample: str = "Ay") -> int:
    bbox = font.getbbox(sample)
    return bbox[3] - bbox[1]

def measure_line_width(font: ImageFont.FreeTypeFont, text: str) -> int:
    if not text:
        return 0
    bbox = font.getbbox(text)
    return bbox[2] - bbox[0]

def wrap_text_pixels(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> List[str]:
    words = (text or "").split()
    lines: List[str] = []
    current = []
    for w in words:
        candidate = (" ".join(current + [w])).strip()
        if not current or measure_line_width(font, candidate) <= max_width:
            current.append(w)
        else:
            lines.append(" ".join(current))
            current = [w]
    if current:
        lines.append(" ".join(current))
    return lines

def measure_paragraph_height(text: str, font: ImageFont.FreeTypeFont, max_width: int, line_gap: int) -> Tuple[List[str], int]:
    lines = []
    total = 0
    for raw in (text or "").split("\n"):
        wrapped = wrap_text_pixels(raw, font, max_width) if raw.strip() else [""]
        for ln in wrapped:
            lines.append(ln)
            total += text_height(font) + line_gap
    return lines, total

def measure_bullets_height(items: List[str], font: ImageFont.FreeTypeFont, max_width: int, line_gap: int, bullet_indent: int) -> Tuple[List[str], int]:
    render_lines = []
    total = 0
    bullet = "• "
    for item in (items or []):
        first_prefix = bullet
        rest_prefix  = " " * bullet_indent
        first_w = measure_line_width(font, first_prefix)
        raw_lines = wrap_text_pixels(str(item), font, max_width - first_w) or [""]
        render_lines.append(first_prefix + raw_lines[0])
        total += text_height(font) + line_gap
        for ln in raw_lines[1:]:
            render_lines.append(rest_prefix + ln)
            total += text_height(font) + line_gap
    return render_lines, total

# ===================== CARD BUILDER =====================

def create_villain_card(villain, image_file=None, theme_name="dark"):
    """
    Dynamic-height, social-ready villain card with:
    - Portrait top-right
    - Meta sections in left column
    - Origin full width beneath portrait (wraps under it)
    """
    theme = STYLE_THEMES.get(theme_name, STYLE_THEMES["dark"])

    # Layout
    card_width      = 1200
    margin          = 40
    portrait_size   = (360, 360)   # a touch larger to match bigger text
    section_gap     = 18
    label_gap       = 8
    line_gap        = 8
    bullet_indent   = 3
    left_col_width  = card_width - (margin * 3) - portrait_size[0]
    body_indent_px  = 10

    # Fonts
    title_font, section_font, body_font, italic_font = load_fonts()

    # Normalize inputs
    catchphrase = villain.get("catchphrase", "") or "Unknown"
    crimes = villain.get("crimes", [])
    if isinstance(crimes, str):
        crimes = [crimes] if crimes else []
    power        = villain.get("power", "Unknown")
    weakness     = villain.get("weakness", "Unknown")
    nemesis      = villain.get("nemesis", "Unknown")
    lair         = villain.get("lair", "Unknown")
    threat_level = villain.get("threat_level", "Unknown")
    faction      = villain.get("faction", "Unknown")
    origin_text  = villain.get("origin", "Unknown")

    # Measure pass
    title_text = f"{villain.get('name','Unknown')} aka {villain.get('alias','Unknown')}"
    title_h = text_height(title_font)

    def measure_section(label: str, content: str, *, italic=False, bullets: Optional[List[str]] = None) -> int:
        h = text_height(section_font) + label_gap
        if bullets is not None:
            _, block_h = measure_bullets_height(bullets, body_font, left_col_width - body_indent_px, line_gap, bullet_indent)
        else:
            f = italic_font if italic else body_font
            _, block_h = measure_paragraph_height(str(content), f, left_col_width - body_indent_px, line_gap)
        h += block_h + section_gap
        return h

    meta_height = 0
    meta_height += measure_section("Power", power)
    meta_height += measure_section("Weakness", weakness)
    meta_height += measure_section("Nemesis", nemesis)
    meta_height += measure_section("Lair", lair)
    meta_height += measure_section("Catchphrase", catchphrase, italic=True)
    meta_height += measure_section("Crimes", "", bullets=crimes)
    meta_height += measure_section("Threat Level", threat_level)
    meta_height += measure_section("Faction", faction)

    portrait_bottom = margin + portrait_size[1]
    left_column_bottom = margin + title_h + section_gap + meta_height
    origin_start_y = max(left_column_bottom, portrait_bottom + margin)
    origin_label_h = text_height(section_font) + label_gap
    _, origin_block_h = measure_paragraph_height(origin_text, body_font, card_width - (margin * 2) - body_indent_px, line_gap)
    origin_total_h = origin_label_h + origin_block_h + section_gap

    card_height = origin_start_y + origin_total_h + margin

    # Draw pass
    image = Image.new("RGBA", (card_width, card_height), (0, 0, 0, 255))
    draw = ImageDraw.Draw(image)

    # Portrait helpers
    def load_portrait(img_src):
        try:
            if img_src and hasattr(img_src, "read"):
                img_src.seek(0)
                return Image.open(img_src).convert("RGBA")
            if isinstance(img_src, str) and os.path.exists(img_src):
                with open(img_src, "rb") as f:
                    return Image.open(f).convert("RGBA")
        except Exception:
            pass
        if os.path.exists(DEFAULT_IMAGE):
            return Image.open(DEFAULT_IMAGE).convert("RGBA")
        return None

    def circular_glow(img):
        img = img.copy().resize(portrait_size)
        mask = Image.new("L", portrait_size, 0)
        ImageDraw.Draw(mask).ellipse((0, 0) + portrait_size, fill=255)
        glow = img.copy().filter(ImageFilter.GaussianBlur(12))
        out = Image.new("RGBA", portrait_size, (0, 0, 0, 0))
        out.paste(glow, (0, 0), mask)
        out.paste(img, (0, 0), mask)
        return out

    portrait = load_portrait(image_file)
    if portrait:
        final_portrait = circular_glow(portrait)
        image.paste(final_portrait, (card_width - portrait_size[0] - margin, margin), final_portrait)

    # Title
    x = margin
    y = margin
    draw.text((x, y), title_text, font=title_font, fill=theme["accent"])
    y += title_h + section_gap

    # Left column sections
    left_x = margin
    left_y = y
    left_max_w = left_col_width

    def draw_section(label: str, content: str, *, italic=False, bullets: Optional[List[str]] = None):
        nonlocal left_y
        draw.text((left_x, left_y), f"{label}:", font=section_font, fill=theme["text"])
        left_y += text_height(section_font) + label_gap

        if bullets is not None:
            lines, _ = measure_bullets_height(bullets, body_font, left_max_w - body_indent_px, line_gap, bullet_indent)
            for ln in lines:
                draw.text((left_x + body_indent_px, left_y), ln, font=body_font, fill=theme["text"])
                left_y += text_height(body_font) + line_gap
        else:
            f = italic_font if italic else body_font
            lines, _ = measure_paragraph_height(str(content), f, left_max_w - body_indent_px, line_gap)
            for ln in lines:
                draw.text((left_x + body_indent_px, left_y), ln, font=f, fill=theme["text"])
                left_y += text_height(f) + line_gap

        left_y += section_gap

    draw_section("Power", power)
    draw_section("Weakness", weakness)
    draw_section("Nemesis", nemesis)
    draw_section("Lair", lair)
    draw_section("Catchphrase", catchphrase, italic=True)
    draw_section("Crimes", "", bullets=crimes)
    draw_section("Threat Level", threat_level)
    draw_section("Faction", faction)

    # Origin (full width)
    y_origin = max(left_y, portrait_bottom + margin)
    draw.text((margin, y_origin), "Origin:", font=section_font, fill=theme["text"])
    y_origin += text_height(section_font) + label_gap

    origin_max_w = card_width - (margin * 2) - body_indent_px
    origin_lines, _ = measure_paragraph_height(origin_text, body_font, origin_max_w, line_gap)
    for ln in origin_lines:
        draw.text((margin + body_indent_px, y_origin), ln, font=body_font, fill=theme["text"])
        y_origin += text_height(body_font) + line_gap

    # Border
    image = ImageOps.expand(image, border=6, fill="white")

    # Save
    os.makedirs(CARD_FOLDER, exist_ok=True)
    safe_name = (villain.get("name", "villain") or "villain").replace(" ", "_").lower()
    outpath = os.path.join(CARD_FOLDER, f"{safe_name}_card.png")
    image.save(outpath)
    return outpath

# ===================== VISUAL PROMPT FLOW =====================

def _theme_style_line(villain: dict) -> str:
    return safe_theme_line(villain)

def generate_visual_prompt(villain):
    """
    Build a PG-13 visual prompt for DALL·E with explicit guardrails.
    """
    client = OpenAI()

    gender_hint = (villain.get("gender", "unknown") or "").lower()
    if "female" in gender_hint:
        gender_phrase = "feminine, graceful energy"
    elif "male" in gender_hint:
        gender_phrase = "masculine, powerful energy"
    elif "nonbinary" in gender_hint or "androgynous" in gender_hint:
        gender_phrase = "androgynous presence"
    else:
        gender_phrase = "mysterious energy"

    theme_line = _theme_style_line(villain)

    # Sanitize freeform fields before use
    origin_s = sanitize_for_images(villain.get("origin", ""))
    power_s  = sanitize_for_images(villain.get("power", ""))

    system_prompt = (
        "You are composing a PG-13-safe visual prompt for an image model. "
        "Describe ONLY appearance: color, mood, style, pose, clothing, atmosphere. "
        "NEVER include names, logos, flags, words, numbers, posters, or text. "
        "Exclude gore, graphic violence, self-harm, sexualization, nudity, minors, and hate symbols. "
        "Imply gender with adjectives (masculine/feminine/androgynous) or visuals. "
        "Output 1–2 cinematic sentences max."
    )

    user_prompt = (
        f"{gender_phrase}. {theme_line} "
        f"Origin vibe (PG-13 only): {origin_s} "
        f"Power vibe (PG-13 only): {power_s} "
        f"{QUALITY_HINT}"
    )

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=120,
        )
        visual_prompt = (response.choices[0].message.content or "").strip()
        st.session_state["visual_prompt"] = visual_prompt
        save_visual_prompt_to_log(villain.get('name', 'unknown'), visual_prompt)
        return visual_prompt
    except Exception as e:
        print(f"[Error generating visual prompt]: {e}")
        # Super-safe default
        fallback = (
            "Cinematic PG-13 villain portrait, 3/4 bust, dramatic lighting, detailed clothing and atmosphere, "
            "no text, no logos, no flags, no gore, no sexualization, no minors."
        )
        st.session_state["visual_prompt"] = fallback
        return fallback

def _decode_and_check_png(b64: str) -> bytes:
    raw = base64.b64decode(b64)
    with Image.open(io.BytesIO(raw)) as im:
        w, h = im.size
        if w != 1024 or h != 1024:
            raise ValueError(f"Unexpected image size {w}x{h}")
    return raw

def _gen_once(client: OpenAI, prompt: str, allow_style: bool = True):
    """
    Generate one image at 1024x1024 using base64 to avoid CDN/thumb issues.
    If allow_style is True, try a vivid style hint; otherwise omit for compatibility.
    """
    kwargs = dict(
        model="dall-e-3",
        prompt=prompt,
        n=1,
        size="1024x1024",
        response_format="b64_json",
    )
    if allow_style:
        kwargs["style"] = "vivid"
    return client.images.generate(**kwargs)

def _safe_placeholder(out_path: str) -> str:
    """
    Copies DEFAULT_IMAGE to the desired output path to keep app flow alive if both attempts fail.
    """
    try:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        if os.path.exists(DEFAULT_IMAGE):
            with Image.open(DEFAULT_IMAGE).convert("RGBA") as im:
                im.save(out_path)
            return out_path
    except Exception:
        pass
    img = Image.new("RGBA", (1024, 1024), (0, 0, 0, 255))
    img.save(out_path)
    return out_path

def generate_ai_portrait(villain):
    """
    1) Build sanitized visual prompt
    2) Try vivid generation
    3) If 400/safety → fallback to ultra-safe theme-only prompt without style
    4) If still fails → save placeholder to expected path
    """
    client = OpenAI()
    visual_prompt = generate_visual_prompt(villain)
    final_prompt = visual_prompt

    os.makedirs(IMAGE_FOLDER, exist_ok=True)
    vid = hash_villain(villain)
    img_path = os.path.join(IMAGE_FOLDER, f"ai_portrait_{vid}.png")

    image_calls = 0
    # Attempt 1 — with style
    try:
        resp = _gen_once(client, final_prompt, allow_style=True)
        image_calls += 1
        b64 = resp.data[0].b64_json
        png_bytes = _decode_and_check_png(b64)
        with open(img_path, "wb") as f:
            f.write(png_bytes)
        set_debug_info(context="DALL·E Image", prompt=final_prompt, cost_only=True, image_count=image_calls)
        return img_path
    except Exception as e1:
        # Attempt 2 — safe fallback, no style, no origin details
        print(f"[Image attempt 1 failed, retrying safe fallback] {e1}")
        safe_theme = safe_theme_line(villain)
        gender_hint = (villain.get("gender", "unknown") or "").lower()
        if "female" in gender_hint:
            gender_phrase = "feminine"
        elif "male" in gender_hint:
            gender_phrase = "masculine"
        elif "nonbinary" in gender_hint or "androgynous" in gender_hint:
            gender_phrase = "androgynous"
        else:
            gender_phrase = "mysterious"

        fallback_prompt = (
            f"PG-13 safe villain portrait, {gender_phrase} energy. {safe_theme} "
            "3/4 bust, dramatic cinematic lighting, detailed clothing, atmospheric background; "
            "no text, no logos, no flags, no gore, no sexualization, no minors. "
            f"{QUALITY_HINT}"
        )
        try:
            resp = _gen_once(client, fallback_prompt, allow_style=False)
            image_calls += 1
            b64 = resp.data[0].b64_json
            png_bytes = _decode_and_check_png(b64)
            with open(img_path, "wb") as f:
                f.write(png_bytes)
            set_debug_info(context="DALL·E Image (fallback)", prompt=fallback_prompt, cost_only=True, image_count=image_calls)
            return img_path
        except Exception as e2:
            print(f"[Image attempt 2 failed; using placeholder] {e2}")
            placeholder = _safe_placeholder(img_path)
            try:
                set_debug_info(context="DALL·E Image (placeholder)", prompt="(placeholder due to safety)", cost_only=True, image_count=image_calls or 1)
            except Exception:
                pass
            return placeholder

__all__ = [
    "create_villain_card",
    "save_villain_to_log",
    "generate_ai_portrait",
    "STYLE_THEMES"
]

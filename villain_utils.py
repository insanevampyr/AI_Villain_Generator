from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import os
import datetime
import textwrap
import streamlit as st
from openai import OpenAI
import base64
import io
from typing import List, Tuple

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
FONT_PATH     = "C:/Users/VampyrLee/Desktop/AI_Villain/fonts/ttf"
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

# ========== TEXT MEASUREMENT HELPERS (pixel-accurate wrapping) ==========

def load_fonts():
    """
    Prefer your bundled DejaVu fonts; fall back to PIL default if missing.
    Font sizes tuned for readability and social sharing.
    """
    try:
        title_font   = ImageFont.truetype(f"{FONT_PATH}/DejaVuSans-Bold.ttf", 64)   # Name
        section_font = ImageFont.truetype(f"{FONT_PATH}/DejaVuSans-Bold.ttf", 38)   # Section headings
        body_font    = ImageFont.truetype(f"{FONT_PATH}/DejaVuSans.ttf", 30)        # Body text
        italic_font  = ImageFont.truetype(f"{FONT_PATH}/DejaVuSans-Oblique.ttf", 30)
    except IOError:
        title_font = section_font = body_font = italic_font = ImageFont.load_default()
    return title_font, section_font, body_font, italic_font

def text_height(font: ImageFont.FreeTypeFont, text: str) -> int:
    # Robust height using bbox (works better than getsize on new PIL)
    if not text:
        return 0
    bbox = font.getbbox("Ay")
    return bbox[3] - bbox[1]

def measure_line_width(font: ImageFont.FreeTypeFont, text: str) -> int:
    if not text:
        return 0
    bbox = font.getbbox(text)
    return bbox[2] - bbox[0]

def wrap_text_pixels(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> List[str]:
    """
    Wrap text based on pixel width (not characters). Keeps words intact.
    """
    words = (text or "").split()
    lines: List[str] = []
    current = []
    for w in words:
        test = (" ".join(current + [w])).strip()
        if measure_line_width(font, test) <= max_width or not current:
            current.append(w)
        else:
            lines.append(" ".join(current))
            current = [w]
    if current:
        lines.append(" ".join(current))
    return lines

def measure_paragraph_height(text: str, font: ImageFont.FreeTypeFont, max_width: int, line_gap: int) -> Tuple[List[str], int]:
    """
    Returns (wrapped_lines, total_height_px)
    """
    lines = []
    total_h = 0
    for raw in (text or "").split("\n"):
        wrapped = wrap_text_pixels(raw, font, max_width) if raw.strip() else [""]
        for ln in wrapped:
            lines.append(ln)
            total_h += text_height(font) + line_gap
    return lines, total_h

def measure_bullets_height(items: List[str], font: ImageFont.FreeTypeFont, max_width: int, line_gap: int, bullet_indent: int) -> Tuple[List[str], int]:
    """
    Wrap each bullet item; prepend "• " on first line, indent following lines.
    Returns (render_lines, total_height)
    """
    render_lines = []
    total_h = 0
    bullet = "• "
    space_w = measure_line_width(font, " " * bullet_indent)

    for item in (items or []):
        first_prefix = bullet
        rest_prefix  = " " * bullet_indent
        raw_lines = wrap_text_pixels(str(item), font, max_width - measure_line_width(font, first_prefix))
        if not raw_lines:
            raw_lines = [""]
        # First line with bullet
        render_lines.append(first_prefix + raw_lines[0])
        total_h += text_height(font) + line_gap
        # Continuation lines with indent
        for ln in raw_lines[1:]:
            render_lines.append(rest_prefix + ln)
            total_h += text_height(font) + line_gap
    return render_lines, total_h

# ========== CARD BUILDER ==========

def create_villain_card(villain, image_file=None, theme_name="dark"):
    """
    Dynamic-height, social-ready villain card.
    Layout:
      - Title (left) + circular portrait (top-right)
      - Meta sections (Power → Faction) in left column beside the portrait
      - Origin uses full width BELOW the portrait (wraps naturally)
    """
    theme = STYLE_THEMES.get(theme_name, STYLE_THEMES["dark"])

    # --- Layout constants (tuned for readability) ---
    card_width      = 1200                # wider for clarity on socials
    margin          = 40
    gutter          = 24                  # space between columns
    portrait_size   = (320, 320)          # large, crisp portrait
    section_gap     = 14                  # gap after each section block
    label_gap       = 6                   # gap after section title
    line_gap        = 6                   # line spacing within paragraphs
    bullet_indent   = 3                   # indent chars after "• " for wrapped lines
    left_col_width  = card_width - (margin * 3) - portrait_size[0]  # space beside the portrait
    body_indent_px  = 10                  # small indent for body lines

    # --- Fonts ---
    title_font, section_font, body_font, italic_font = load_fonts()

    # --- Normalize inputs / fallbacks ---
    catchphrase = villain.get("catchphrase", "")
    if not catchphrase or "Expecting value" in catchphrase:
        catchphrase = "Unknown"
    crimes = villain.get("crimes", [])
    if isinstance(crimes, str):
        crimes = [crimes] if crimes else []
    # Ensure text fields exist
    power        = villain.get("power", "Unknown")
    weakness     = villain.get("weakness", "Unknown")
    nemesis      = villain.get("nemesis", "Unknown")
    lair         = villain.get("lair", "Unknown")
    threat_level = villain.get("threat_level", "Unknown")
    faction      = villain.get("faction", "Unknown")
    origin_text  = villain.get("origin", "Unknown")

    # --- Measure pass (compute total height before drawing) ---
    # Title line
    title_text = f"{villain.get('name','Unknown')} aka {villain.get('alias','Unknown')}"
    title_h = text_height(title_font)

    # Meta sections go in left column under the title
    def measure_section_block(label: str, content: str, *, italic=False, bullets: List[str] = None) -> int:
        h = 0
        # Label
        h += text_height(section_font) + label_gap
        # Content (either paragraph or bullets)
        if bullets is not None:
            render_lines, block_h = measure_bullets_height(bullets, body_font, left_col_width - body_indent_px, line_gap, bullet_indent)
            h += block_h
        else:
            font_used = italic_font if italic else body_font
            _, block_h = measure_paragraph_height(str(content), font_used, left_col_width - body_indent_px, line_gap)
            h += block_h
        # Section gap
        h += section_gap
        return h

    meta_height = 0
    meta_height += measure_section_block("Power", power)
    meta_height += measure_section_block("Weakness", weakness)
    meta_height += measure_section_block("Nemesis", nemesis)
    meta_height += measure_section_block("Lair", lair)
    meta_height += measure_section_block("Catchphrase", catchphrase, italic=True)
    meta_height += measure_section_block("Crimes", "", bullets=crimes)
    meta_height += measure_section_block("Threat Level", threat_level)
    meta_height += measure_section_block("Faction", faction)

    portrait_bottom = margin + portrait_size[1]
    left_column_bottom = margin + title_h + section_gap + meta_height
    # Origin starts below whichever is lower: text column or portrait bottom
    origin_start_y = max(left_column_bottom, portrait_bottom + margin)
    # Origin is FULL WIDTH under the portrait
    origin_label_h = text_height(section_font) + label_gap
    _, origin_block_h = measure_paragraph_height(origin_text, body_font, card_width - (margin * 2) - body_indent_px, line_gap)
    origin_total_h = origin_label_h + origin_block_h + section_gap

    # Final canvas height = top margin + (whatever is higher among left column & portrait)
    # + origin block + bottom margin
    card_height = origin_start_y + origin_total_h + margin

    # --- Draw pass ---
    image = Image.new("RGBA", (card_width, card_height), (0, 0, 0, 255))
    draw = ImageDraw.Draw(image)

    # Portrait (circular with soft glow)
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
        # Glow
        glow = img.copy()
        glow = glow.filter(ImageFilter.GaussianBlur(12))
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

    # Meta sections in left column (beside portrait)
    left_x = margin
    left_y = y
    left_max_w = left_col_width

    def draw_section(label: str, content: str, *, italic=False, bullets: List[str] = None):
        nonlocal left_y
        # Label
        draw.text((left_x, left_y), f"{label}:", font=section_font, fill=theme["text"])
        left_y += text_height(section_font) + label_gap

        # Content
        if bullets is not None:
            lines, _h = measure_bullets_height(bullets, body_font, left_max_w - body_indent_px, line_gap, bullet_indent)
            for ln in lines:
                draw.text((left_x + body_indent_px, left_y), ln, font=body_font, fill=theme["text"])
                left_y += text_height(body_font) + line_gap
        else:
            f = italic_font if italic else body_font
            lines, _h = measure_paragraph_height(str(content), f, left_max_w - body_indent_px, line_gap)
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

    # Origin (full width) under portrait
    y_origin = max(left_y, portrait_bottom + margin)
    draw.text((margin, y_origin), "Origin:", font=section_font, fill=theme["text"])
    y_origin += text_height(section_font) + label_gap

    origin_max_w = card_width - (margin * 2) - body_indent_px
    origin_lines, _ = measure_paragraph_height(origin_text, body_font, origin_max_w, line_gap)
    for ln in origin_lines:
        draw.text((margin + body_indent_px, y_origin), ln, font=body_font, fill=theme["text"])
        y_origin += text_height(body_font) + line_gap

    # Subtle outer border for a clean, share-ready finish
    image = ImageOps.expand(image, border=6, fill="white")

    # Save
    os.makedirs(CARD_FOLDER, exist_ok=True)
    safe_name = (villain.get("name", "villain") or "villain").replace(" ", "_").lower()
    outpath = os.path.join(CARD_FOLDER, f"{safe_name}_card.png")
    image.save(outpath)
    return outpath

# ====== Visual prompt flow (unchanged, just organized) ======

def _theme_style_line(villain: dict) -> str:
    t = (villain.get("theme") or "").lower()
    style = THEME_VISUALS.get(t)
    return f"Theme style: {style}." if style else ""

def generate_visual_prompt(villain):
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

    system_prompt = (
        "Convert villain data into a DALL·E 3 visual prompt. Describe ONLY appearance: color, mood, style, pose, "
        "clothing, atmosphere. NEVER include names, logos, words, numbers, posters, or text. Imply gender with "
        "adjectives (masculine/feminine/androgynous) or visuals. 1–2 cinematic sentences. Avoid anything that "
        "could render as written text."
    )

    theme_line = _theme_style_line(villain)

    user_prompt = (
        f"{gender_phrase}. {theme_line} "
        f"Origin: {villain.get('origin', '')} "
        f"Power: {villain.get('power', '')} "
        f"Faction: {villain.get('faction', '')} "
        f"Threat Level: {villain.get('threat_level', '')}"
    )

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.8,
            max_tokens=150
        )
        visual_prompt = response.choices[0].message.content.strip()
        # Append strong portrait quality guidance
        visual_prompt = f"{visual_prompt}\n\n{QUALITY_HINT}"
        st.session_state["visual_prompt"] = visual_prompt
        save_visual_prompt_to_log(villain.get('name', 'unknown'), visual_prompt)
        return visual_prompt

    except Exception as e:
        print(f"[Error generating visual prompt]: {e}")
        return (
            "A dramatic, wordless villain portrait with cinematic lighting and energy, "
            "photorealistic, 3/4 bust, depth of field, NOT an icon or logo or sticker."
        )

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
    try:
        return client.images.generate(**kwargs)
    except Exception:
        if allow_style:
            kwargs.pop("style", None)
            return client.images.generate(**kwargs)
        raise

def generate_ai_portrait(villain):
    client = OpenAI()
    visual_prompt = generate_visual_prompt(villain)
    final_prompt = visual_prompt

    os.makedirs(IMAGE_FOLDER, exist_ok=True)
    vid = hash_villain(villain)
    img_path = os.path.join(IMAGE_FOLDER, f"ai_portrait_{vid}.png")

    image_calls = 0
    try:
        # First attempt (with vivid style if supported)
        response = _gen_once(client, final_prompt, allow_style=True)
        image_calls += 1
        b64 = response.data[0].b64_json
        png_bytes = _decode_and_check_png(b64)
    except Exception:
        # One retry without style + even stronger prompt suffix
        retry_prompt = final_prompt + (
            "\n\nUltra-detailed cinematic portrait, film still, realistic lensing and lighting, "
            "NOT an icon/logo/sticker, no text."
        )
        response = _gen_once(client, retry_prompt, allow_style=False)
        image_calls += 1
        b64 = response.data[0].b64_json
        png_bytes = _decode_and_check_png(b64)

    with open(img_path, "wb") as f:
        f.write(png_bytes)

    # Record the real image call count (1 normally; 2 if we retried)
    try:
        set_debug_info(
            context="DALL·E Image",
            prompt=final_prompt,
            cost_only=True,
            image_count=image_calls
        )
    except Exception:
        pass

    return img_path


__all__ = [
    "create_villain_card",
    "save_villain_to_log",
    "generate_ai_portrait",
    "STYLE_THEMES"
]

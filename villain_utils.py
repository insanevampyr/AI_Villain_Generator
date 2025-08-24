# villain_utils.py
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import os
import datetime
import streamlit as st
from openai import OpenAI
import base64
import io
import re
from typing import List, Tuple, Optional
from optimization_utils import hash_villain, set_debug_info, dalle_price

try:
    import pytesseract
    _HAS_OCR = True
except Exception:
    _HAS_OCR = False

def _contains_text(png_bytes: bytes) -> bool:
    """Detect if an image has visible text (requires pytesseract)."""
    if not _HAS_OCR:
        return False
    try:
        with Image.open(io.BytesIO(png_bytes)) as im:
            im = im.convert("L")  # grayscale
            txt = pytesseract.image_to_string(im, config="--psm 6")
            return bool(re.search(r"[A-Za-z0-9]{4,}", txt))
    except Exception:
        return False


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
CARD_FOLDER     = "C:/Users/VampyrLee/Desktop/AI_Villain/villain_cards"
IMAGE_FOLDER    = "C:/Users/VampyrLee/Desktop/AI_Villain/villain_images"
DEFAULT_IMAGE   = "C:/Users/VampyrLee/Desktop/AI_Villain/assets/AI_Villain_logo.png"
FONT_PATH       = "C:/Users/VampyrLee/Desktop/AI_Villain/fonts/ttf"
LOG_FOLDER      = "C:/Users/VampyrLee/Desktop/AI_Villain/villain_logs"
DOSSIER_TEXTURE = "C:/Users/VampyrLee/Desktop/AI_Villain/assets/dossier_paper.png"

# Footer / branding
QR_STAMP      = "C:/Users/VampyrLee/Desktop/AI_Villain/assets/qr_stamp.png"   # <-- your QR file
HASHTAG_TEXT  = "#AIVillains"
FOOTER_BAND_H = 96    # reserved footer height so text never overlaps
QR_SIZE       = 88    # px
FOOTER_PAD    = 24

# Threat meter skull icon (your new one)
SKULL_ICON = "C:/Users/VampyrLee/Desktop/AI_Villain/assets/skull_icon.png"
SKULL_SIZE = 22   # auto-scaled again by bar height

# Portrait quality guidance
QUALITY_HINT = (
    "Cinematic bust portrait, 3/4 view, photorealistic skin texture, dramatic lighting, "
    "depth of field, rich background bokeh, intricate detail, volumetric light, high dynamic range. "
    "absolutely no words, no text, no typography, no letters, no numbers, "
    "no captions, no subtitles, no watermarks, no signatures, no graffiti, "
    "no posters, no billboards, no logos, no signage, no diagrams, no labels, no UI, no HUD, no interface overlays; "
    "NOT an icon, NOT a sticker, NOT flat vector art"
)



# Theme → visual style boosters
THEME_VISUALS = {
    "funny": "bright, comedic composition, exaggerated expressions, whimsical props, saturated but balanced colors",
    "satirical": "playful yet sharp composition, clever visual irony, illustrative vibe (no posters, no text blocks)",
    "dark": "low-key lighting, chiaroscuro, cold palette, occult hints, oppressive atmosphere",
    "epic": "grand scale, celestial glow, ethereal atmosphere, ultra-detailed, sweeping cinematic lighting",
    "mythic": "ancient textures, carved stone, sacred motifs, weathered materials, natural backdrops",
    "sci-fi": "clean industrial design, emissive materials, precise geometry, cool palette (no control panels, no monitors)",
    "cyberpunk": "neon grime, rain-slick surfaces, retro-futurist color haze and rimlight (no holograms, no signage, no billboards)",
    "chaotic": "motion blur, double exposure, textured light leaks (no glitch text, no UI elements)",
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

BANNED_REGEXES = [
    r"\b(blood|bloody|bloodied|gore|gory|guts|entrails|decapitat\w*|behead\w*|mutilat\w*|tortur\w*|maim\w*|"
    r"throat\s*slit|knife\s*to\s*throat|dismember\w*|severed)\b",
    r"\b(suicide|self[-\s]*harm|overdose|self[-\s]*mutilation)\b",
    r"\b(rape|sexual|sex|nude|nudity|breasts?|nipples?|genitals?|explicit|fetish)\b",
    r"\b(child|children|minor|underage|schoolgirl|teen\b)\b",
    r"\b(hate\s*symbol|nazi|swastika|kkk|lynch\w*)\b",
    r"[\"“”‘’][^\"“”‘’]{0,80}[\"“”‘’]",
]

def sanitize_for_images(text: str, max_len: int = 300) -> str:
    if not text:
        return ""
    s = re.sub(r"\s+", " ", text).strip()
    for rx in BANNED_REGEXES:
        s = re.sub(rx, "redacted", s, flags=re.IGNORECASE)
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
    candidates = [
        os.path.join(FONT_PATH, filename),
        os.path.join("fonts", "ttf", filename),
        os.path.join(".", "fonts", "ttf", filename),
    ]
    win_map = {
        "DejaVuSans.ttf":         r"C:\Windows\Fonts\arial.ttf",
        "DejaVuSans-Bold.ttf":    r"C:\Windows\Fonts\arialbd.ttf",
        "DejaVuSans-Oblique.ttf": r"C:\Windows\Fonts\ariali.ttf",
    }
    if os.name == "nt" and filename in win_map:
        candidates.append(win_map[filename])
    try:
        import PIL
        pil_fonts = os.path.join(os.path.dirname(PIL.__file__), "fonts")
        candidates.append(os.path.join(pil_fonts, filename))
    except Exception:
        pass
    return _first_existing(candidates)

def load_fonts():
    names = {
        "title":   "DejaVuSans-Bold.ttf",
        "subtitle":"DejaVuSans-Bold.ttf",
        "section": "DejaVuSans-Bold.ttf",
        "body":    "DejaVuSans.ttf",
        "italic":  "DejaVuSans-Oblique.ttf",
    }
    paths = {k: _resolve_font_path(v) for k, v in names.items()}

    SIZE_TITLE_BASE    = 72
    SIZE_SUBTITLE_BASE = 52
    SIZE_SECTION       = 44
    SIZE_BODY          = 34

    def _load(path, size, fallback_name):
        if path:
            try:
                return ImageFont.truetype(path, size)
            except Exception as e:
                print(f"[font] Failed to load {path}: {e}")
        print(f"[font] WARNING: Using PIL default for {fallback_name}. Text may look small if TrueType not found.")
        return ImageFont.load_default()

    title_font_base    = _load(paths["title"],    SIZE_TITLE_BASE,    "title")
    subtitle_font_base = _load(paths["subtitle"], SIZE_SUBTITLE_BASE, "subtitle")
    section_font       = _load(paths["section"],  SIZE_SECTION,       "section")
    body_font          = _load(paths["body"],     SIZE_BODY,          "body")
    italic_font        = _load(paths["italic"],   SIZE_BODY,          "italic")

    try:
        set_debug_info(
            context="Card Fonts",
            prompt=f"title={paths['title']}, subtitle={paths['subtitle']}, section={paths['section']}, body={paths['body']}, italic={paths['italic']}",
            cost_only=True
        )
    except Exception:
        pass

    return title_font_base, subtitle_font_base, section_font, body_font, italic_font

# ===================== TEXT HELPERS =====================

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
    """
    Returns render lines with '• ' prefix only for the first line of each bullet.
    Continuation lines are prefixed with spaces (no bullet).
    """
    render_lines = []
    total = 0
    bullet = "• "
    for item in (items or []):
        first_prefix = bullet
        rest_prefix  = " " * bullet_indent
        first_w = measure_line_width(font, first_prefix)
        raw_lines = wrap_text_pixels(str(item), font, max_width - first_w) or [""]
        # First line with bullet prefix
        render_lines.append(first_prefix + raw_lines[0])
        total += text_height(font) + line_gap
        # Continuation lines (indented, no bullet)
        for ln in raw_lines[1:]:
            render_lines.append(rest_prefix + ln)
            total += text_height(font) + line_gap
    return render_lines, total

# ========== ADAPTIVE TITLE (two-line + scaling) ==========

def _adaptive_title_fonts(name_txt: str, aka_txt: str, title_font_base: ImageFont.FreeTypeFont,
                          subtitle_font_base: ImageFont.FreeTypeFont, max_width: int,
                          max_name_lines: int = 2, max_aka_lines: int = 2,
                          min_title: int = 44, min_subtitle: int = 34):
    def _infer_path(font_obj):
        return getattr(font_obj, "path", _resolve_font_path("DejaVuSans-Bold.ttf"))

    title_path    = _infer_path(title_font_base)
    subtitle_path = _infer_path(subtitle_font_base)

    size_title    = 72
    size_subtitle = 52

    def mk_font(path, size):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            return ImageFont.load_default()

    while True:
        title_font    = mk_font(title_path, size_title)
        subtitle_font = mk_font(subtitle_path, size_subtitle)

        name_lines = wrap_text_pixels(name_txt, title_font, max_width)
        aka_lines  = wrap_text_pixels(aka_txt,  subtitle_font, max_width)

        too_long = len(name_lines) > max_name_lines or len(aka_lines) > max_aka_lines

        if too_long and (size_title > min_title or size_subtitle > min_subtitle):
            if size_title > min_title:
                size_title -= 4
            if size_subtitle > min_subtitle:
                size_subtitle -= 4
            continue

        return title_font, subtitle_font, name_lines, aka_lines

# ===================== SPECIAL DRAW HELPERS =====================

def draw_glow_text(base_img: Image.Image, xy: Tuple[int, int], text: str, font: ImageFont.FreeTypeFont,
                   glow_color=(255, 255, 255, 160), text_color=(255, 255, 255, 255), radius=6):
    layer = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.text(xy, text, font=font, fill=glow_color)
    layer = layer.filter(ImageFilter.GaussianBlur(radius))
    base_img.alpha_composite(layer)
    d2 = ImageDraw.Draw(base_img)
    d2.text(xy, text, font=font, fill=text_color)

# ===================== THREAT METER =====================

THREAT_LEVELS = ["Laughably Low", "Moderate", "High", "Extreme"]
THREAT_COLORS = [
    (56, 200, 90, 255),     # Low
    (255, 208, 0, 255),     # Moderate
    (255, 140, 0, 255),     # High
    (220, 20, 60, 255),     # Extreme (crimson blood red)

]

THREAT_METER_HEIGHT = 100  # bar + labels

def _normalize_threat_name(name: str) -> str:
    if not name:
        return "Moderate"
    s = name.strip().lower()
    if s.startswith("laugh") or s.startswith("low"):
        return "Laughably Low"
    if s.startswith("mod"):
        return "Moderate"
    if s.startswith("high"):
        return "High"
    if s.startswith("ext") or s.startswith("cat") or s.startswith("apoc"):
        return "Extreme"
    for lvl in THREAT_LEVELS:
        if lvl.lower() == s:
            return lvl
    return "Moderate"

def _draw_segment_with_glow(base_img: Image.Image, rect: Tuple[int,int,int,int], color: Tuple[int,int,int,int]):
    x1, y1, x2, y2 = rect
    w, h = x2 - x1, y2 - y1
    layer = Image.new("RGBA", (w, h), (0,0,0,0))
    d = ImageDraw.Draw(layer)

    d.rounded_rectangle([(0,0),(w-1,h-1)], radius=8, fill=color)

    glow = Image.new("RGBA", (w, h), (255,255,255,0))
    dglow = ImageDraw.Draw(glow)
    dglow.rounded_rectangle([(3,3),(w-4,h-4)], radius=6, fill=(255,255,255,40))
    glow = glow.filter(ImageFilter.GaussianBlur(5))
    layer = Image.alpha_composite(layer, glow)

    hl = Image.new("RGBA", (w, h), (255,255,255,0))
    dhl = ImageDraw.Draw(hl)
    dhl.rectangle([(int(w*0.12), 2), (int(w*0.20), h-3)], fill=(255,255,255,50))
    hl = hl.filter(ImageFilter.GaussianBlur(6))
    layer = Image.alpha_composite(layer, hl)

    if color == THREAT_COLORS[2] or color == THREAT_COLORS[3]:
        tx = Image.new("RGBA", (w, h), (0,0,0,0))
        dtx = ImageDraw.Draw(tx)
        for k in range(-h, w, 8):
            dtx.line([(k, h), (k + h, 0)], fill=(255,255,255,35), width=2)
        tx = tx.filter(ImageFilter.GaussianBlur(1))
        layer = Image.alpha_composite(layer, tx)

    base_img.paste(layer, (x1, y1), layer)

def _paste_skull_icon(img: Image.Image, cx: int, cy: int, size: int) -> bool:
    if not os.path.exists(SKULL_ICON):
        return False
    try:
        icon = Image.open(SKULL_ICON).convert("RGBA")
        icon = icon.resize((size, size), Image.LANCZOS)
        x = cx - size // 2
        y = cy - size // 2
        img.paste(icon, (x, y), icon)
        return True
    except Exception:
        return False

def _draw_tiny_skull_with_crossbones(draw: ImageDraw.ImageDraw, cx: int, cy: int, scale: int = 9, color=(255,255,255,255)):
    """Very small vector fallback ☠ so we never show a dot/X if the PNG is missing."""
    s = scale
    # skull
    draw.ellipse((cx-2*s, cy-2*s, cx+2*s, cy+2*s), outline=color, width=max(1, s//3))
    draw.ellipse((cx-s//2, cy-s//2, cx, cy), fill=color)            # left eye
    draw.ellipse((cx, cy-s//2, cx+s//2, cy), fill=color)            # right eye
    draw.rectangle((cx-s//3, cy+s//3, cx+s//3, cy+s//3 + s//2), fill=color)
    # crossbones
    draw.line((cx-3*s, cy+2*s, cx+3*s, cy-2*s), fill=color, width=max(1, s//2))
    draw.line((cx-3*s, cy-2*s, cx+3*s, cy+2*s), fill=color, width=max(1, s//2))


def draw_threat_meter(img: Image.Image, draw: ImageDraw.ImageDraw, x: int, y: int, width: int, level_name: str, font: ImageFont.FreeTypeFont):
    """
    Draw a 4-section labeled meter. Lights all segments up to current level.
    """
    # geometry
    bar_h   = 46
    seg_gap = 8
    seg_w   = (width - seg_gap * 3) // 4

    level = _normalize_threat_name(level_name)
    try:
        idx = THREAT_LEVELS.index(level)
    except ValueError:
        idx = 1

    # segments (with glow)
    for i, _ in enumerate(THREAT_LEVELS):
        sx = x + i * (seg_w + seg_gap)
        rect = (sx, y, sx + seg_w, y + bar_h)
        draw.rounded_rectangle(rect, radius=8, fill=(40, 40, 40, 255))
        if i <= idx:
            _draw_segment_with_glow(img, rect, THREAT_COLORS[i])

    # labels under segments (auto-fit)
    label_y   = y + bar_h + 8
    base_size = int(getattr(font, "size", 32))
    path_body = getattr(font, "path", _resolve_font_path("DejaVuSans.ttf"))

    for i, lab in enumerate(THREAT_LEVELS):
        text = lab
        tw   = measure_line_width(font, text)
        if tw > seg_w - 10:
            text = {"Laughably Low": "Low"}.get(lab, lab)
            tw   = measure_line_width(font, text)

        used_font = font
        if tw > seg_w - 10 and path_body:
            size = base_size
            while size > 20:
                try:
                    f2 = ImageFont.truetype(path_body, size)
                except Exception:
                    break
                if measure_line_width(f2, text) <= seg_w - 10:
                    used_font = f2
                    break
                size -= 2

        sx  = x + i * (seg_w + seg_gap) + seg_w // 2
        col = (230,230,230,255) if i <= idx else (160,160,160,255)
        tw  = measure_line_width(used_font, text)
        draw.text((sx - tw // 2, label_y), text, font=used_font, fill=col)

# ===================== CARD BUILDER =====================

def _draw_footer_branding(img: Image.Image, draw: ImageDraw.ImageDraw, body_font: ImageFont.FreeTypeFont):
    """Bottom-left hashtag + bottom-right QR (if present)."""
    w, h = img.size

    # Hashtag (bottom-left)
    small_font = body_font
    try:
        # ensure it's not huge
        path_body = getattr(body_font, "path", _resolve_font_path("DejaVuSans.ttf"))
        small_font = ImageFont.truetype(path_body, max(22, min(28, getattr(body_font, "size", 34))))
    except Exception:
        pass

    ht = text_height(small_font)
    draw.text((FOOTER_PAD, h - FOOTER_PAD - ht), HASHTAG_TEXT, font=small_font, fill=(200,200,200,255))

    # QR (bottom-right)
    if os.path.exists(QR_STAMP):
        try:
            qr = Image.open(QR_STAMP).convert("RGBA").resize((QR_SIZE, QR_SIZE), Image.LANCZOS)
            img.paste(qr, (w - FOOTER_PAD - QR_SIZE, h - FOOTER_PAD - QR_SIZE), qr)
        except Exception:
            pass


def _measure_origin_with_dropcap(origin_text: str, body_font: ImageFont.FreeTypeFont,
                                 origin_wrap_w: int, line_gap: int, body_indent_px: int) -> Tuple[int, dict]:
    text = origin_text or ""
    if not text:
        return 0, {"lines": [], "drop_char": "", "drop_w": 0, "drop_h": 0, "wrap_lines": 0, "dropcap_size": 0}

    stripped = text.lstrip()
    leading_ws = text[:len(text) - len(stripped)]
    drop_char = stripped[0]
    rest_text = leading_ws + stripped[1:]

    body_h = text_height(body_font)
    dropcap_size = int(body_h * 3.1)
    path_body = getattr(body_font, "path", _resolve_font_path("DejaVuSans.ttf"))
    try:
        drop_font = ImageFont.truetype(path_body, dropcap_size)
    except Exception:
        drop_font = body_font
    drop_w = measure_line_width(drop_font, drop_char)
    drop_h = text_height(drop_font)

    wrap_lines = max(2, min(3, (drop_h + line_gap) // (body_h + line_gap)))

    words = (rest_text or "").split()
    lines = []
    current = ""
    while words:
        word = words.pop(0)
        candidate = (current + " " + word).strip()
        max_w = origin_wrap_w - (drop_w + 12) if len(lines) < wrap_lines else origin_wrap_w
        if measure_line_width(body_font, candidate) <= max_w:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)

    height = len(lines) * (body_h + line_gap)
    return height, {
        "lines": lines,
        "drop_char": drop_char,
        "drop_w": drop_w,
        "drop_h": drop_h,
        "wrap_lines": wrap_lines,
        "dropcap_size": dropcap_size
    }

def create_villain_card(villain, image_file=None, theme_name="dark"):
    theme = STYLE_THEMES.get(theme_name, STYLE_THEMES["dark"])
    bullet_color = (255, 75, 75, 255)  # blood-red bullets

    # Layout
    card_width      = 1200
    margin          = 40
    portrait_size   = (400, 400)
    section_gap     = 22
    label_gap       = 8
    line_gap        = 8
    title_line_gap  = 6
    bullet_indent   = 3
    body_indent_px  = 10
    left_col_width  = card_width - (margin * 3) - portrait_size[0]

    # Fonts
    title_font_base, subtitle_font_base, section_font, body_font, italic_font = load_fonts()

    # Data
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

    name_text = str(villain.get('name', 'Unknown') or 'Unknown').strip()
    alias_text = str(villain.get('alias', 'Unknown') or 'Unknown').strip()
    aka_text = f"aka {alias_text}"

    # Adaptive title
    title_font, subtitle_font, name_lines, aka_lines = _adaptive_title_fonts(
        name_text, aka_text, title_font_base, subtitle_font_base, left_col_width
    )

    # Accent glow for catchphrase
    accent_rgba = tuple(int(theme["accent"].lstrip("#")[i:i+2], 16) for i in (0,2,4)) + (140,)

    # Measure sections (Threat last)
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
    meta_height += measure_section("Faction", faction)
    meta_height += text_height(section_font) + label_gap + THREAT_METER_HEIGHT + section_gap  # threat meter

    # Title block height
    title_h = 0
    for ln in name_lines:
        title_h += text_height(title_font) + title_line_gap
    for ln in aka_lines:
        title_h += text_height(subtitle_font) + title_line_gap
    if title_h > 0:
        title_h -= title_line_gap

    portrait_bottom = margin + portrait_size[1]
    left_column_bottom = margin + title_h + section_gap + meta_height
    origin_start_y = max(left_column_bottom, portrait_bottom + margin)

    # Origin measurement (with drop cap)
    origin_label_h = text_height(section_font) + label_gap
    origin_wrap_w = card_width - (margin * 2) - body_indent_px
    origin_h, origin_info = _measure_origin_with_dropcap(origin_text, body_font, origin_wrap_w, line_gap, body_indent_px)
    origin_total_h = origin_label_h + origin_h + section_gap

    # Total height includes footer band so nothing overlaps the QR/hashtag
    card_height = origin_start_y + origin_total_h + FOOTER_BAND_H + margin

    # Background: dark + dossier overlay
    image = Image.new("RGBA", (card_width, card_height), (8, 8, 8, 255))
    if os.path.exists(DOSSIER_TEXTURE):
        tex = Image.open(DOSSIER_TEXTURE).convert("RGBA")
        tex = ImageOps.fit(tex, (card_width, card_height))
        alpha = Image.new("L", tex.size, 64)  # ~25%
        tex.putalpha(alpha)
        image.alpha_composite(tex)
    draw = ImageDraw.Draw(image)

    # Portrait with glow
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

    def circular_with_glow(img):
        img = img.copy().resize(portrait_size)
        mask = Image.new("L", portrait_size, 0)
        ImageDraw.Draw(mask).ellipse((0, 0) + portrait_size, fill=255)

        glow_size = (portrait_size[0] + 48, portrait_size[1] + 48)
        glow = Image.new("RGBA", glow_size, (255, 255, 255, 0))
        glow_mask = Image.new("L", glow_size, 0)
        ImageDraw.Draw(glow_mask).ellipse((0, 0) + glow_size, fill=180)
        glow_blur = glow_mask.filter(ImageFilter.GaussianBlur(18))
        glow_img = Image.new("RGBA", glow_size, (255, 255, 255, 80))
        glow = Image.composite(glow_img, glow, glow_blur)

        out = Image.new("RGBA", glow_size, (0, 0, 0, 0))
        out.paste(glow, (0, 0), glow)
        offset = ((glow_size[0] - portrait_size[0]) // 2, (glow_size[1] - portrait_size[1]) // 2)
        circ = Image.new("RGBA", portrait_size, (0, 0, 0, 0))
        circ.paste(img, (0, 0), mask)
        out.paste(circ, offset, mask)
        return out

    portrait = load_portrait(image_file)
    if portrait:
        final_portrait = circular_with_glow(portrait)
        image.paste(final_portrait, (card_width - final_portrait.size[0] - margin, margin), final_portrait)

    # Title
    x = margin
    y = margin
    for ln in name_lines:
        draw.text((x, y), ln, font=title_font, fill=theme["accent"])
        y += text_height(title_font) + title_line_gap
    for ln in aka_lines:
        draw.text((x, y), ln, font=subtitle_font, fill=theme["text"])
        y += text_height(subtitle_font) + title_line_gap
    y += section_gap

    # Left column sections
    left_x = margin
    left_y = y
    left_max_w = left_col_width

    def draw_bulleted_lines(lines: List[str]):
        nonlocal left_y
        for ln in lines:
            if ln.startswith("• "):
                dot_radius = 5
                dot_x = left_x + body_indent_px
                dot_y = left_y + text_height(body_font) // 2
                draw.ellipse((dot_x - dot_radius, dot_y - dot_radius, dot_x + dot_radius, dot_y + dot_radius), fill=bullet_color)
                text_x = dot_x + dot_radius * 2 + 10
                draw.text((text_x, left_y), ln[2:], font=body_font, fill=theme["text"])
            else:
                cont_x = left_x + body_indent_px + (5 * 2) + 10
                draw.text((cont_x, left_y), ln, font=body_font, fill=theme["text"])
            left_y += text_height(body_font) + line_gap

    def draw_section(label: str, content: str, *, italic=False, bullets: Optional[List[str]] = None, special_catchphrase=False):
        nonlocal left_y
        draw.text((left_x, left_y), f"{label}:", font=section_font, fill=theme["text"])
        left_y += text_height(section_font) + label_gap

        if bullets is not None:
            lines, _ = measure_bullets_height(bullets, body_font, left_max_w - body_indent_px, line_gap, bullet_indent)
            draw_bulleted_lines(lines)
        else:
            f = italic_font if italic else body_font
            lines, _ = measure_paragraph_height(str(content), f, left_max_w - body_indent_px, line_gap)
            if special_catchphrase:
                y_cursor = left_y
                for ln in lines:
                    draw_glow_text(
                        image,
                        (left_x + body_indent_px, y_cursor),
                        ln,
                        f,
                        glow_color=accent_rgba,
                        text_color=(230, 230, 230, 255),
                        radius=4
                    )
                    y_cursor += text_height(f) + line_gap
                left_y = y_cursor
            else:
                for ln in lines:
                    draw.text((left_x + body_indent_px, left_y), ln, font=f, fill=theme["text"])
                    left_y += text_height(f) + line_gap

        left_y += section_gap

    # Order
    draw_section("Power", power)
    draw_section("Weakness", weakness)
    draw_section("Nemesis", nemesis)
    draw_section("Lair", lair)
    draw_section("Catchphrase", catchphrase, italic=True, special_catchphrase=True)
    draw_section("Crimes", "", bullets=crimes)
    draw_section("Faction", faction)

    # Threat Meter
    draw.text((left_x, left_y), "Threat Level:", font=section_font, fill=theme["text"])
    left_y += text_height(section_font) + label_gap
    meter_w = card_width - (margin * 2) - body_indent_px  # align to Origin width
    draw_threat_meter(image, draw, left_x + body_indent_px, left_y, meter_w, threat_level, body_font)
    left_y += THREAT_METER_HEIGHT + section_gap + 4

    # Divider + Origin (normal text, no drop cap)
    y_origin = max(left_y, (margin + portrait_size[1]) + margin)
    divider_y = y_origin - int(section_gap * 0.5)
    draw.line([(margin, divider_y), (card_width - margin, divider_y)], fill=(255, 255, 255, 60), width=2)

    draw.text((margin, y_origin), "Origin:", font=section_font, fill=theme["text"])
    y_origin += text_height(section_font) + label_gap

    # Just wrap/draw Origin normally
    lines, _ = measure_paragraph_height(str(origin_text), body_font, card_width - (margin*2), line_gap)
    for ln in lines:
        draw.text((margin + body_indent_px, y_origin), ln, font=body_font, fill=theme["text"])
        y_origin += text_height(body_font) + line_gap

    # Footer: hashtag left, QR right (pinned to bottom)
    footer_y = card_height - FOOTER_BAND_H
    draw.line([(margin, footer_y), (card_width - margin, footer_y)], fill=(255,255,255,40), width=1)
    footer_y += 10

    ht = text_height(body_font)
    draw.text((margin, footer_y + (FOOTER_BAND_H - ht)//2), HASHTAG_TEXT, font=body_font, fill=(235,235,235,255))

    if os.path.exists(QR_STAMP):
        try:
            qr = Image.open(QR_STAMP).convert("RGBA").resize((QR_SIZE, QR_SIZE), Image.LANCZOS)
            qr_x = card_width - margin - QR_SIZE
            qr_y = footer_y + (FOOTER_BAND_H - QR_SIZE)//2
            image.paste(qr, (qr_x, qr_y), qr)
        except Exception:
            pass


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
    client = OpenAI()

    gender_hint = (villain.get("gender", "unknown") or "").lower()
    if "female" in gender_hint:
        gender_phrase = "feminine, graceful energy"
    elif "male" in gender_hint:
        gender_phrase = "masculine, powerful energy"
    else:
        gender_phrase = "mysterious energy"

    theme_line = _theme_style_line(villain)

    origin_s = sanitize_for_images(villain.get("origin", ""))
    power_s  = sanitize_for_images(villain.get("power", ""))

    system_prompt = (
        "You compose PG-13-safe visual prompts for an image model. Output 1–2 cinematic sentences, appearance only. "
        "Imply gender with visual adjectives. Do NOT include any words or writing of any kind: no text, no typography, "
        "no letters, no numbers, no captions, no subtitles, no posters, no billboards, no signage, no logos, no UI. "
        "Absolutely forbid any written words from appearing in the image—even if they appear in this prompt. "
        "If a style like glitch/cyberpunk/poster would suggest UI, labels, displays or screens, reinterpret it purely "
        "as lighting, texture, color, or atmosphere; omit panels, monitors, interfaces, graffiti, labels, or signage."
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
        fallback = (
            "Cinematic PG-13 villain portrait, 3/4 bust, dramatic lighting, detailed clothing and atmosphere; "
            "no words or writing of any kind (no text, letters, numbers, captions, subtitles, posters, signage, logos)."
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
    kwargs = dict(
        model="dall-e-3",
        prompt=prompt,
        n=1,
        size="1024x1024",
        response_format="b64_json",
        style="natural",   # ← use natural to reduce graphic-design artifacts
    )
    # (If you want to sometimes try vivid, keep the arg but default is now natural.)
    return client.images.generate(**kwargs)


def _safe_placeholder(out_path: str) -> str:
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
    client = OpenAI()
    visual_prompt = generate_visual_prompt(villain)
    final_prompt = visual_prompt

    os.makedirs(IMAGE_FOLDER, exist_ok=True)
    vid = hash_villain(villain)
    img_path = os.path.join(IMAGE_FOLDER, f"ai_portrait_{vid}.png")

    image_calls = 0
    try:
        # First attempt
        resp = _gen_once(client, final_prompt, allow_style=True)
        image_calls += 1
        b64 = resp.data[0].b64_json
        png_bytes = _decode_and_check_png(b64)

        # Optional OCR reroll once if text is detected (only runs if pytesseract + Tesseract exist)
        try:
            has_words = _contains_text(png_bytes)
        except Exception:
            has_words = False  # silently skip OCR if OCR tool isn't available

        if has_words:
            # Make the background plainer to avoid accidental labels/signs
            reroll_prompt = (
                final_prompt
                + " Plain, uncluttered background; no screens, no panels, no posters, no signs or signage."
            )
            resp2 = _gen_once(client, reroll_prompt, allow_style=False)
            image_calls += 1
            b64 = resp2.data[0].b64_json
            png_bytes = _decode_and_check_png(b64)

        with open(img_path, "wb") as f:
            f.write(png_bytes)

        set_debug_info(context="DALL·E Image", prompt=final_prompt, cost_only=True, image_count=image_calls)
        return img_path

    except Exception as e1:
        print(f"[Image attempt 1 failed, retrying safe fallback] {e1}")
        safe_theme = safe_theme_line(villain)
        gender_hint = (villain.get("gender", "unknown") or "").lower()
        if "female" in gender_hint:
            gender_phrase = "feminine"
        elif "male" in gender_hint:
            gender_phrase = "masculine"
        else:
            gender_phrase = "mysterious"

        fallback_prompt = (
            f"PG-13 safe villain portrait, {gender_phrase} energy. {safe_theme} "
            "3/4 bust, dramatic cinematic lighting, detailed clothing, atmospheric background; "
            "no words or writing of any kind (no text, letters, numbers, captions, posters, signage, logos). "
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
                set_debug_info(context="DALL·E Image (placeholder due to safety)", cost_only=True, image_count=image_calls or 1)
            except Exception:
                pass
            return placeholder


__all__ = [
    "create_villain_card",
    "save_villain_to_log",
    "generate_ai_portrait",
    "STYLE_THEMES"
]
